#!/usr/bin/env bash
# Build thin jasl/vLLM SM120 image and push.
# Prefer GitHub Actions (scripts workflow) — local host needs Docker + ~40Gi free RAM.
set -euo pipefail

JASL_REF="${JASL_REF:-9a9c41c0cf4f3f66d3d721f0042fa68ffc2582c1}"
IMAGE_REF="${IMAGE_REF:?set IMAGE_REF e.g. ghcr.io/YOU/vllm-jasl-dsv4:sm120-20260804}"
PLATFORM="${PLATFORM:-linux/amd64}"
MAX_JOBS="${MAX_JOBS:-2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="${ROOT}/scripts/Dockerfile.jasl-sm120-thin"
CTX="${ROOT}/scripts"

echo "Building $IMAGE_REF from jasl/vllm@$JASL_REF (thin Dockerfile)…"
docker buildx build \
  --platform "$PLATFORM" \
  --build-arg "JASL_REF=${JASL_REF}" \
  --build-arg "TORCH_CUDA_ARCH_LIST=12.0" \
  --build-arg "MAX_JOBS=${MAX_JOBS}" \
  -t "$IMAGE_REF" \
  --push \
  -f "$DOCKERFILE" \
  "$CTX"

echo "Pushed $IMAGE_REF"
echo "Point chart engine.images.nvidia / hard-pin to this tag, then upgrade."
