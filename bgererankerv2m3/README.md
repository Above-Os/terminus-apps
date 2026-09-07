# bgererankerv2m3

Olares app for [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
served by [rerank-server](https://github.com/beclab/rerank) + llm-init (`ENGINE_KIND=rerank`).

Resource sizing from `/var/wangzhong/local-dev/llminit/rerank_resource_reports/rerank-resource-report-20260907.md`.

## Workloads

| Deployment | Role |
|------------|------|
| `{{ Release.Name }}` (= `bgererankerv2m3`) | rerank-server engine（内部 `http://rerank:8080`） |
| `llminit` | llm-init（`ENGINE_KIND=rerank`）：下载 + API 代理（8090） |

## API 路径

| 入口 | 目标 | 说明 |
|------|------|------|
| rerankclient / rerankapi / shared entrance | `download-svc:8090` | llm-init 代理 `/v1/rerank`、`/v1/models` 等到 rerank-server |
| 集群内直连引擎 | `rerankserver:8080` 或 `rerank:8080` | 仅内部/debug；外部应走 llm-init |

## Accelerator → image mapping

| Mode | Docker image | `ACCELERATOR` | `RERANK_RUNTIME` | HF subdir |
|------|--------------|---------------|------------------|-----------|
| `intel` | `beclab/rerank-server:v0.1.0-ov-intel-amd64` | `intel-gpu` | `openvino` | `openvino/` |
| `cpu` | `beclab/rerank-server:v0.1.0-onnx-cpu` | `cpu` | `onnx` | `onnx/` |
| `nvidia` | `beclab/rerank-server:v0.1.0-onnx-cuda12` or `*-cuda13` | `nvidia` | `onnx` | `onnx/` |
| `nvidia-gb10` | `beclab/rerank-server:v0.1.0-onnx-cuda13-gb10-arm64` | `nvidia-gb10` | `onnx` | `onnx/` |

## Naming contract

- llm-init: `MODEL_NAME` = `MODEL_ID` = `bge-reranker-v2-m3`
- rerank-server: `MODEL_ID` only

## Model source (llm-init)

Unified repo: https://huggingface.co/beclab/bge-reranker-v2-m3

- Intel: `hf://beclab/bge-reranker-v2-m3 --revision main --exclude onnx/** --subdir openvino`
- Others: `hf://beclab/bge-reranker-v2-m3 --revision main --exclude openvino/** --subdir onnx`

## Images

| Component | Image |
|-----------|-------|
| rerank-server | `beclab/rerank-server:v0.1.0-*` |
| llm-init | `beclab/llm-init:v1.7.1` |

## Resource profile (steady-state inference)

| Mode | Engine RAM | GPU VRAM | CPU (inference) |
|------|------------|----------|-----------------|
| cpu | ~1.4 GiB | — | ~1 core |
| nvidia | ~0.7 GiB | ~3.2 GiB | low |
| intel | ~0.75 GiB* | iGPU shared | low* |

\*OpenVINO compile may spike RAM ~3.2 GiB and CPU ~2.7 cores on first start.

## Device mounts

- **intel:** `/dev/dri`, `/sys/class/drm` (+ privileged)
- **nvidia / nvidia-gb10:** Olares `gpu-inject` annotation

## Smoke test

```bash
curl -s http://<llm-init>:8090/v1/models
curl -s http://<llm-init>:8090/v1/rerank \
  -H 'Content-Type: application/json' \
  -d '{"model":"bge-reranker-v2-m3","query":"what is a panda?","documents":["the giant panda lives in China","quantum computing"]}'
```
