# Image provenance and reproduction

Upstream: https://github.com/JustVugg/colibri

Source commit: `0a5504a1dc64f86fcd0fe7db298b0448c730e7e6` (2.1.0), Apache-2.0.

Image: `harveyff/colibri:2.1.0-0a5504a-cuda128-olares2`

Digest: `sha256:90607d8704047c20a5038ee181d18e1fb70310e846316ca56bbc10aaf021b9f4`

The CUDA 12.8 build targets sm_120 on linux/amd64 with x86-64-v3 CPU instructions. This is not an older-GPU or ARM64 build. `COLI_CUDA=0` selects the CPU fallback.

Apply dashboard.patch to the pinned upstream checkout, then build from that checkout using this Dockerfile. The patch adds Olares browser authentication behavior and the optional same-origin Router connection; it contains no credentials.

```sh
git clone https://github.com/JustVugg/colibri.git upstream
git -C upstream checkout 0a5504a1dc64f86fcd0fe7db298b0448c730e7e6
git -C upstream apply /path/to/colibri/build/dashboard.patch
docker build --platform linux/amd64 -f /path/to/colibri/build/Dockerfile -t harveyff/colibri:2.1.0-0a5504a-cuda128-olares2 upstream
```

The image retains the upstream LICENSE, NOTICE and third-party notices. The chart uses read-only shared model weights, an application data directory for imported metadata, and a generated server-side API key. No model weights are distributed with the chart or image.
