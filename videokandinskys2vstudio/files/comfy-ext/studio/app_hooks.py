"""Studio hooks for Kandinsky S2V: seconds a job takes on Olares One.

The speech is padded to whole 5 s chunks (ceil(seconds / 5), no tolerance:
10.01 s is three chunks) and every chunk is sampled with 16 steps and
decoded, so time is a fixed part plus a per-chunk part. Fitted on One at
768x512 (HAMi time slicing, models unloaded between jobs): Lite at 2, 6 and
12 chunks (283, 828 and 1649 s), Pro at 3 chunks (2182-2189 s); Pro's
per-chunk cost is taken as constant, as it is for both models on the
RTX PRO 6000 up to 12 chunks (local-model-bench kandinsky-s2v). 512x512
portraits have two thirds of the tokens per frame and are scaled by that,
not measured. The studio scales the result by this install's own history."""

import math

DEVICES = ("Olares One",)
CHUNK_SECONDS = 5.0
# variant -> (fixed seconds, seconds per chunk)
COST = {"lite": (9.4, 136.6), "pro": (6.0, 727.0)}
BUCKETS = ((512, 512), (768, 512), (512, 768))  # (height, width)


def _area_scale(items):
    for it in items:
        a = it["asset"]
        if it["role"] == "ref_image" and a.get("width") and a.get("height"):
            r = a["width"] / a["height"]
            h, w = min(BUCKETS, key=lambda b: abs(r - b[1] / b[0]))
            return h * w / (768 * 512)
    return 1.0


def estimate(mode, variant, resolution, duration, aspect, items, prompt=""):
    row = COST.get(variant)
    seconds = next((it["asset"].get("duration") for it in items if it["role"] == "ref_audio"), None)
    if row is None or not seconds:
        return None
    fixed, per_chunk = row
    return fixed + max(1, math.ceil(seconds / CHUNK_SECONDS)) * per_chunk * _area_scale(items)
