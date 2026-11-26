"""Studio hooks for MiniMax H3: seconds a job takes on Olares One, from its
sequence length.

Port of local-model-bench minimax-h3/vram-calculator.html (98 runs on One,
ComfyUI default memory mode): DiT sampling = c0 + steps * (c1*S + c2*S^2)
with S the sequence length in k tokens, plus prompt/reference encoding and
VAE decode. The studio scales it by this install's own history."""

from functools import partial

from .hooklib import h3_estimator as h3

reference_memory = partial(h3.reference_memory, {"int8": (0.0068, 0.10290), "nvfp4": (0.0380, 0.13294)})

STEPS = 8

SAMPLING = {
    "fasth3-int8": (3.11, 0.21742, 0.002237),
    "fasth3-nvfp4": (6.736, 0.12674, 0.0027539),
    "omniref-int8": (4.967, 0.22837, 0.0010002),
    "omniref-int8-refvid": (4.967, 0.55805, 0.0024062),
    "omniref-int8-refimg": (4.967, 0.23122, 0.0028675),
    "omniref-nvfp4": (7.677, 0.13128, 0.0015519),
    "omniref-nvfp4-refvid": (7.677, 0.45017, 0.0030214),
    "omniref-nvfp4-refimg": (7.677, 0.1254, 0.0036886),
}
BEFORE = (5.992, 1.4286, 3.0209)  # base, per 1k reference-video tokens, per 1k reference-image tokens
DECODE = (0.02103, 0.06915)  # per frame: d0 + d1 * megapixels
MODE_MODEL = {"t2v": "fasth3", "i2v": "fasth3", "omniref": "omniref"}
DEVICES = ("Olares One",)


def estimate(mode, variant, resolution, duration, aspect, items, prompt=""):
    work = h3.workload(resolution, duration, aspect, items, prompt)
    S = work.tokens_k
    key = "%s-%s" % (MODE_MODEL.get(mode, "fasth3"), variant)
    c0, c1, c2 = SAMPLING.get(key + work.group) or SAMPLING.get(key) or SAMPLING["fasth3-nvfp4"]
    sampling = c0 + STEPS * (c1 * S + c2 * S * S)
    before = BEFORE[0] + BEFORE[1] * work.ref_video / 1000 + BEFORE[2] * work.ref_image / 1000
    decode = work.frames * (DECODE[0] + DECODE[1] * work.pixels / 1e6)
    return sampling + before + decode
