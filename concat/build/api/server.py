"""Authenticated HTTP and stateless MCP transport for the Concat 0.2.2 engine."""
import base64
import copy
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(os.environ.get("CONCAT_PROJECTS", "/config/Projects")).resolve()
CONFIG = Path(os.environ.get("CONCAT_CONFIG", "/config"))
FLAG = CONFIG / ".concat-api-editing"
TOKEN = os.environ.get("CONCAT_API_TOKEN", "")
CLI = os.environ.get("CONCAT_CLI", "/opt/concat-cli/concat-cli")
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
IDLE_SECONDS = 900
METHODS = {"version", "project.create", "project.open", "project.close", "project.get",
           "project.document", "project.save", "project.setVideo", "edit.apply",
           "edit.undo", "edit.redo", "media.probe", "media.import", "catalogue.list",
           "preview.frame", "export.run"}
MUTATING = {"project.create", "project.setVideo", "edit.apply", "edit.undo", "edit.redo", "media.import"}


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def scoped(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise Problem("A nonempty project-relative path is required")
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_relative_to(ROOT):
        raise Problem("Path must remain inside Documents/Concat", 403)
    return path


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def checked_paths(value):
    """Validate paths also inside project documents, media records and batch edits."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "file", "location", "output", "fontPath"} and isinstance(item, str) and item:
                value[key] = str(scoped(item))
            else:
                checked_paths(item)
    elif isinstance(value, list):
        for item in value:
            checked_paths(item)


def default_cjk_font(command):
    """Give newly created CJK titles a usable face without overriding a choice."""
    if not isinstance(command, dict):
        return
    if command.get("op") == "batch":
        for child in command.get("commands", []):
            default_cjk_font(child)
    if command.get("op") == "addTextClip":
        style = command.get("style", {})
        content = style.get("content", "")
        if not style.get("fontFamily") and isinstance(content, str) and any(
            "\u3400" <= char <= "\u9fff" or "\u3000" <= char <= "\u303f"
            for char in content
        ):
            style["fontFamily"] = "Noto Sans CJK SC"


class Engine:
    def __init__(self):
        self.lock = threading.RLock()
        self.proc = None
        self.active = False
        self.touched = time.monotonic()
        self.fingerprints = {}
        self.jobs = {}
        self.tasks = queue.Queue(maxsize=16)
        self.jobs_dir = CONFIG / "api-jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        for path in self.jobs_dir.glob("*.json"):
            job = json.loads(path.read_text())
            if job["state"] in {"queued", "running"}:
                job.update(state="interrupted", error="Server restarted; inspect output before retrying")
                atomic_json(path, job)
            self.jobs[job["id"]] = job
        FLAG.unlink(missing_ok=True)
        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.expire, daemon=True).start()

    def gui_pids(self):
        found = []
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                if entry.stat().st_uid == os.getuid() and (entry / "comm").read_text().strip() == "concat":
                    found.append(int(entry.name))
            except (OSError, ValueError):
                pass
        return found

    def begin(self):
        with self.lock:
            self.touched = time.monotonic()
            if not self.active:
                FLAG.touch(mode=0o600)
                for pid in self.gui_pids():
                    os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 8
                while self.gui_pids() and time.monotonic() < deadline:
                    time.sleep(0.1)
                if self.gui_pids():
                    FLAG.unlink(missing_ok=True)
                    raise Problem("Desktop did not stop; no project has been edited", 409)
                self.active = True
            return self.status()

    def finish(self):
        with self.lock:
            if any(j["state"] in {"queued", "running"} for j in self.jobs.values()):
                raise Problem("Wait for queued/running jobs before returning to desktop mode", 409)
            self.stop()
            self.active = False
            self.fingerprints.clear()
            FLAG.unlink(missing_ok=True)
            return self.status()

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc = None

    def status(self):
        return {"version": "0.2.2", "apiVersion": "1", "editing": self.active,
                "projectsRoot": str(ROOT), "idleTimeoutSeconds": IDLE_SECONDS,
                "jobs": [copy.deepcopy(j) for j in list(self.jobs.values())[-20:]]}

    def fingerprint(self, folder):
        path = Path(folder) / "concat.json"
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    def exchange(self, request, job=None):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen([CLI, "api"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=None, text=True, encoding="utf-8", bufsize=1,
                                         env={**os.environ, "LD_LIBRARY_PATH": "/opt/concat/lib"})
            self.fingerprints.clear()
        self.proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                self.stop()
                raise Problem("Concat engine exited; reopen the project before retrying", 502)
            response = json.loads(line)
            if "event" in response:
                if job is not None:
                    job["progress"] = response
                continue
            if "error" in response:
                raise Problem(response["error"], 422)
            return response["result"]

    def call(self, raw, job=None):
        with self.lock:
            self.touched = time.monotonic()
            if not isinstance(raw, dict) or raw.get("method") not in METHODS:
                raise Problem("Unsupported method; use concat_help for the supported API")
            request = copy.deepcopy(raw)
            method = request["method"]
            if method not in {"version", "catalogue.list", "media.probe"} and not self.active:
                raise Problem("Call concat_begin_edit first. It pauses the desktop to prevent conflicting saves.", 409)
            checked_paths(request)
            if method == "edit.apply":
                default_cjk_font(request.get("command"))
            if method == "project.create":
                name = request.get("name", "")
                if not isinstance(name, str) or not re.fullmatch(r"[^/\\\x00]{1,120}", name) or name in {".", ".."}:
                    raise Problem("Project name must be one folder name")
                request.setdefault("location", str(ROOT))
                scoped(request["location"])
                clean_name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', '-', name.strip()).strip('. ') or "Untitled project"
                created_folder = str(scoped(str(Path(request["location"]) / clean_name)))
            folder = request.get("path") if method.startswith(("project.", "edit.", "export.", "preview.")) or method == "media.import" else None
            if folder:
                if folder in self.fingerprints and self.fingerprint(folder) != self.fingerprints[folder]:
                    raise Problem("Project changed outside the API. Finish editing and reopen it before continuing.", 409)
                doc = Path(folder) / "concat.json"
                if method == "project.open" and doc.exists():
                    checked_paths(json.loads(doc.read_text(encoding="utf-8")))
                    backup = CONFIG / "api-backups" / (str(uuid.uuid4()) + ".json")
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    backup.write_bytes(doc.read_bytes())
            if method in {"preview.frame", "export.run"}:
                output = scoped(request.get("output", ""))
                if output.exists():
                    raise Problem("Output already exists; choose a new filename", 409)
                output.parent.mkdir(parents=True, exist_ok=True)
            result = self.exchange(request, job)
            if method == "project.create":
                folder = created_folder
                result["projectPath"] = str(Path(folder).relative_to(ROOT))
            if method in MUTATING:
                self.exchange({"method": "project.save", "path": folder})
            if folder:
                if method == "project.close":
                    self.fingerprints.pop(folder, None)
                else:
                    self.fingerprints[folder] = self.fingerprint(folder)
            return result

    def submit(self, request):
        with self.lock:
            if not self.active:
                raise Problem("Call concat_begin_edit first", 409)
            if self.tasks.full():
                raise Problem("Job queue is full", 429)
            job = {"id": str(uuid.uuid4()), "state": "queued", "method": request.get("method")}
            self.jobs[job["id"]] = job
            atomic_json(self.jobs_dir / (job["id"] + ".json"), job)
            self.tasks.put_nowait((copy.deepcopy(request), job))
            return copy.deepcopy(job)

    def worker(self):
        while True:
            request, job = self.tasks.get()
            try:
                job["state"] = "running"
                job["result"] = self.call(request, job)
                job["state"] = "done"
            except Exception as exc:
                job.update(state="failed", error=str(exc))
            finally:
                atomic_json(self.jobs_dir / (job["id"] + ".json"), job)
                self.tasks.task_done()

    def expire(self):
        while True:
            time.sleep(10)
            if self.active and time.monotonic() - self.touched > IDLE_SECONDS:
                if not any(j["state"] in {"queued", "running"} for j in self.jobs.values()):
                    self.finish()


def tool(name, description, properties=None, required=None, readonly=False):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": readonly, "destructiveHint": not readonly, "openWorldHint": False}}


STRING = {"type": "string"}
TOOLS = [
    tool("concat_status", "Check editing mode and jobs without changing the desktop.", readonly=True),
    tool("concat_help", "Read API methods, edit examples and the workflow. Read this before editing.", readonly=True),
    tool("concat_begin_edit", "Pause the desktop editor and enter API editing mode. Saved projects remain available. Do this before opening/creating a project."),
    tool("concat_finish_edit", "End API editing and restore the desktop. Every successful edit is already saved. Wait for jobs first."),
    tool("concat_request", "Call the Concat engine using a request object from concat_help. Paths are relative to Documents/Concat. Export and frame rendering return an async job ID.", {"request": {"type": "object"}}, ["request"]),
    tool("concat_job", "Poll a rendering job. When a preview is done, also returns its PNG image.", {"id": STRING}, ["id"], True),
    tool("concat_list_files", "List a project/media folder under Documents/Concat.", {"path": STRING}, readonly=True),
]


def help_info():
    return {"workflow": ["concat_begin_edit", "project.create or project.open", "media.import", "edit.apply", "preview.frame or export.run", "concat_job", "concat_finish_edit"],
            "paths": "Relative to Documents/Concat; no arbitrary server filesystem access. Outputs must use a new filename.",
            "fonts": "Chinese titles: use fontFamily Noto Sans CJK SC (sans) or Noto Serif CJK SC (serif). New CJK text without a fontFamily defaults to Noto Sans CJK SC. For existing titles, explicitly change their fontFamily; Latin-only fonts such as DejaVu Sans do not cover Chinese.",
            "methods": sorted(METHODS), "notes": "Edits save automatically. Never edit the same project from another process. Project state includes createdId, media IDs, timeline track IDs and clip IDs. Read returned IDs; do not invent them.",
            "examples": [
                {"method": "project.create", "location": ".", "name": "My edit", "video": {"width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1}},
                {"method": "project.open", "path": "My edit"},
                {"method": "media.import", "path": "My edit", "file": "assets/clip.mp4"},
                {"method": "edit.apply", "path": "My edit", "command": {"op": "addClipAtFirstFree", "mediaId": "<returned media ID>", "start": 0}},
                {"method": "edit.apply", "path": "My edit", "command": {"op": "trimClip", "clipId": "<clip ID>", "edge": "end", "delta": -2}},
                {"method": "edit.apply", "path": "My edit", "command": {"op": "addTextClip", "trackId": None, "start": 0, "duration": 3, "style": {"content": "My title"}}},
                {"method": "project.document", "path": "My edit"},
                {"method": "preview.frame", "path": "My edit", "time": 1, "output": "outputs/preview.png", "width": 640, "height": 360},
                {"method": "export.run", "path": "My edit", "output": "outputs/edit.mp4", "codec": "h264", "preset": "fast"}],
            "editCommands": json.loads((Path(__file__).parent / "commands.json").read_text())}


def call_tool(name, args):
    if name == "concat_status": return ENGINE.status()
    if name == "concat_help": return help_info()
    if name == "concat_begin_edit": return ENGINE.begin()
    if name == "concat_finish_edit": return ENGINE.finish()
    if name == "concat_request":
        request = args["request"]
        return ENGINE.submit(request) if request.get("method") in {"export.run", "preview.frame"} else ENGINE.call(request)
    if name == "concat_job":
        if args["id"] not in ENGINE.jobs: raise Problem("Unknown job", 404)
        return copy.deepcopy(ENGINE.jobs[args["id"]])
    if name == "concat_list_files":
        folder = scoped(args.get("path", "."))
        return {"files": [{"path": str(p.relative_to(ROOT)), "directory": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0}
                          for p in sorted(folder.iterdir()) if not p.is_symlink()]}
    raise Problem("Unknown tool")


class Handler(BaseHTTPRequestHandler):
    server_version = "ConcatAPI/1"
    def log_message(self, *_): pass

    def send_json(self, status, value=None):
        payload = json.dumps(value, ensure_ascii=False).encode() if value is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def authorize(self):
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            raise Problem("Origin is not allowed", 403)
        if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + TOKEN).encode()):
            raise Problem("A valid API bearer token is required", 401)

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            if parsed.path == "/healthz":
                return self.send_json(200, {"ok": True})
            self.authorize()
            if parsed.path == "/mcp": return self.send_json(405, {"error": "Use POST; SSE is not used"})
            if parsed.path == "/v1/status": return self.send_json(200, ENGINE.status())
            if parsed.path == "/v1/help": return self.send_json(200, help_info())
            if parsed.path == "/v1/tools": return self.send_json(200, TOOLS)
            if parsed.path.startswith("/v1/jobs/"):
                return self.send_json(200, call_tool("concat_job", {"id": parsed.path.rsplit("/", 1)[1]}))
            if parsed.path == "/v1/files":
                path = scoped(parse_qs(parsed.query).get("path", ["."])[0])
                if path.is_dir(): return self.send_json(200, call_tool("concat_list_files", {"path": str(path)}))
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with path.open("rb") as source:
                    while chunk := source.read(1024 * 1024): self.wfile.write(chunk)
                return
            raise Problem("Not found", 404)
        except Problem as exc: self.send_json(exc.status, {"error": str(exc)})
        except (OSError, ValueError) as exc: self.send_json(400, {"error": str(exc)})

    def do_PUT(self):
        temporary = None
        try:
            self.authorize()
            parsed = urlsplit(self.path)
            if parsed.path != "/v1/files": raise Problem("Not found", 404)
            path = scoped(parse_qs(parsed.query).get("path", [""])[0])
            if path.exists(): raise Problem("File already exists; choose another path", 409)
            size = int(self.headers.get("Content-Length", "-1"))
            if size < 0 or size > 2 * 1024**3: raise Problem("Content-Length must be between 0 and 2 GiB", 413)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(".upload-" + uuid.uuid4().hex)
            with temporary.open("xb") as output:
                remaining = size
                while remaining:
                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                    if not chunk: raise Problem("Upload ended early")
                    output.write(chunk)
                    remaining -= len(chunk)
            # link refuses overwrites even if another request created the destination meanwhile.
            os.link(temporary, path)
            return self.send_json(201, {"path": str(path.relative_to(ROOT)), "size": size})
        except Problem as exc: self.send_json(exc.status, {"error": str(exc)})
        except (OSError, ValueError) as exc: self.send_json(400, {"error": str(exc)})
        finally:
            if temporary: temporary.unlink(missing_ok=True)

    def do_POST(self):
        try:
            self.authorize()
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2 * 1024**2: raise Problem("JSON body must be between 1 byte and 2 MiB", 413)
            if self.headers.get_content_type() != "application/json": raise Problem("Use application/json", 415)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict): raise Problem("Expected one JSON object")
            if self.path == "/v1/call":
                result = call_tool("concat_request", {"request": data})
                return self.send_json(200, {"result": result})
            if self.path == "/v1/editing/start": return self.send_json(200, ENGINE.begin())
            if self.path == "/v1/editing/finish": return self.send_json(200, ENGINE.finish())
            if self.path != "/mcp": raise Problem("Not found", 404)
            version = self.headers.get("MCP-Protocol-Version", "2025-03-26")
            if version not in PROTOCOLS: raise Problem("Unsupported MCP protocol version")
            if data.get("jsonrpc") != "2.0": raise Problem("Expected JSON-RPC 2.0")
            if "id" not in data: return self.send_json(202)
            request_id, method, params = data["id"], data.get("method"), data.get("params", {})
            if method == "initialize":
                requested = params.get("protocolVersion")
                result = {"protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[0],
                          "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "concat-olares", "version": "0.2.0"},
                          "instructions": "Read concat_help. Begin editing before project operations; finish editing after jobs complete to restore the desktop. Paths are relative to Documents/Concat."}
            elif method == "ping": result = {}
            elif method == "tools/list": result = {"tools": TOOLS}
            elif method == "tools/call":
                try:
                    value = call_tool(params.get("name"), params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": value if isinstance(value, dict) else {"result": value}, "isError": False}
                    if params.get("name") == "concat_job" and value.get("state") == "done" and value.get("method") == "preview.frame":
                        preview = scoped(value["result"]["path"])
                        if preview.stat().st_size <= 2 * 1024**2:
                            result["content"].append({"type": "image", "mimeType": "image/png", "data": base64.b64encode(preview.read_bytes()).decode()})
                except (Problem, KeyError, TypeError, ValueError, OSError) as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            else:
                return self.send_json(200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}})
            self.send_json(200, {"jsonrpc": "2.0", "id": request_id, "result": result})
        except Problem as exc: self.send_json(exc.status, {"error": str(exc)})
        except (ValueError, KeyError, TypeError, OSError) as exc: self.send_json(400, {"error": str(exc)})

    def do_DELETE(self):
        try:
            self.authorize()
            self.send_json(405, {"error": "Stateless MCP has no transport session to delete"})
        except Problem as exc: self.send_json(exc.status, {"error": str(exc)})


if __name__ == "__main__":
    if len(TOKEN) < 32:
        raise SystemExit("CONCAT_API_TOKEN must contain at least 32 characters")
    ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG.mkdir(parents=True, exist_ok=True)
    token_file = CONFIG / "api-token"
    token_file.write_text(TOKEN, encoding="utf-8")
    token_file.chmod(0o600)
    ENGINE = Engine()
    server = ThreadingHTTPServer((os.environ.get("CONCAT_API_BIND", "0.0.0.0"), 8080), Handler)
    def shutdown(*_):
        ENGINE.stop()
        FLAG.unlink(missing_ok=True)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        server.serve_forever()
    finally:
        ENGINE.stop()
        FLAG.unlink(missing_ok=True)
