# embeddinggemma2

Olares application for `onnx-community/embeddinggemma-2-ONNX`, served by IREmbeddingServer through model-console.

## Runtime contract

- `ENGINE_KIND=multimodalembed`; model-console proxies to `multimodalembed:8080`.
- The model revision is pinned to `daa72c51243991dfcaf9f9137d2c573d8f7790c0` and downloads the fusion, vision, and audio ONNX graphs plus their external data.
- Text and image use `POST /v1/embeddings`.
- Audio, video, and ordered text/media input use `POST /v1/embedding-tasks` and `/v1/tasks/{id}` lifecycle routes.
- `/var/lib/irembed/tasks` is backed by appData and prepared for UID/GID 1000.
- Hugging Face artifacts use the shared appCommon cache.

## Pinned images

| Component | Image |
|---|---|
| embed-server | `beclab/embed-server:embeddinggemma2-bdd5717-onnx-cpu` |
| llm-init | `beclab/llm-init:embeddinggemma2-cabe786` |

Both images are published for amd64 and arm64. The initial chart exposes CPU mode only because that is the implemented and validated EmbeddingGemma 2 execution provider.
