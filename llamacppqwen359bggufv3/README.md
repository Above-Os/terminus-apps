# Qwen3.5-9B Q4_K_M Vision

NVIDIA amd64 only. The chart retains the Model Console / llama.cpp base layout, shared Hugging Face cache and same-node run-state affinity.

The default is `-c 262144 -np 4 -kvu --kv-unified-per-slot 131072`: four slots dynamically share a total 262144-token KV pool. Each request is capped at 131072 tokens and may use available capacity, while aggregate input and output budgets must fit the pool. Model Console checks shared-pool admission; oversubscribed requests receive a clear capacity error. This does not reserve 256K for each slot. Windows include template, image, input and output tokens. Q8 KV, GPU projector, and 1024-token image budget are retained in both modes.

## Reproducibility

Model revision: `3885219b6810b007914f3a7950a8d1b469d598a5`.

| File | SHA256 |
|---|---|
| Qwen3.5-9B-Q4_K_M.gguf | 03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8 |
| mmproj-F16.gguf | f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f |

The CUDA image digest is pinned in values.yaml. Model Console uses `beclab/llm-init:v1.7.21` for shared-pool admission accounting. Explicit `-m` and `--mmproj` paths point to the pinned downloaded snapshot; this avoids depending on llama.cpp's separate HF lookup.

## Capacity evidence

The earlier fixed-partition 4x64K and 2x128K modes passed three rounds with all slots concurrently processing near-full-window retrieval prompts, followed by distinct-image OCR and queue/cancel/over-window checks. Text inputs were 63721 tokens per slot for 4x64K and 129055 tokens per slot for 2x128K, reserving at least 1024 output tokens.

The highest sampled GPU usage was 11857 MiB and 11820 MiB respectively, on an RTX 5090 Laptop with a 12288 MiB HAMi quota. These are quota results on a physical 24GB GPU. No separate 30-minute soak was run for these expanded modes; do not infer sustained-load certification from the capacity checks. Image recognition remains fallible.
