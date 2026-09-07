"""Canonical Olares music API in front of ACE-Step's native async API."""

from __future__ import annotations

import atexit
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
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
CLEAN_NEGATIVE_PROMPT = (
    "background hiss, static, vinyl crackle, tape noise, lo-fi noise, noisy room, "
    "muddy wash, harsh sibilance, brittle cymbals, distorted vocal"
)
VOCAL_LANGUAGES = (
    "ar", "az", "bg", "bn", "ca", "cs", "da", "de", "el", "en", "es", "fa", "fi", "fr", "he", "hi",
    "hr", "ht", "hu", "id", "is", "it", "ja", "ko", "la", "lt", "ms", "ne", "nl", "no", "pa", "pl",
    "pt", "ro", "ru", "sa", "sk", "sr", "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur", "vi",
    "yue", "zh",
)
VOCAL_LANGUAGE_SET = frozenset(VOCAL_LANGUAGES)

app = FastAPI(title="Olares Music Engine", version="1")


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _native_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        NATIVE_BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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
    if task.get("effective_prompt"):
        result["effective_prompt"] = task["effective_prompt"]
    if task.get("effective_lyrics"):
        result["effective_lyrics"] = task["effective_lyrics"]
    if task.get("metas"):
        result["metas"] = task["metas"]
    return result


def _public_format(task: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": task["id"],
        "object": "music.format",
        "status": task["status"],
        "created_at": task["created_at"],
        "model": MODEL_NAME,
        "draft_prompt": task["draft_prompt"],
        "draft_lyrics": task["draft_lyrics"],
        "vocal_language": task["vocal_language"],
        "warnings": task.get("warnings", []),
        "metrics": task.get("metrics", {}),
    }
    if task.get("effective_prompt") is not None:
        result["effective_prompt"] = task["effective_prompt"]
    if task.get("effective_lyrics") is not None:
        result["effective_lyrics"] = task["effective_lyrics"]
    if task.get("error"):
        result["error"] = task["error"]
    return result


def _active_task(kind: str) -> bool:
    with TASKS_LOCK:
        return any(
            task.get("kind") == kind and task.get("status") not in {"completed", "failed"}
            for task in TASKS.values()
        )


def _line_metrics(lyrics: str, language: str) -> tuple[list[str], dict[str, Any]]:
    lines = [
        line.strip() for line in lyrics.splitlines()
        if line.strip() and not (line.strip().startswith("[") and line.strip().endswith("]"))
    ]
    if not lines:
        return [], {"line_count": 0, "line_length_variation": 0.0, "uniformity_risk": "low", "syntactic_pattern_risk": "low"}
    if language in {"zh", "yue"}:
        counts = [sum(1 for char in line if "\u3400" <= char <= "\u9fff") for line in lines]
    else:
        counts = [len(line.split()) if " " in line else len(line) for line in lines]
    mean = sum(counts) / len(counts)
    variation = 0.0 if mean == 0 else (sum(abs(value - mean) for value in counts) / len(counts)) / mean
    most_common = max(counts.count(value) for value in set(counts)) / len(counts)
    longest_run = 1
    current_run = 1
    for previous, current in zip(counts, counts[1:]):
        if previous == current:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    risk = "high" if most_common >= 0.7 or longest_run >= 4 else "low"
    warnings = []
    if language in {"zh", "yue"} and risk == "high":
        warnings.append("uniform_chinese_line_lengths")
    if language == "yue":
        warnings.append("cantonese_tone_melody_alignment_requires_listening_review")
    syntactic_risk = "high" if language in {"zh", "yue"} and _repeated_chinese_opening(lyrics) else "low"
    if syntactic_risk == "high":
        warnings.append("repetitive_chinese_line_openings")
    return warnings, {
        "line_count": len(lines),
        "line_length_variation": round(variation, 3),
        "uniformity_risk": risk,
        "syntactic_pattern_risk": syntactic_risk,
    }


