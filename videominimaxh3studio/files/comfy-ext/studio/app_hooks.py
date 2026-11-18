"""Studio hooks for MiniMax H3 (fl2va and ref2va int8): seconds a job takes
on Olares One, from its sequence length.

Port of local-model-bench minimax-h3/vram-calculator.html (98 runs on One,
ComfyUI default memory mode): DiT sampling = c0 + steps * (c1*S + c2*S^2)
with S the sequence length in k tokens, plus prompt/reference encoding and
VAE decode. The coefficients were fitted at 4 steps with the Lightning
LoRA merged in; the quality flows' 20 steps extrapolate per step. The
studio scales it by this install's own history."""

import math

FPS = 24
MAX_PIXELS = 768 * 1344
TIER_AREA = {"480p": 864 * 480, "720p": 1344 * 768}
PROMPT_TOKENS = 400

SAMPLING = {
    "fl2va-int8": (5.105, 0.17296, 0.005956),
    "ref2va-int8": (2.753, 0.17767, 0.0059264),
    "ref2va-int8-refvid": (2.753, 0.18127, 0.0059667),
    "ref2va-int8-refimg": (2.753, 0.18569, 0.0058444),
}
BEFORE = (5.992, 1.4286, 3.0209)  # base, per 1k reference-video tokens, per 1k reference-image tokens
DECODE = (0.02103, 0.06915)  # per frame: d0 + d1 * megapixels
# mode: (model, steps)
MODES = {
    "t2v": ("fl2va", 20), "t2v_fast": ("fl2va", 8),
    "i2v": ("fl2va", 20), "i2v_fast": ("fl2va", 8),
    "omniref": ("ref2va", 20), "omniref_fast": ("ref2va", 4),
}
DEVICES = ("Olares One",)


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


def estimate(mode, variant, resolution, duration, aspect, items, prompt=""):
    area = TIER_AREA.get(resolution, TIER_AREA["480p"])
    r = _ratio(aspect, items)
    W = math.sqrt(area * r)
    H = area / W
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
            raw = round((a.get("duration") or 0) * FPS)
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
    model, steps = MODES.get(mode, MODES["t2v"])
    key = model + "-int8"
    group = "-refvid" if ref_vid else "-refimg" if (ref_img or ref_audio) else ""
    c0, c1, c2 = SAMPLING.get(key + group) or SAMPLING[key]
    sampling = c0 + steps * (c1 * S + c2 * S * S)
    before = BEFORE[0] + BEFORE[1] * ref_vid / 1000 + BEFORE[2] * ref_img / 1000
    decode = F * (DECODE[0] + DECODE[1] * W * H / 1e6)
    return sampling + before + decode
