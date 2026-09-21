# jinaclipv2embed

Olares app for [beclab/jina-clip-v2-split](https://huggingface.co/beclab/jina-clip-v2-split)
served by [IREmbeddingServer](https://github.com/beclab/IREmbeddingServer) via llm-init `ENGINE_KIND=clipembed`.

Replaces the legacy `jinaclipv2` stack (custom images + `/api/text/embed`). This app follows the same pattern as `embeddinggemmav3` and is aligned with `integration_test_clipembed.sh`.

## Workloads

| Deployment | Role |
|------------|------|
| `{{ Release.Name }}` (= `jinaclipv2embed`) | embed-server engine（内部 `http://clipembed:8080`） |
| `llminit` | llm-init（`ENGINE_KIND=clipembed`）：下载 + API 代理（8090） |

## API 路径

| 入口 | 目标 | 说明 |
|------|------|------|
| clipclient / clipapi / shared entrance | `download-svc:8090` | llm-init 代理 `/v1/embeddings` 等到 embed-server |
| 集群内直连引擎 | `embedserver:8080` 或 `clipembed:8080` | 仅内部/debug；外部应走 llm-init |

OpenAI-compatible endpoints:

- `POST /v1/embeddings` — text (`input` string) or image (`input` object + base64 data URL)
- `GET /v1/models` — model id `jina-clip-v2`

## Accelerator → image mapping

| Mode | Docker image | `MODEL_ID` | `ACCELERATOR` | HF subdir |
|------|--------------|------------|----------------|-----------|
| `intel` | `beclab/embed-server:v0.2.1-ov-intel` | `jina-clip-v2-split` | `intel` | `openvino/` |
| `intel-gpu` | `beclab/embed-server:v0.2.1-ov-intel` | `jina-clip-v2-split` | `intel-gpu` | `openvino/` |
| `cpu` | `beclab/embed-server:v0.2.1-onnx-cpu` | `jina-clip-v2-split` | `cpu` | `onnx/` |
| `nvidia` | `beclab/embed-server:v0.2.1-onnx-cuda12` or `*-cuda13` | `jina-clip-v2-split` | `nvidia` | `onnx/` |
| `nvidia-gb10` | `beclab/embed-server:v0.2.1-onnx-cuda13-gb10-arm64` | `jina-clip-v2-split` | `nvidia-gb10` | `onnx/` |

## Model source (llm-init)

Unified repo: https://huggingface.co/beclab/jina-clip-v2-split

- Intel 核显/独显: `hf://beclab/jina-clip-v2-split --revision main --exclude onnx/** --subdir openvino`
- Others: `hf://beclab/jina-clip-v2-split --revision main --exclude openvino/** --subdir onnx`

`MODEL_NAME=jina-clip-v2` (logical id for `/v1/models` and proxy rewrite).

## Images

| Component | Image |
|-----------|-------|
| embed-server | `beclab/embed-server:v0.2.1-*` |
| llm-init | `beclab/llm-init:v1.7.21` |

## Device mounts

- **intel / intel-gpu:** `/dev/dri`, `/sys/class/drm` (+ privileged)
- **nvidia / nvidia-gb10:** Olares `gpu-inject` annotation

## Local integration test

```bash
bash /var/wangzhong/local-dev/llminit/integration_test_clipembed.sh
```

Uses the same `MODEL_SOURCE` / `MODEL_ID` / `ENGINE_KIND=clipembed` defaults as this chart.

## Resource profiling

```bash
bash /var/wangzhong/local-dev/llminit/integration_test_clipembed_resources.sh
```

Measured peaks (2026-08-10): see  
[`/var/wangzhong/local-dev/llminit/clipembed_resource_reports/Jina-CLIP-v2-资源画像.md`](/var/wangzhong/local-dev/llminit/clipembed_resource_reports/Jina-CLIP-v2-资源画像.md).

Summary: embed-server RAM ~**2.8 GiB** (OpenVINO) / ~**2.2 GiB** host RAM (NVIDIA steady); VRAM ~**9589 MiB**. Chart uses **3Gi/6Gi** pod memory and **`nvidia.com/gpumem: 10240`** on `nvidia`; **`nvidia-gb10`** uses unified memory (**10Gi/14Gi** embed-server, OlaresManifest **12Gi/16Gi**, no standalone GPU fields).

## Verify runtime device

```bash
curl -s http://<pod>:8080/v1/capabilities | jq '{configured_device_kind, inference_backend, cpu_fallback}'
```

## v0.2.1 migration (Chart 1.0.15)

Engine configuration uses `MODEL_ID=jina-clip-v2-split` on every backend and
`ACCELERATOR` from the Olares compute selection. Do not pass `EMBED_DEVICE` or
legacy suffixed model IDs to the new engine. The public API model name remains
`jina-clip-v2`. Backend assets are selected from the matching `openvino/` or
`onnx/` subdirectory; no extra format environment variable is required.

`intel` requires an integrated Intel GPU; `intel-gpu` requires a discrete Intel
GPU. They do not fall back to the other GPU type or CPU. The discrete mode uses
Olares GPU injection and 10240Mi / 12288Mi allocation annotations, matching its
manifest. This is an initial allocation, not a measured Intel dGPU peak guarantee.
The existing Jina host-memory and NVIDIA/GB10 budgets are preserved; Gemma's
smaller budgets are not suitable evidence for this dual-tower model.

`ENGINE_KIND=clipembed`, the `clipembed` service alias, `MODEL_SUPPORTS` image
capability, entrances, cache and run-state paths are preserved. Upgrade image and
configuration together; roll both back together if necessary. Local lint and
render checks do not prove model loading on physical hardware. Validate both text
and image inference via llm-init on each target before declaring deployment tested.
