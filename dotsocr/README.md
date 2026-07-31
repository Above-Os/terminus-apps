# dotsocr — Olares App

dots.ocr（[ggml-org/dots.ocr-GGUF](https://huggingface.co/ggml-org/dots.ocr-GGUF) **Q8**）文档 OCR 应用。

参考：[`embeddinggemmav3`](../embeddinggemmav3)（llm-init 双 Deployment 模式）+ llm-init [`deploy/compose/ocr.yml`](../../../llm-init/deploy/compose/ocr.yml) 拓扑。

## 拓扑

```
Client / LLM Gateway
        │
        ▼
  llm-init :8090          ENGINE_KIND=ocr  MODEL_MODE=ocr
  (download-svc)          代理 → http://ocradapter:8080
        │
        ▼
  ocradapter :8080        pipeline=dots
        │                 REDIS_URL ← Olares middleware Redis（非 chart 内 redis 容器）
        ▼
  llamacpp :8081          CUDA + Q8 GGUF + mmproj
```

Service 名必须固定：`ocradapter`、`llamacpp`（与 llm-init / OCRAdapter 约定一致）。

## 只下载 Q8

`MODEL_SOURCE` 默认：

```text
hf://ggml-org/dots.ocr-GGUF --include dots.ocr-Q8_0.gguf --include mmproj-dots.ocr-Q8_0.gguf
```

两个 `--include` 时 llm-init **不会**整仓拉取，同仓库的 F16（`dots.ocr-f16.gguf` / `mmproj-dots.ocr-f16.gguf`）会跳过。见 [model-source.md](https://github.com/beclab/llm-init/blob/main/docs/model-source.md)。

HF 镜像用部署级 `HF_ENDPOINT`（Olares `OLARES_SYSTEM_HUGGINGFACE_SERVICE`），不要写进 `MODEL_SOURCE`。

## 加速器

**仅 CUDA**：`accelerator` 声明 `nvidia` / `nvidia-gb10`。模板在 `cpu` / `intel` 下 `fail`。

资源参考本地画像（Q8 峰显存 ~9.1 GiB）：

| 项 | 默认 |
|----|------|
| `requiredGPUMemory` | 11Gi |
| llamacpp CPU request | 1500m |
| llamacpp memory request | 1Gi |

## Redis

`OlaresManifest`：

```yaml
middleware:
  redis:
    namespace: dotsocr
```

OCRAdapter：`REDIS_URL=redis://[:password@]host:port/0`（来自 `.Values.redis`）。

## 目录

```
dotsocr/
├── Chart.yaml
├── OlaresManifest.yaml
├── README.md
├── owners
├── values.yaml
├── i18n/{en-US,zh-CN}/OlaresManifest.yaml
└── templates/
    ├── _helpers.tpl
    ├── llm-init.yaml
    ├── ocradapter.yaml
    ├── llamacpp.yaml
    ├── wrappers.yaml
    └── secret.yaml
```

## 镜像

| 组件 | 镜像 |
|------|------|
| llm-init | `beclab/llm-init:v1.3.2` |
| OCRAdapter | `beclab/ocr-adapter:latest` |
| llama.cpp | `beclab/ggml-org-llama.cpp:server-cuda12-b10143` |

## 分析与待拍板

见 [`/var/wangzhong/local-dev/terminus-apps-docs/dotsocr/分析-待拍板.md`](/var/wangzhong/local-dev/terminus-apps-docs/dotsocr/分析-待拍板.md)（问题清单 + Q1–Q12）。

