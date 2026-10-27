# 15Gi GPU memory and a 12Gi static pool — 1.0.5

The NVIDIA reservation rises from 13824Mi (13.5Gi) to 15360Mi (15Gi), and the
launch wrapper's static-pool cap from `min(0.80, 11Gi / visible)` to
`min(0.80, 12Gi / visible)`. On a 15Gi slice that is the full 80%, 12Gi, against
10.8Gi before; raising the reservation alone would have left the pool at 11Gi.
The cap lives in `templates/wrappers.yaml` (`prepare.py`), which an upgrade
applies, unlike a saved `ENGINE_ARGS`. Time-sliced installations, which see the
whole card, get 12Gi instead of 11Gi.

The companion charts free the memory on the same card: audioqwen3asr06v3 1.0.3
(3.5Gi → 2.3Gi) and audioqwen3ttsv3 1.0.12 (6Gi → 5.7Gi). The three still add up
to 23Gi.

## Why

Measured on pptest03 (RTX 5090 Laptop, 24Gi, memory slicing) with 1.0.4:

- SGLang allocates `max_mamba_cache_size: 19` (conv 0.02GB, ssm 0.94GB) beside
  1.12GB of FP8 KV, and logs `mamba usage: 0.21` at rest: about four slots hold
  cached prefixes while each running request takes five.
- A 15.5k-token prompt sent again after N other prompts of about 4k tokens:

  | Other prompts in between | Second request | Prefix |
  | --- | --- | --- |
  | 0–2 | 0.11–0.28 s | cached |
  | 3 | 3.15 s | re-read |
  | 6 | 3.34 s | re-read |

- In a Lares voice session the Agent's first call of a turn reused 11–13k of a
  22k-token prompt (`#cached-token`) and re-read the rest, adding 2–6 s, although
  the request matched the previous one byte for byte up to its new messages
  (Lares `agent-request` trace). The dialogue's own calls in between were enough
  to evict the Agent's state.

Peak use over three hours on that card: ASR 2.04Gi of 3.5Gi, TTS 5.23Gi of 6Gi,
SGLang 13.08Gi of 13.5Gi.

## Local checks

- `olares-cli chart lint`: passed under both owner installation scenarios,
  including the Helm dry-run render.
- No upgrade note before 1.0.5 was changed; only current descriptions and
  defaults now say 15Gi / 12Gi.

## To check after upgrading pptest03

- The SGLang pod requests `nvidia.com/gpumem` 15360 and logs
  `visible GPU total≈15Gi, static fraction=0.80000` and a larger
  `max_mamba_cache_size`.
- `SGLANG_REQUIRED_GPU_MEMORY` is not editable; confirm an upgraded installation
  takes the new default rather than keeping 13824Mi.
- The same prefix probe and the weather → light → light-off voice sequence:
  how many other prompts the Agent's prefix now survives.
