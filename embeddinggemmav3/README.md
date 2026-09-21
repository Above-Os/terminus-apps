# embeddinggemmav3

Olares app for [google/embeddinggemma-300m](https://huggingface.co/google/embeddinggemma-300m)
served by [IREmbeddingServer](https://github.com/beclab/IREmbeddingServer).

## Workloads

| Deployment | Role |
|------------|------|
| `{{ Release.Name }}` (= `embeddinggemmav3`) | embed-server engine（内部 `http://embed:8080`） |
| `llminit` | llm-init（`ENGINE_KIND=embed`）：下载 + API 代理（8090） |

## API 路径

| 入口 | 目标 | 说明 |
|------|------|------|
| embedclient / embedapi / shared entrance | `download-svc:8090` | llm-init 代理 `/v1/embeddings` 等到 embed-server |
| 集群内直连引擎 | `embedserver:8080` 或 `embed:8080` | 仅内部/debug；外部应走 llm-init |

## Accelerator → image mapping

| Mode | Docker image | `MODEL_ID` | `ACCELERATOR` | HF subdir |
|------|--------------|------------|----------------|-----------|
| `intel` | `beclab/embed-server:hw-bfaa3cc-ov-intel` | `embeddinggemma-300m` | `intel` | `openvino/` |
| `intel-gpu` | `beclab/embed-server:hw-bfaa3cc-ov-intel` | `embeddinggemma-300m` | `intel-gpu` | `openvino/` |
| `cpu` | `beclab/embed-server:hw-bfaa3cc-onnx-cpu` | `embeddinggemma-300m` | `cpu` | `onnx/` |
| `nvidia` | `beclab/embed-server:hw-bfaa3cc-onnx-cuda12` or `*-cuda13` | `embeddinggemma-300m` | `nvidia` | `onnx/` |
| `nvidia-gb10` | `beclab/embed-server:hw-bfaa3cc-onnx-cuda13-gb10-arm64` | `embeddinggemma-300m` | `nvidia-gb10` | `onnx/` |

## Model source (llm-init)

Unified repo: https://huggingface.co/beclab/embeddinggemma-300m

- Intel: `hf://beclab/embeddinggemma-300m --revision main --exclude onnx/** --subdir openvino`
- Others: `hf://beclab/embeddinggemma-300m --revision main --exclude openvino/** --subdir onnx`

## Images

| Component | Image |
|-----------|-------|
| embed-server | `beclab/embed-server:hw-bfaa3cc-*` |
| llm-init | `beclab/llm-init:v1.3.5` |

## Device mounts

- **intel:** `/dev/dri`, `/sys/class/drm` (+ privileged)
- **nvidia / nvidia-gb10:** Olares `gpu-inject` annotation

## Verify runtime device

```bash
curl -s http://<pod>:8080/v1/capabilities | jq '{configured_device_kind, inference_backend, cpu_fallback}'
```

## Upgrade notes

See [UPGRADE-hw-bfaa3cc.md](./UPGRADE-hw-bfaa3cc.md).

## Hardware contract migration (candidate)

Engine candidate `hw-bfaa3cc` is paired with chart 1.1.5. This is a coordinated
image/configuration migration: roll back both together. `ACCELERATOR` is mandatory,
old `EMBED_DEVICE` / `EMBED_ALLOW_CPU_FALLBACK` settings and suffixed deployment IDs
are rejected. Intel modes require the matching integrated/discrete device; they do
not fall back to another type or CPU. Both download OpenVINO assets. Other modes
use ONNX assets. Lower-case `gpu` overrides `GPU.Type`; unknown values fail rendering.

Intel discrete mode uses GPU injection and 2048Mi required / 4096Mi limited GPU
memory annotations. These are allocation settings, not a measured peak guarantee.
HF cache and run-state paths are unchanged. llm-init remains v1.7.21.

Release gate: the current candidate images were built for amd64. ARM64 CPU/CUDA
and GB10 candidate artifacts have not been built/validated in this run; do not
publish this candidate as an all-architecture release. Registry push and remote
Olares acceptance must pass before rollout. Local lint/render success alone does
not demonstrate that a device, image download, or model load works.
