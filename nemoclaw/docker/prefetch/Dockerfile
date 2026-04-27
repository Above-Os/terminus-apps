# Nemoclaw init-prefetch image — contents under /prefetch/ are copied at pod start to
# /workspace/.nemoclaw-prefetch/ on the nemoclaw workspace PVC (see deployment init-prefetch).
# skill-env then installs each known file from /workspace/.nemoclaw-prefetch/ into
# sandbox ~/.local/bin/ when present. Current contents: busybox (provides vi), micro, rg, fd.
# gog (gogcli) is intentionally excluded — installed manually inside the sandbox.
#
# Build (linux/amd64, matches typical sandbox):
#   docker build --platform linux/amd64 -t YOUR_REGISTRY/nemoclaw-prefetch:1 -f docker/prefetch/Dockerfile docker/prefetch
#
# Push:
#   docker push YOUR_REGISTRY/nemoclaw-prefetch:1
#
# Image ref is pinned in templates/deployment.yaml (init-prefetch). Rebuild, push, bump tag there.
#
# Optional: place more files under ./extra/ next to this Dockerfile and uncomment the COPY line.

# NOTE: gog (gogcli) is intentionally NOT prefetched here — it's installed manually
# inside the sandbox (brew install steipete/tap/gog) so the user controls its version
# and auth flow. Re-add a `# --- gog ---` block below if you ever want to bake it in.

# micro editor (static single-binary, modern TUI).
ARG MICRO_VERSION=2.0.13
ARG MICRO_ARCH=linux64-static
# ripgrep: fast grep replacement; musl build is static.
ARG RG_VERSION=14.1.1
ARG RG_TRIPLE=x86_64-unknown-linux-musl
# fd: fast find replacement; musl build is static.
ARG FD_VERSION=10.2.0
ARG FD_TRIPLE=x86_64-unknown-linux-musl

FROM alpine:3.20 AS unpack
ARG MICRO_VERSION
ARG MICRO_ARCH
ARG RG_VERSION
ARG RG_TRIPLE
ARG FD_VERSION
ARG FD_TRIPLE
RUN apk add --no-cache curl ca-certificates tar \
  && mkdir -p /prefetch \
  # --- busybox (provides static `vi`) -----------------------------------
  # The alpine busybox binary is already static; copy it and expose as `vi`.
  # Size ~1.1MB. `busybox vi file` works; skill-env installs a wrapper as `vi`.
  && install -m0755 /bin/busybox /prefetch/busybox \
  # --- micro editor -----------------------------------------------------
  && curl -fsSL -o /tmp/micro.tgz \
       "https://github.com/zyedidia/micro/releases/download/v${MICRO_VERSION}/micro-${MICRO_VERSION}-${MICRO_ARCH}.tar.gz" \
  && tar -xzf /tmp/micro.tgz -C /tmp \
  && m=$(find /tmp -maxdepth 4 -type f -name micro 2>/dev/null | head -1) \
  && test -n "$m" \
  && install -m0755 "$m" /prefetch/micro \
  && test -x /prefetch/micro \
  # --- ripgrep (rg) -----------------------------------------------------
  && curl -fsSL -o /tmp/rg.tgz \
       "https://github.com/BurntSushi/ripgrep/releases/download/${RG_VERSION}/ripgrep-${RG_VERSION}-${RG_TRIPLE}.tar.gz" \
  && tar -xzf /tmp/rg.tgz -C /tmp \
  && rg=$(find /tmp -maxdepth 4 -type f -name rg 2>/dev/null | head -1) \
  && test -n "$rg" \
  && install -m0755 "$rg" /prefetch/rg \
  && test -x /prefetch/rg \
  # --- fd ---------------------------------------------------------------
  && curl -fsSL -o /tmp/fd.tgz \
       "https://github.com/sharkdp/fd/releases/download/v${FD_VERSION}/fd-v${FD_VERSION}-${FD_TRIPLE}.tar.gz" \
  && tar -xzf /tmp/fd.tgz -C /tmp \
  && fd=$(find /tmp -maxdepth 4 -type f -name fd 2>/dev/null | head -1) \
  && test -n "$fd" \
  && install -m0755 "$fd" /prefetch/fd \
  && test -x /prefetch/fd

# Final stage must include sh/cp/chmod: chart init-prefetch runs `sh -c` with cp into the PVC.
# (scratch would make the initContainer fail with "sh: not found".)
FROM busybox:1.36
COPY --from=unpack /prefetch /prefetch
# Multi-stage note: add a prior stage COPY extra/ /prefetch/extra/ then COPY --from=that /prefetch /prefetch here.
