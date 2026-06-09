# llama.cpp LLM Base (llamacppllmbasev3)

通用 **llama.cpp + llm-init** 基座，结构与 `vllmllmbasev3` / `sglangllmbasev3` 平行，
但引擎换成 llama.cpp、模型格式换成 **GGUF**。

- **引擎镜像**: `beclab/ggml-org-llama.cpp:server-cuda12-b9426`（GPU / CUDA 12）
- **llm-init**: `beclab/llm-init:v1.2.1`
- **版本**: chart `1.0.0` / appVersion `b9426`

## 架构

| 组件 | Deployment | 端口 | 作用 |
|---|---|---|---|
| **llm-init** | `llamacppllmbasev3` | 8090 | GGUF 下载、sentinel、`/v1/*` 代理、`http://llamacpp:8081` |
| **llama.cpp** | `llamacpp` | 8081 | GGUF 推理（Service 名必须为 `llamacpp`） |

- HF/GGUF 缓存：`appCommon/huggingface` → `/cache/hf/hub`（共享）
- sentinel：`appCache/llm-init-run/<release>` → `/run/llm-init`（按实例隔离）

## 与 vLLM / SGLang 的关键区别

| 项 | vLLM / SGLang | llama.cpp |
|---|---|---|
| 模型格式 | 完整 HF safetensors | **GGUF** |
| MODEL_SOURCE | `hf://<repo>` | `hf://<repo> --include <file>.gguf`（llm-init 下载） |
| MODEL_NAME | API 模型名 / `--model` | **`owner/repo:quant`** → `llama-server -hf` |
| 量化 | AWQ/GPTQ/FP8 | GGUF 内置量化（Q4_K_M 等） |
| GPU 卸载 | 默认全在 GPU | 需 `-ngl all` 显式卸载，否则跑 CPU |

## 安装示例

### 示例 A：GPU（推荐，全量卸载）

```bash
MODEL_SOURCE=hf://unsloth/Qwen3-0.6B-GGUF --include Qwen3-0.6B-Q4_K_M.gguf
MODEL_NAME=unsloth/Qwen3-0.6B-GGUF:Q4_K_M
MODEL_MODE=chat
MODEL_SUPPORTS=
ENGINE_ARGS=-c 8192 -ngl all -fa on
LOG_LEVEL=info
LLAMACPP_CPU_REQUEST=200m
LLAMACPP_MEMORY_REQUEST=2Gi
LLAMACPP_CPU_LIMIT=6
LLAMACPP_MEMORY_LIMIT=35Gi
```

### 示例 B：大模型部分卸载（显存不够时）

> 显存放不下整模型时，用 `-ngl <N>` 只卸载前 N 层到 GPU，其余留 CPU；
> 同时调高 CPU/内存上限。

```bash
MODEL_SOURCE=hf://unsloth/Qwen3-8B-GGUF --include Qwen3-8B-Q4_K_M.gguf
MODEL_NAME=unsloth/Qwen3-8B-GGUF:Q4_K_M
MODEL_MODE=chat
ENGINE_ARGS=-c 16384 -ngl 24 -fa on
LOG_LEVEL=info
LLAMACPP_CPU_REQUEST=1
LLAMACPP_MEMORY_REQUEST=4Gi
LLAMACPP_CPU_LIMIT=8
LLAMACPP_MEMORY_LIMIT=24Gi
```

## ENGINE_ARGS 常用项（llama.cpp 语法）

| flag | 作用 | 说明 |
|---|---|---|
| `-c` | 上下文长度（token） | `-c 8192` |
| `-ngl` | 卸载到 GPU 的层数 | `-ngl all` = 全量；省略 = CPU |
| `-fa on` | Flash Attention | 省显存/提速 |
| `-t` | CPU 线程数 | CPU 推理时调 |
| `--parallel` | 并发请求 slot 数 | `--parallel 4` |

也支持 `LLAMA_ARG_*=val` 形式（如 `LLAMA_ARG_CTX_SIZE=8192`），wrapper 自动路由。

`-hf` / `--alias` / `--host` / `--port` 由 wrapper 设置（`-hf` 来自 `MODEL_NAME`），勿在 ENGINE_ARGS 重复。

## 调用验证

```bash
curl -s http://sharedentrances-api.<namespace>:80/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-0.6b","messages":[{"role":"user","content":"hi"}]}'
```
