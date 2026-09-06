"""Canonical Olares music API in front of ACE-Step's native async API."""

from __future__ import annotations

import atexit
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse


NATIVE_BASE = "http://127.0.0.1:8002"
MODEL_NAME = os.getenv("MODEL_NAME", "ACE-Step/acestep-v15-xl-sft")
QUALITY_MODEL = os.getenv("ACESTEP_CONFIG_PATH", "acestep-v15-xl-sft")
TASKS: dict[str, dict[str, Any]] = {}
TASKS_LOCK = threading.Lock()
REPAINT_INPUT_DIR = os.getenv("REPAINT_INPUT_DIR", "/app/data/repaint-inputs")
MAX_REPAINT_AUDIO_BYTES = 64 * 1024 * 1024

app = FastAPI(title="Olares Music Engine", version="1")


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _native_json(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        NATIVE_BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            parsed = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _error(502, "upstream_unavailable", f"ACE-Step native API unavailable: {exc}") from exc
    if not isinstance(parsed, dict) or parsed.get("code", 200) != 200:
        message = parsed.get("error", "ACE-Step request failed") if isinstance(parsed, dict) else "ACE-Step request failed"
        raise _error(502, "upstream_error", str(message))
    return parsed


def _task(task_id: str) -> dict[str, Any]:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            raise _error(410, "task_lost", "The engine restarted and no longer knows this generation.")
        return dict(task)


def _public(task: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": task["id"],
        "object": "music.generation",
        "status": task["status"],
        "created_at": task["created_at"],
        "model": MODEL_NAME,
        "outputs": task.get("outputs", []),
    }
    if task.get("error"):
        result["error"] = task["error"]
    return result


def _options(source: dict[str, Any]) -> dict[str, Any]:
    value = source.get("provider_options") or {}
    if not isinstance(value, dict):
        raise _error(400, "invalid_provider_options", "provider_options must be an object.")
    allowed = {
        "quality_profile", "bpm", "guidance_scale", "key_scale",
        "time_signature", "vocal_language", "vocal_type", "section_structure",
        "repaint_start_seconds", "repaint_end_seconds", "repaint_mode", "repaint_strength",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(400, "unknown_provider_option", f"Unsupported provider option: {unknown[0]}.")
    return value


def _number(options: dict[str, Any], key: str, minimum: float, maximum: float) -> float | None:
    if key not in options or options[key] in (None, ""):
        return None
    try:
        value = float(options[key])
    except (TypeError, ValueError) as exc:
        raise _error(400, f"invalid_{key}", f"{key} must be a number.") from exc
    if value < minimum or value > maximum:
        raise _error(400, f"invalid_{key}", f"{key} must be between {minimum:g} and {maximum:g}.")
    return value


def _described_prompt(prompt: str, options: dict[str, Any]) -> str:
    additions = []
    vocal_type = str(options.get("vocal_type", "")).strip()
    if vocal_type:
        additions.append(f"Vocal character: {vocal_type}")
    described = ". ".join([prompt, *additions])
    if len(described) > 512:
        raise _error(400, "invalid_prompt", "prompt and vocal description must fit within 512 characters.")
    return described


def _decode_repaint_audio(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("data:audio/") or ";base64," not in value[:128]:
        raise _error(400, "invalid_input_audio", "input_audio must be a base64 audio data URL.")
    header, encoded = value.split(",", 1)
    subtype = header[11:].split(";", 1)[0].lower()
    suffix = {"wav": "wav", "wave": "wav", "x-wav": "wav", "mpeg": "mp3", "mp3": "mp3", "flac": "flac", "ogg": "ogg"}.get(subtype)
    if suffix is None:
        raise _error(415, "unsupported_input_audio", "Repaint input must be WAV, MP3, FLAC, or OGG.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _error(400, "invalid_input_audio", "input_audio contains invalid base64 data.") from exc
    if not raw or len(raw) > MAX_REPAINT_AUDIO_BYTES:
        raise _error(413, "input_audio_too_large", "Repaint input audio must be between 1 byte and 64 MiB.")
    os.makedirs(REPAINT_INPUT_DIR, mode=0o750, exist_ok=True)
    path = os.path.join(REPAINT_INPUT_DIR, f"{uuid.uuid4().hex}.{suffix}")
    with open(path, "xb") as output:
        output.write(raw)
    return path


def _cleanup_source(task: dict[str, Any]) -> None:
    path = task.pop("source_path", "")
    if path:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "ACE-Step"}],
    }


@app.get("/api/engine-spec")
def engine_spec() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "model": MODEL_NAME,
        "mode": "music_generation",
        "implements": ["music.generate", "music.repaint"],
        "declares": ["music.generate", "music.repaint"],
        "serves": ["music.generate", "music.repaint"],
        "max_concurrency": 1,
        "workers": 1,
        "extensions": {
            "creative": {
                "media": "music",
                "operations": ["generate", "repaint"],
            },
            "music": {
                "quality_profiles": ["quality", "high_quality"],
                "default_quality_profile": "high_quality",
                "music_controls": ["bpm", "key_scale", "time_signature", "vocal_language", "vocal_type", "section_structure"],
            }
        },
        "endpoints": [
            {"method": "GET", "path": "/v1/models", "available": True},
            {"method": "POST", "path": "/v1/music/generations", "available": True, "async_supported": True},
            {"method": "GET", "path": "/v1/music/generations/{id}", "available": True, "async_supported": True},
            {"method": "GET", "path": "/v1/music/generations/{id}/content", "available": True},
            {"method": "DELETE", "path": "/v1/music/generations/{id}", "available": True},
        ],
    }


