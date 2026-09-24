FROM docker.io/harveyff/concat:0.2.2-olares-r9@sha256:9557bad989488855e88cc591ed42d7e18c87f38857f0dd3fff8bd3d424defb9f
COPY api/server.py api/commands.json /opt/concat-api/
COPY --chmod=755 start-concat /usr/local/bin/start-concat
