"""Studio hooks for MiniMax H3 (fl2va and ref2va int8): seconds a job takes
on Olares One, from its sequence length.

Port of local-model-bench minimax-h3/vram-calculator.html (98 runs on One,
ComfyUI default memory mode): DiT sampling = c0 + steps * (c1*S + c2*S^2)
with S the sequence length in k tokens, plus prompt/reference encoding and
VAE decode. The coefficients were fitted at 4 steps with the Lightning
LoRA merged in; the quality flows' 20 steps extrapolate per step. The
studio scales it by this install's own history."""

from functools import partial

from .hooklib import h3_estimator as h3

reference_memory = partial(h3.reference_memory, {"": (0.0005, 0.10179)})

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


def estimate(mode, variant, resolution, duration, aspect, items, prompt=""):
    work = h3.workload(resolution, duration, aspect, items, prompt)
    S = work.tokens_k
    model, steps = MODES.get(mode, MODES["t2v"])
    key = model + "-int8"
    c0, c1, c2 = SAMPLING.get(key + work.group) or SAMPLING[key]
    sampling = c0 + steps * (c1 * S + c2 * S * S)
    before = BEFORE[0] + BEFORE[1] * work.ref_video / 1000 + BEFORE[2] * work.ref_image / 1000
    decode = work.frames * (DECODE[0] + DECODE[1] * work.pixels / 1e6)
    return sampling + before + decode
