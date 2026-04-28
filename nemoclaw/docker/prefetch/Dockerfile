# Nemoclaw init-prefetch image — contents under /prefetch/ are copied at pod start to
# /workspace/.nemoclaw-prefetch/ on the nemoclaw workspace PVC (see deployment init-prefetch).
# skill-env then installs each known artifact from /workspace/.nemoclaw-prefetch/ into
# the sandbox. Current contents:
#   busybox, micro, rg, fd          -> sandbox ~/.local/bin/<name>     (single-file static)
#   homebrew.tar.gz                 -> sandbox /sandbox/.linuxbrew/Homebrew (Homebrew tree
#                                     with portable-ruby pre-vendored, no ghcr.io fetch needed)
#
# Why ship Homebrew prebuilt: a fresh sandbox previously had to (1) git clone Homebrew/brew,
# (2) `brew vendor-install ruby` which fetches portable-ruby from ghcr.io as an OCI blob,
# and (3) source-build any formula the user installs. Step (2) routes through the OpenShell
# egress proxy and ghcr.io's anti-abuse layer 403s anonymous OCI blob requests
# unpredictably, which used to stall every cold boot. Baking a ready-to-use Homebrew tree
# (~70MB compressed) eliminates steps (1) and (2). Source compilation (3) still happens at
# install time but only needs gcc, which the chart's skill-env apt-installs in-sandbox.
#
# gog (gogcli) is intentionally NOT shipped in this image. Operators install it
# in-sandbox via `openclaw config --section skills` -> brew install steipete/tap/gog
# so the version, auth flow, and OAuth callback host stay under their control. Pairs
# with the disabled gog-prefetch block in templates/configmap-sandbox-bridge.yaml.
#
# Build (linux/amd64, matches typical sandbox):
#   docker build --platform linux/amd64 \
#     -t beclab/harveyff-nemoclaw-prefetch:2026.4.27 \
#     -f docker/prefetch/Dockerfile docker/prefetch
#
# Push:
#   docker push beclab/harveyff-nemoclaw-prefetch:2026.4.27
#
# Image ref is pinned in templates/deployment.yaml (init-prefetch). Rebuild, push, bump tag there.

# Versions for the static-binary fetch stage
ARG MICRO_VERSION=2.0.13
ARG MICRO_ARCH=linux64-static
ARG RG_VERSION=14.1.1
ARG RG_TRIPLE=x86_64-unknown-linux-musl
ARG FD_VERSION=10.2.0
ARG FD_TRIPLE=x86_64-unknown-linux-musl

# ----------------------------------------------------------------------------
# Stage 1: static binaries (busybox/micro/rg/fd) — unchanged from prior image.
# ----------------------------------------------------------------------------
FROM alpine:3.20 AS unpack
ARG MICRO_VERSION
ARG MICRO_ARCH
ARG RG_VERSION
ARG RG_TRIPLE
ARG FD_VERSION
ARG FD_TRIPLE
RUN apk add --no-cache curl ca-certificates tar \
  && mkdir -p /prefetch \
  # busybox provides static `vi` (skill-env wraps it with a 2-line shim).
  && install -m0755 /bin/busybox /prefetch/busybox \
  # micro editor.
  && curl -fsSL -o /tmp/micro.tgz \
       "https://github.com/zyedidia/micro/releases/download/v${MICRO_VERSION}/micro-${MICRO_VERSION}-${MICRO_ARCH}.tar.gz" \
  && tar -xzf /tmp/micro.tgz -C /tmp \
  && m=$(find /tmp -maxdepth 4 -type f -name micro 2>/dev/null | head -1) \
  && test -n "$m" \
  && install -m0755 "$m" /prefetch/micro \
  && test -x /prefetch/micro \
  # ripgrep.
  && curl -fsSL -o /tmp/rg.tgz \
       "https://github.com/BurntSushi/ripgrep/releases/download/${RG_VERSION}/ripgrep-${RG_VERSION}-${RG_TRIPLE}.tar.gz" \
  && tar -xzf /tmp/rg.tgz -C /tmp \
  && rg=$(find /tmp -maxdepth 4 -type f -name rg 2>/dev/null | head -1) \
  && test -n "$rg" \
  && install -m0755 "$rg" /prefetch/rg \
  && test -x /prefetch/rg \
  # fd.
  && curl -fsSL -o /tmp/fd.tgz \
       "https://github.com/sharkdp/fd/releases/download/v${FD_VERSION}/fd-v${FD_VERSION}-${FD_TRIPLE}.tar.gz" \
  && tar -xzf /tmp/fd.tgz -C /tmp \
  && fd=$(find /tmp -maxdepth 4 -type f -name fd 2>/dev/null | head -1) \
  && test -n "$fd" \
  && install -m0755 "$fd" /prefetch/fd \
  && test -x /prefetch/fd

# ----------------------------------------------------------------------------
# Stage 2: Homebrew tree with portable-ruby pre-vendored.
#
# brew refuses to run as uid 0 (security check is in Library/Homebrew/utils/permissions.rb
# and not configurable), so we add a non-root `brewuser` to the build context. This stage
# clones the latest Homebrew core repo (shallow) and runs `brew vendor-install ruby`,
# which lands a portable-ruby-X.Y.Z/ tree under Library/Homebrew/vendor/portable-ruby/
# plus a `current` symlink. Both are required for any source-build formula in the
# sandbox (the actual gog binary is built separately in Stage 3, so the sandbox only
# uses Homebrew for binary maintenance — ruby satisfies brew's own runtime needs).
#
# The whole ~120MB Homebrew tree is then tar+gzip'd into a single artifact so the
# bridge can stream it into the sandbox in one kubectl exec hop instead of N kubectl cp.
# ----------------------------------------------------------------------------
FROM debian:bookworm-slim AS brewbuilder
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       git curl ca-certificates procps file coreutils tar gzip \
  && rm -rf /var/lib/apt/lists/*
RUN useradd -ms /bin/bash brewuser
USER brewuser
WORKDIR /home/brewuser
ENV HOMEBREW_NO_AUTO_UPDATE=1 \
    HOMEBREW_NO_ANALYTICS=1 \
    HOMEBREW_NO_INSTALL_FROM_API=1 \
    HOMEBREW_NO_ENV_HINTS=1 \
    PATH=/home/brewuser/.linuxbrew/Homebrew/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN git clone --depth=1 https://github.com/Homebrew/brew.git .linuxbrew/Homebrew \
  && /home/brewuser/.linuxbrew/Homebrew/bin/brew vendor-install ruby \
  && ls /home/brewuser/.linuxbrew/Homebrew/Library/Homebrew/vendor/portable-ruby/current/bin/ruby
USER root
RUN cd /home/brewuser/.linuxbrew \
  && tar -czf /tmp/homebrew.tar.gz Homebrew \
  && ls -la /tmp/homebrew.tar.gz \
  && du -sh /tmp/homebrew.tar.gz

# ----------------------------------------------------------------------------
# Stage 3: assemble the prefetch image. busybox final stage so the chart's
# `sh -c` init-prefetch args (cp/chmod/ls) work without needing a bigger base.
# ----------------------------------------------------------------------------
FROM busybox:1.36
COPY --from=unpack       /prefetch              /prefetch
COPY --from=brewbuilder  /tmp/homebrew.tar.gz   /prefetch/homebrew.tar.gz
RUN ls -la /prefetch/
