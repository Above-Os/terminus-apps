#!/bin/bash
set -euo pipefail
umask 077
mkdir -p "$YUE_STUDIO_DATA_ROOT" "$YUE_MODELS_ROOT" "$HOME" "$XDG_CACHE_HOME"
MCP_AUTH_ENABLED="${MCP_AUTH_ENABLED:-false}"
case "${MCP_AUTH_ENABLED,,}" in
    true|1|yes|on) export YUE_STUDIO_MCP_AUTH_DEFAULT=0 ;;
    false|0|no|off|"") export YUE_STUDIO_MCP_AUTH_DEFAULT=1 ;;
    *) printf 'MCP_AUTH_ENABLED must be true or false\n' >&2; exit 64 ;;
esac
test -n "${YUE_STUDIO_MCP_TOKEN:-}"
mkdir -p "$YUE_STUDIO_DATA_ROOT/config"
printf '%s\n' "$YUE_STUDIO_MCP_TOKEN" > "$YUE_STUDIO_DATA_ROOT/config/mcp-token"
export YUE_STUDIO_ACCESS_KEY
YUE_STUDIO_ACCESS_KEY="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
envsubst '${YUE_STUDIO_ACCESS_KEY} ${YUE_STUDIO_MCP_TOKEN} ${YUE_STUDIO_MCP_AUTH_DEFAULT}' < /opt/olares/nginx.conf.template > /tmp/yue2-nginx.conf
music-server &
server_pid=$!
nginx -c /tmp/yue2-nginx.conf -g 'daemon off;' &
proxy_pid=$!
cleanup() {
    kill -TERM "$server_pid" "$proxy_pid" 2>/dev/null || true
    wait "$server_pid" "$proxy_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
set +e
wait -n "$server_pid" "$proxy_pid"
exit $?