def _repeated_chinese_opening(lyrics: str) -> bool:
    previous = ""
    run = 0
    for raw in lyrics.splitlines():
        line = raw.strip()
        if not line or (line.startswith("[") and line.endswith("]")):
            previous, run = "", 0
            continue
        opening = "".join(char for char in line if "\u3400" <= char <= "\u9fff")[:1]
        if opening and opening == previous:
            run += 1
        else:
            previous, run = opening, 1
        if run >= 4:
            return True
    return False


def _fit_caption(caption: str, limit: int = 512) -> tuple[str, bool]:
    """Fit ACE's unconstrained /format_input caption into our API contract."""
    caption = " ".join(caption.split()).strip()
    if len(caption) <= limit:
        return caption, False

    prefix = caption[:limit]
    # Prefer a complete sentence near the end of the available budget. ACE
    # commonly emits 550-700 character prose despite receiving a <=512 input.
    boundaries = [match.end() for match in re.finditer(r"[.!?;](?:\s|$)", prefix)]
    cutoff = max((value for value in boundaries if value >= limit // 2), default=0)
    if not cutoff:
        cutoff = prefix.rfind(" ")
    if cutoff <= 0:
        cutoff = limit
    return prefix[:cutoff].strip(), True


def _run_format_task(task_id: str, temperature: float, duration: int) -> None:
    with TASKS_LOCK:
        task = dict(TASKS[task_id])
        task["status"] = "running"
        TASKS[task_id] = task
    try:
        native = _native_json(
            "/format_input",
            {
                "prompt": task["draft_prompt"],
                "lyrics": task["draft_lyrics"],
                "temperature": temperature,
                "param_obj": json.dumps({
                    "duration": duration,
                    "language": task["vocal_language"],
                }),
            },
            timeout=300,
        )
        data = native.get("data") or {}
        effective_prompt, caption_truncated = _fit_caption(
            str(data.get("caption") or task["draft_prompt"])
        )
        effective_lyrics = str(data.get("lyrics") or task["draft_lyrics"]).strip()
        if not effective_prompt:
            raise ValueError("ACE-Step returned an invalid formatted caption")
        if len(effective_lyrics) > 4096:
            raise ValueError("ACE-Step returned formatted lyrics that exceed 4096 characters")
        warnings, metrics = _line_metrics(effective_lyrics, task["vocal_language"])
        if caption_truncated:
            warnings.insert(0, "formatted_caption_trimmed_to_512_characters")
        task.update({
            "status": "completed",
            "effective_prompt": effective_prompt,
            "effective_lyrics": effective_lyrics,
            "warnings": warnings,
            "metrics": metrics,
        })
    except Exception as exc:
        task.update({
            "status": "failed",
            "error": {"code": "format_failed", "message": str(exc)},
        })
    with TASKS_LOCK:
        TASKS[task_id] = task


def _options(source: dict[str, Any]) -> dict[str, Any]:
    value = source.get("provider_options") or {}
    if not isinstance(value, dict):
        raise _error(400, "invalid_provider_options", "provider_options must be an object.")
    allowed = {
        "quality_profile", "bpm", "guidance_scale", "key_scale",
        "time_signature", "vocal_language", "vocal_type", "section_structure",
        "production_profile", "caption_mode",
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
    if options.get("production_profile", "clean") == "clean":
        additions.append(
            "Production: clean studio recording, low noise floor, clear lead vocal, "
            "separated instruments, controlled sibilance, polished master"
        )
    described = prompt
    for addition in additions:
        candidate = f"{described}. {addition}"
        if len(candidate) <= 512:
            described = candidate
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
        "implements": ["music.generate", "music.repaint", "music.format"],
        "declares": ["music.generate", "music.repaint", "music.format"],
        "serves": ["music.generate", "music.repaint", "music.format"],
        "max_concurrency": 1,
        "workers": 1,
        "extensions": {
            "creative": {
                "media": "music",
                "operations": ["generate", "repaint", "format"],
            },
            "music": {
                "quality_profiles": ["quality", "high_quality"],
                "default_quality_profile": "high_quality",
                "production_profiles": ["clean", "textured"],
                "default_production_profile": "clean",
                "caption_modes": ["preserve", "enhance"],
                "default_caption_mode": "preserve",
                "vocal_languages": list(VOCAL_LANGUAGES),
                "music_controls": ["bpm", "key_scale", "time_signature", "vocal_language", "vocal_type", "section_structure", "production_profile", "caption_mode"],
            }
        },
        "endpoints": [
            {"method": "GET", "path": "/v1/models", "available": True},
            {"method": "POST", "path": "/v1/music/generations", "available": True, "async_supported": True},
            {"method": "GET", "path": "/v1/music/generations/{id}", "available": True, "async_supported": True},
            {"method": "GET", "path": "/v1/music/generations/{id}/content", "available": True},
            {"method": "DELETE", "path": "/v1/music/generations/{id}", "available": True},
            {"method": "POST", "path": "/v1/music/formats", "available": True, "async_supported": True},
            {"method": "GET", "path": "/v1/music/formats/{id}", "available": True, "async_supported": True},
        ],
    }


@app.post("/v1/music/formats", status_code=202)
async def create_format(request: Request) -> dict[str, Any]:
    try:
        source = await request.json()
    except json.JSONDecodeError as exc:
        raise _error(400, "invalid_json", "Request body must be JSON.") from exc
    allowed = {"model", "prompt", "lyrics", "vocal_language", "duration_seconds", "temperature"}
    unknown = sorted(set(source) - allowed)
    if unknown:
        raise _error(400, "unknown_field", f"Unsupported format field: {unknown[0]}.")
    prompt = str(source.get("prompt", "")).strip()
    lyrics = str(source.get("lyrics", "")).strip()
    language = str(source.get("vocal_language", "")).strip().lower()
    try:
        duration = int(source.get("duration_seconds", 240))
        temperature = float(source.get("temperature", 0.85))
    except (TypeError, ValueError) as exc:
        raise _error(400, "invalid_format_request", "duration_seconds and temperature must be numbers.") from exc
    if not prompt or len(prompt) > 512:
        raise _error(400, "invalid_prompt", "prompt must contain 1-512 characters.")
    if not lyrics or len(lyrics) > 4096:
        raise _error(400, "invalid_lyrics", "lyrics must contain 1-4096 characters.")
    if language not in VOCAL_LANGUAGE_SET:
        raise _error(400, "invalid_vocal_language", "vocal_language must be a supported ACE-Step language code.")
    if duration < 10 or duration > 600:
        raise _error(400, "invalid_duration", "duration_seconds must be between 10 and 600.")
    if temperature < 0 or temperature > 2:
        raise _error(400, "invalid_temperature", "temperature must be between 0 and 2.")
    if _active_task("format"):
        raise _error(409, "format_in_progress", "Another ACE-Step format task is already running.")
    task_id = "fmt_" + uuid.uuid4().hex
    task = {
        "id": task_id,
        "kind": "format",
        "status": "queued",
        "created_at": int(time.time()),
        "draft_prompt": prompt,
        "draft_lyrics": lyrics,
        "vocal_language": language,
        "warnings": [],
        "metrics": {},
    }
    with TASKS_LOCK:
        TASKS[task_id] = task
    threading.Thread(target=_run_format_task, args=(task_id, temperature, duration), daemon=True).start()
    return _public_format(task)


@app.get("/v1/music/formats/{task_id}")
def get_format(task_id: str) -> dict[str, Any]:
    task = _task(task_id)
    if task.get("kind") != "format":
        raise _error(404, "format_not_found", "The requested format task does not exist.")
    return _public_format(task)


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
    production_profile = str(options.get("production_profile", "clean")).strip().lower()
    caption_mode = str(options.get("caption_mode", "preserve")).strip().lower()
    if production_profile not in {"clean", "textured"}:
        raise _error(400, "invalid_production_profile", "production_profile must be clean or textured.")
    if caption_mode not in {"preserve", "enhance"}:
        raise _error(400, "invalid_caption_mode", "caption_mode must be preserve or enhance.")
    key_scale = str(options.get("key_scale", "")).strip()
    time_signature = str(options.get("time_signature", "")).strip()
    vocal_language = str(options.get("vocal_language", "")).strip().lower()
    if time_signature and time_signature not in {"2", "3", "4", "6"}:
        raise _error(400, "invalid_time_signature", "time_signature must be 2, 3, 4, or 6.")
    vocal_type = str(options.get("vocal_type", "")).strip()
    if len(key_scale) > 40 or len(vocal_language) > 16 or len(vocal_type) > 120:
        raise _error(400, "invalid_provider_options", "Music control text is too long.")
    if vocal_language and vocal_language not in VOCAL_LANGUAGE_SET and not (instrumental and vocal_language == "unknown"):
        raise _error(400, "invalid_vocal_language", "vocal_language must be a supported ACE-Step language code.")
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
        "use_format": False,
        "use_cot_caption": caption_mode == "enhance",
        "use_cot_lyrics": False,
        "audio_format": "wav",
        "audio_duration": duration,
        "batch_size": 1,
        "model": QUALITY_MODEL,
        "task_type": "repaint" if operation == "repaint" else "text2music",
        "inference_steps": 64 if profile == "high_quality" else 50,
        "use_adg": profile == "high_quality",
        "guidance_scale": guidance if guidance is not None else (8.0 if profile == "high_quality" else 7.0),
        "shift": 3.0 if profile == "high_quality" else 1.0,
        "infer_method": "ode",
    }
    if production_profile == "clean":
        native["lm_negative_prompt"] = CLEAN_NEGATIVE_PROMPT
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
        "kind": "generation",
        "status": "queued",
        "created_at": int(time.time()),
        "outputs": [],
        "native_outputs": {},
        "source_path": source_path,
    }
    with TASKS_LOCK:
        TASKS[task_id] = task
    return _public(task)


