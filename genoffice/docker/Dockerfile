# GenOffice (Electron office suite) streamed over KasmVNC for Olares.
# Base starts as root then drops to PUID/PGID (1000).
FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble

ARG GENOFFICE_VERSION=0.7.512
ENV TITLE=GenOffice \
    GENOFFICE_VERSION=${GENOFFICE_VERSION}

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        wget \
        ca-certificates \
        fonts-noto-cjk \
        fonts-liberation \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
    && wget -q -O /tmp/genoffice.deb \
        "https://github.com/genspark-ai/genoffice/releases/download/v${GENOFFICE_VERSION}/genoffice_${GENOFFICE_VERSION}_amd64.deb" \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/genoffice.deb \
    && rm -f /tmp/genoffice.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && (command -v genoffice >/dev/null || ls -l /opt /usr/bin /usr/lib 2>/dev/null | head)

COPY root/ /
RUN chmod +x /usr/local/bin/genoffice-olares \
    && sed -i 's/\r$//' /usr/local/bin/genoffice-olares /defaults/autostart

EXPOSE 3000
