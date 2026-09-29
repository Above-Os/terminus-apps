# Official mcp/context7 on Docker Hub is still the June 2025 image.
# This image pins @upstash/context7-mcp@4.1.1 and ctx7@0.5.12, listens on
# HTTP :8080, and runs as uid 1000. The CLI is baked in so the terminal
# container can exec ctx7 without a root initContainer.
FROM node:22.22.1-alpine

LABEL org.opencontainers.image.source="https://github.com/harveyff/terminus-apps" \
      org.opencontainers.image.description="Context7 MCP 4.1.1 with ctx7 0.5.12"

RUN apk add --no-cache bash \
    && npm install -g @upstash/context7-mcp@4.1.1 ctx7@0.5.12 \
    && mkdir -p /app \
    && chown 1000:1000 /app

USER 1000
WORKDIR /app

ENV MCP_TRANSPORT=http \
    PORT=8080

EXPOSE 8080

CMD ["context7-mcp", "--transport", "http", "--port", "8080"]