def _decode_native_outputs(task_id: str, value: Any) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise _error(502, "invalid_upstream_response", "ACE-Step returned malformed result JSON.") from exc
    rows = value if isinstance(value, list) else []
    outputs: list[dict[str, Any]] = []
    native: dict[str, str] = {}
    effective: dict[str, Any] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("file"):
            continue
        output_id = "out_" + hashlib.sha256(f"{task_id}:{index}".encode()).hexdigest()[:16]
        file_url = str(row["file"])
        suffix = urllib.parse.urlparse(file_url).path.rsplit(".", 1)[-1].lower()
        content_type = mimetypes.types_map.get("." + suffix, "audio/wav")
        metas = row.get("metas") if isinstance(row.get("metas"), dict) else {}
        if not effective:
            effective = {
                "effective_prompt": str(row.get("prompt") or "").strip(),
                "effective_lyrics": str(row.get("lyrics") or "").strip(),
                "metas": metas,
            }
        outputs.append(
            {
                "id": output_id,
                "content_type": content_type,
                "duration_seconds": float(metas.get("duration") or 0),
                "content_url": f"/v1/music/generations/{task_id}/content?output_id={output_id}",
            }
        )
        native[output_id] = file_url
    return outputs, native, effective


@app.get("/v1/music/generations/{task_id}")
def get_generation(task_id: str) -> dict[str, Any]:
    task = _task(task_id)
    if task["status"] not in {"completed", "failed"}:
        queried = _native_json("/query_result", {"task_id_list": [task_id]})
        rows = queried.get("data") or []
        row = rows[0] if isinstance(rows, list) and rows else {}
        native_status = int(row.get("status", 0)) if isinstance(row, dict) else 0
        if native_status == 1:
            outputs, native_outputs, effective = _decode_native_outputs(task_id, row.get("result"))
            task["status"] = "completed"
            task["outputs"] = outputs
            task["native_outputs"] = native_outputs
            task.update(effective)
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
