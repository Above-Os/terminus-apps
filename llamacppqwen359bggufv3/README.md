# Qwen3.5-9B Q4_K_M Vision

NVIDIA amd64 only. The chart retains the Model Console / llama.cpp base layout, shared Hugging Face cache and same-node run-state affinity.

The default is `-c 262144 -np 4 -kvu --kv-unified-per-slot 131072`: four slots dynamically share a total 262144-token KV pool. Each request is capped at 131072 tokens and may use available capacity, while aggregate input and output budgets must fit the pool. Model Console checks shared-pool admission; oversubscribed requests receive a clear capacity error. This does not reserve 256K for each slot. Windows include template, image, input and output tokens. Q8 KV, GPU projector, and a 1024-token image budget are retained.

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

## Shared-pool validation

The submitted preset (`-c 262144 -np 4 -kvu --kv-unified-per-slot 131072`, llm-init v1.7.21) was tested without restarting between workloads:

| Workload | Actual text input tokens per request | Checks | Observed TTFT |
|---|---|---|---|
| Four concurrent near-64K retrieval requests | 63721 | 4/4 | 16.97–141.15 s |
| Two concurrent near-128K retrieval requests | 129055 | 2/2 | 104.46–206.67 s |
| Four concurrent long-text requests with different 2560x960 digit images | Within 64K including image and output budget | 8/8 retrieval and OCR | See raw test measurements |

Each retrieval prompt contains distinct facts at the beginning, middle and end, and checks for cross-request contamination. Each request reserves at least 1024 output tokens. These UKV capacity cases were each run once; the three-round fixed-slot results above are separate measurements.

Highest sampled shared-pool GPU usage was 12049 MiB (239 MiB below the 12288 MiB quota). Processes remained unchanged during these checks. The shared-pool configuration has longer observed TTFT than the earlier fixed-slot presets; flexibility does not imply a throughput improvement. No 30-minute UKV soak has been completed.

Pool-admission testing submitted three near-128K requests simultaneously: two completed and one returned explicit `kv_budget_exhausted`, followed by a successful recovery request. Over-window rejection, fifth-request queueing, cancellation through Model Console, slot release and subsequent generation also passed. No process restart occurred during these scenarios.
