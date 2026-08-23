# GenOffice (Electron office suite) streamed over KasmVNC for Olares.
# Stage 1 builds a linux/amd64 .deb from the custom-LLM fork; stage 2
# installs it on the same KasmVNC base as 0.0.3 (SwiftShader + idle patch).
ARG NODE_IMAGE=node:22-bookworm
FROM ${NODE_IMAGE} AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    CSC_IDENTITY_AUTO_DISCOVERY=false \
    npm_config_audit=false \
    npm_config_fund=false \
    PATH="/root/.cargo/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        python3 \
        make \
        g++ \
        pkg-config \
        libssl-dev \
        fakeroot \
        dpkg-dev \
        xz-utils \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgtk-3-0 \
        libgbm1 \
        libasound2 \
        libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable

ARG GENOFFICE_GIT_URL=https://github.com/harveyff/genoffice.git
ARG GENOFFICE_GIT_SHA=c4077fdde97a852e6da37d05768ec518963dff6e
RUN git clone --filter=blob:none --no-checkout "${GENOFFICE_GIT_URL}" /src \
    && git -C /src fetch --depth 1 origin "${GENOFFICE_GIT_SHA}" \
    && git -C /src checkout --detach FETCH_HEAD

WORKDIR /src
RUN npm ci
RUN npm run notices && npm run build:all
WORKDIR /src/apps/shell
RUN npx electron-builder --linux deb --publish never
RUN mkdir -p /out \
    && cp /src/apps/shell/release/genoffice_*_amd64.deb /out/genoffice.deb \
    && ls -lh /out/genoffice.deb

FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG GENOFFICE_VERSION=0.7.512
ENV TITLE=GenOffice \
    GENOFFICE_VERSION=${GENOFFICE_VERSION} \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    GTK_IM_MODULE=fcitx \
    QT_IM_MODULE=fcitx \
    XMODIFIERS=@im=fcitx

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        locales \
        fonts-noto-cjk \
        fonts-liberation \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        dbus-x11 \
        fcitx5 \
        fcitx5-chinese-addons \
        fcitx5-frontend-gtk3 \
        x11-xkb-utils \
    && grep -q '^zh_CN.UTF-8 UTF-8' /etc/locale.gen || echo 'zh_CN.UTF-8 UTF-8' >> /etc/locale.gen \
    && locale-gen zh_CN.UTF-8

COPY --from=builder /out/genoffice.deb /tmp/genoffice.deb
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/genoffice.deb \
    && rm -f /tmp/genoffice.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && (command -v genoffice >/dev/null || ls -l /opt /usr/bin /usr/lib 2>/dev/null | head)

COPY root/ /
COPY patch_kasmvnc.py /tmp/patch_kasmvnc.py
RUN chmod +x /usr/local/bin/genoffice-olares \
    && sed -i 's/\r$//' /usr/local/bin/genoffice-olares /defaults/autostart \
    && python3 /tmp/patch_kasmvnc.py \
    && rm -f /tmp/patch_kasmvnc.py

EXPOSE 3000
