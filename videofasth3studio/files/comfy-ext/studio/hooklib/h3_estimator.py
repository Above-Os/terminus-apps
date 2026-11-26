"""Sequence accounting shared by the MiniMax H3 and FastH3 app hooks."""
import math
import os
import re
from typing import NamedTuple

FPS = 24
MAX_PIXELS = 768 * 1344
TIER_AREA = {"480p": 864 * 480, "720p": 1344 * 768}
PROMPT_TOKENS = 400


class Workload(NamedTuple):
    tokens_k: float
    frames: int
    pixels: float
    ref_video: int
    ref_image: int
    group: str


def _align_up(n):
    return n + (5 - n) % 17


def _align_down(n):
    return n - (n - 5) % 17


def _latent_t(f):
    return 2 if f <= 5 else (f - 5) // 17 * 5 + 2


def _r32(v):
    return max(32, int(round(v / 32)) * 32)


def _grid(w, h):
    return (h // 32) * (w // 32)


def _canvas(vw, vh):
    ratio = vw / vh
    nw, nh = (768 * ratio, 768) if ratio >= 1 else (768, 768 / ratio)
    if nw * nh > MAX_PIXELS:
        s = math.sqrt(MAX_PIXELS / (nw * nh))
        nw, nh = nw * s, nh * s
    cw, ch = _r32(nw), _r32(nh)
    if vw * vh < cw * ch:
        cw, ch = _r32(vw), _r32(vh)
    return cw, ch


def _ratio(aspect, items):
    if aspect:
        try:
            a, b = aspect.split(" ")[0].split(":")
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            pass
    for it in items:
        a = it["asset"]
        if it["role"] == "first_frame" and a.get("width") and a.get("height"):
            return a["width"] / a["height"]
    return 16 / 9


def workload(resolution, duration, aspect, items, prompt, megapixels=None):
    r = _ratio(aspect, items)
    if megapixels is None:
        area = TIER_AREA.get(resolution, TIER_AREA["480p"])
        W = math.sqrt(area * r)
        H = area / W
    else:
        # ResolutionSelector uses a 1024²-pixel megapixel and a 32-pixel grid.
        W = _r32(math.sqrt(megapixels * 1024**2 * r))
        H = _r32(math.sqrt(megapixels * 1024**2 / r))
    F = _align_up(max(5, round(duration * FPS)))
    R = _grid(int(W), int(H))
    text = max(PROMPT_TOKENS, len(prompt) // 4)
    video, audio = _latent_t(F) * R, 2 * round(F / FPS * 40)
    cond = ref_img = ref_vid = ref_audio = 0
    for it in items:
        a, role = it["asset"], it["role"]
        if role in ("first_frame", "last_frame"):
            cond += R
            text += 8 + R
        elif role == "ref_image" and a.get("width") and a.get("height"):
            s = min(1.0, math.sqrt(W * H / (a["width"] * a["height"])))
            g = _grid(_r32(a["width"] * s), _r32(a["height"] * s))
            ref_img += g
            text += 8 + g
        elif role == "ref_video" and a.get("width") and a.get("height"):
            cw, ch = _canvas(a["width"], a["height"])
            raw = a.get("frame_count") or round((a.get("duration") or 0) * (a.get("fps") or FPS))
            if megapixels is not None and not (a.get("frame_count") or (a.get("fps") and a.get("duration"))):
                # Unknown source rate: the node can consume up to the output frame count.
                raw = F
            if raw < 5:
                continue
            n = _align_down(min(raw, F))
            g = _grid(cw, ch)
            ref_vid += _latent_t(n) * g
            text += 6 + sum((6 if j < 10 else 7) + 2 + g for j in range(math.ceil(math.ceil(n / 12) / 2)))
            if a.get("has_audio"):
                ref_audio += 2 * int((a.get("duration") or 0) * 40)
                text += 5
        elif role == "ref_audio":
            ref_audio += 2 * int((a.get("duration") or 0) * 40)
            text += 5
    S = (text + video + audio + cond + ref_img + ref_vid + ref_audio) / 1000
    group = "-refvid" if ref_vid else "-refimg" if (ref_img or ref_audio) else ""
    return Workload(S, F, W * H, ref_vid, ref_img, group)


class GpuMemory(NamedTuple):
    free: float
    total: float
    reserved: float
    simulated: bool = False


def gpu_memory():
    """Read the GPU selected by Comfy. All values are GiB within the app's quota."""
    try:
        from comfy import model_management as mm
        from torch import cuda
        device = mm.get_torch_device()
        if device.type != "cuda":
            return None
        free, total = cuda.mem_get_info(device)
        reserved = cuda.memory_reserved(device) / 1024**3
        free, total = free / 1024**3, total / 1024**3
        index = device.index if device.index is not None else cuda.current_device()
    except (ImportError, RuntimeError, AttributeError, OSError):
        return None
    if total <= 0 or free < 0 or free > total:
        return None
    limit = re.fullmatch(r"(\d+(?:\.\d+)?)([kmg]?)", os.environ.get(f"CUDA_DEVICE_MEMORY_LIMIT_{index}", "").lower())
    if limit and float(limit[1]) > 0:
        total = min(total, float(limit[1]) / {"": 1024**3, "k": 1024**2, "m": 1024, "g": 1}[limit[2]])
        free = min(free, max(0, total - reserved))
    return GpuMemory(free, total, reserved)


def memory_risk(work, coefficients, items):
    # local-model-bench/minimax-h3/vram-model.json fits sampler activations.
    base, per_1k = coefficients
    activation = base + per_1k * work.tokens_k - 0.00377 * work.ref_video / 1000
    gpu = gpu_memory()
    result = {"activationGiB": round(activation, 1), "freeGiB": None, "level": "unknown"}
    if gpu is None:
        return result
    # For a hard stop, give the engine the benefit of *all* its own reserved
    # memory (caches and potentially offloadable models) and 1 GiB fit error.
    ceiling = min(gpu.total, gpu.free + gpu.reserved)
    measured_frames = all(it["asset"].get("frame_count") for it in items if it["role"] == "ref_video")
    if measured_frames and round(activation * 10) > round(ceiling * 10) + 10:
        level = "blocked"
    elif activation >= 0.9 * min(ceiling, max(0, gpu.total - 1.46)):
        level = "warning"
    else:
        level = "ok"
    return dict(result, freeGiB=round(gpu.free, 1), level=level, simulated=gpu.simulated)


def reference_memory(fits, store, variant, megapixels, params, items, history):
    from .. import media

    for item in items:
        if item["role"] != "ref_video":
            continue
        asset = item["asset"]
        # Older assets and unindexed clips get a frame count on first use.
        if asset.get("frame_count") is None:
            try:
                info = media.probe(asset["path"], count_reference_frames=True)
            except (media.MediaError, OSError):
                continue
            asset.update(frame_count=info.get("frame_count") or 0, fps=info.get("fps") or asset.get("fps"))
            store.update_asset(asset["id"], frame_count=asset["frame_count"], fps=asset["fps"])
    work = workload(params["resolution"], params["duration"], params["aspect"], items, params.get("prompt", ""), megapixels)
    risk = memory_risk(work, fits[variant], items)
    risk["previousOom"] = history is not None and store.previous_oom(*history, variant, params, items)
    if risk["previousOom"] and risk["level"] != "blocked":
        risk["level"] = "warning"
    return risk