@app.post("/v1/music/generations", status_code=202)
async def create_generation(request: Request) -> dict[str, Any]:
    try:
        source = await request.json()
    except json.JSONDecodeError as exc:
        raise _error(400, "invalid_json", "Request body must be JSON.") from exc
    prompt = str(source.get("prompt", "")).strip()
    lyrics = str(source.get("lyrics", "")).strip()
    instrumental = bool(source.get("instrumental", False))
    duration = int(source.get("duration_seconds", 240))
    options = _options(source)
    profile = str(options.get("quality_profile", "high_quality")).strip().lower()
    if profile not in {"quality", "high_quality"}:
        raise _error(400, "invalid_quality_profile", "quality_profile must be quality or high_quality.")
    bpm = _number(options, "bpm", 30, 300)
    guidance = _number(options, "guidance_scale", 7, 9)
    key_scale = str(options.get("key_scale", "")).strip()
    time_signature = str(options.get("time_signature", "")).strip()
    vocal_language = str(options.get("vocal_language", "")).strip()
    if time_signature and time_signature not in {"2", "3", "4", "6"}:
        raise _error(400, "invalid_time_signature", "time_signature must be 2, 3, 4, or 6.")
    if len(key_scale) > 40 or len(vocal_language) > 16:
        raise _error(400, "invalid_provider_options", "Music control text is too long.")
    if not prompt or len(prompt) > 512:
        raise _error(400, "invalid_prompt", "prompt must contain 1-512 characters.")
    if len(lyrics) > 4096:
        raise _error(400, "invalid_lyrics", "lyrics must contain at most 4096 characters.")
    if instrumental and lyrics:
        raise _error(400, "lyrics_not_allowed", "lyrics must be empty for instrumental music.")
    if duration < 10 or duration > 600:
        raise _error(400, "invalid_duration", "duration_seconds must be between 10 and 600.")

    operation = str(source.get("operation", "generate")).strip().lower()
    if operation not in {"generate", "repaint"}:
        raise _error(400, "invalid_operation", "operation must be generate or repaint.")
    source_path = ""
    if operation == "repaint":
        source_path = _decode_repaint_audio(source.get("input_audio"))
        start = _number(options, "repaint_start_seconds", 0, duration)
        end = _number(options, "repaint_end_seconds", 0, duration)
        repaint_mode = str(options.get("repaint_mode", "balanced")).strip().lower()
        if start is None or end is None or end <= start:
            os.remove(source_path)
            raise _error(400, "invalid_repaint_range", "repaint_end_seconds must be greater than repaint_start_seconds.")
        if repaint_mode not in {"conservative", "balanced", "aggressive"}:
            os.remove(source_path)
            raise _error(400, "invalid_repaint_mode", "repaint_mode must be conservative, balanced, or aggressive.")
    native = {
        "prompt": _described_prompt(prompt, options),
        "lyrics": "" if instrumental else lyrics,
        "thinking": True,
        "audio_format": "wav",
        "audio_duration": duration,
        "batch_size": 1,
        "model": QUALITY_MODEL,
        "task_type": "repaint" if operation == "repaint" else "text2music",
        "inference_steps": 64 if profile == "high_quality" else 50,
        "use_adg": profile == "high_quality",
        "guidance_scale": guidance if guidance is not None else 7.0,
        "shift": 1.0,
        "infer_method": "ode",
    }
    if bpm is not None:
        native["bpm"] = int(bpm)
    if key_scale:
        native["key_scale"] = key_scale
    if time_signature:
        native["time_signature"] = time_signature
    if vocal_language:
        native["vocal_language"] = vocal_language
    if operation == "repaint":
        native["src_audio_path"] = source_path
        native["repainting_start"] = start
        native["repainting_end"] = end
        native["repaint_mode"] = repaint_mode
        strength = _number(options, "repaint_strength", 0, 1)
        native["repaint_strength"] = strength if strength is not None else 0.5
    if "seed" in source:
        native["seed"] = int(source["seed"])
        native["use_random_seed"] = False
    else:
        native["use_random_seed"] = True
    try:
        released = _native_json("/release_task", native)
    except Exception:
        if source_path:
            os.remove(source_path)
        raise
    data = released.get("data") or {}
    task_id = str(data.get("task_id", ""))
    if not task_id:
        raise _error(502, "invalid_upstream_response", "ACE-Step did not return a task ID.")
    task = {
        "id": task_id,
        "status": "queued",
        "created_at": int(time.time()),
        "outputs": [],
        "native_outputs": {},
        "source_path": source_path,
    }
    with TASKS_LOCK:
        TASKS[task_id] = task
    return _public(task)


def _decode_native_outputs(task_id: str, value: Any) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise _error(502, "invalid_upstream_response", "ACE-Step returned malformed result JSON.") from exc
    rows = value if isinstance(value, list) else []
    outputs: list[dict[str, Any]] = []
    native: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("file"):
            continue
        output_id = "out_" + hashlib.sha256(f"{task_id}:{index}".encode()).hexdigest()[:16]
        file_url = str(row["file"])
        suffix = urllib.parse.urlparse(file_url).path.rsplit(".", 1)[-1].lower()
        content_type = mimetypes.types_map.get("." + suffix, "audio/wav")
        metas = row.get("metas") if isinstance(row.get("metas"), dict) else {}
        outputs.append(
            {
                "id": output_id,
                "content_type": content_type,
                "duration_seconds": float(metas.get("duration") or 0),
                "content_url": f"/v1/music/generations/{task_id}/content?output_id={output_id}",
            }
        )
        native[output_id] = file_url
    return outputs, native


@app.get("/v1/music/generations/{task_id}")
def get_generation(task_id: str) -> dict[str, Any]:
    task = _task(task_id)
    if task["status"] not in {"completed", "failed"}:
        queried = _native_json("/query_result", {"task_id_list": [task_id]})
        rows = queried.get("data") or []
        row = rows[0] if isinstance(rows, list) and rows else {}
        native_status = int(row.get("status", 0)) if isinstance(row, dict) else 0
        if native_status == 1:
            outputs, native_outputs = _decode_native_outputs(task_id, row.get("result"))
            task["status"] = "completed"
            task["outputs"] = outputs
            task["native_outputs"] = native_outputs
            _cleanup_source(task)
        elif native_status == 2:
            task["status"] = "failed"
            task["error"] = {"code": "generation_failed", "message": str(row.get("error") or "ACE-Step generation failed.")}
            _cleanup_source(task)
        else:
            task["status"] = "running"
        with TASKS_LOCK:
            TASKS[task_id] = task
    return _public(task)


@app.delete("/v1/music/generations/{task_id}")
def delete_generation(task_id: str) -> Response:
    _task(task_id)
    raise _error(422, "cancellation_unsupported", "ACE-Step cannot reliably interrupt a running generation.")


@app.get("/v1/music/generations/{task_id}/content")
def generation_content(task_id: str, output_id: str = Query(...)) -> StreamingResponse:
    task = _task(task_id)
    if task["status"] != "completed":
        raise _error(409, "generation_not_completed", "Audio is available only after completion.")
    native_url = task.get("native_outputs", {}).get(output_id)
    if not native_url:
        raise _error(404, "output_not_found", "The requested output does not exist.")
    parsed = urllib.parse.urlparse(native_url)
    if parsed.path != "/v1/audio":
        raise _error(502, "invalid_upstream_response", "ACE-Step returned an unsupported output URL.")
    upstream = urllib.request.urlopen(NATIVE_BASE + parsed.path + "?" + parsed.query, timeout=60)
    content_type = upstream.headers.get_content_type() or "audio/wav"
    return StreamingResponse(upstream, media_type=content_type)


def _wait_native(process: subprocess.Popen[Any], timeout: int = 1800) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ACE-Step native API exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(NATIVE_BASE + "/health", timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)
    raise RuntimeError("timed out waiting for ACE-Step native API")


def main() -> None:
    native = subprocess.Popen(
        [sys.executable, "/opt/olares/staged_api.py", "--host", "127.0.0.1", "--port", "8002"],
        start_new_session=False,
    )

    def stop_native() -> None:
        if native.poll() is None:
            native.send_signal(signal.SIGTERM)
            try:
                native.wait(timeout=30)
            except subprocess.TimeoutExpired:
                native.kill()

    atexit.register(stop_native)
    _wait_native(native)
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)


if __name__ == "__main__":
    main()
