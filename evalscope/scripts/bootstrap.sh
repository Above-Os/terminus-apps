#!/usr/bin/env bash
set -Eeuo pipefail

readonly EVALSCOPE_VERSION=1.12.0
readonly BOOTSTRAP_REVISION=2
readonly RUNTIME_DIR=/cache/runtime/evalscope-1.12.0
readonly DATA_DIR=/data
readonly MARKER_FILE="$RUNTIME_DIR/.ready"

umask 077
mkdir -p "$DATA_DIR/outputs" "$DATA_DIR/config" "$DATA_DIR/bootstrap" /cache/runtime
exec > >(tee -a "$DATA_DIR/bootstrap/startup.log") 2>&1
trap 'echo "[$(date -u +%FT%TZ)] Bootstrap failed at line $LINENO (exit $?). The next start will retry."' ERR

echo "[$(date -u +%FT%TZ)] EvalScope bootstrap revision $BOOTSTRAP_REVISION; uid=$(id -u), gid=$(id -g)"
test "$(id -u)" = 1000
test "$(id -g)" = 1000
readonly BOOTSTRAP_HASH="$(sha256sum /startup/bootstrap.sh | cut -d ' ' -f 1)"

if [[ ! -f "$MARKER_FILE" ]] || [[ "$(cat "$MARKER_FILE")" != "$BOOTSTRAP_HASH" ]] || [[ ! -x "$RUNTIME_DIR/bin/python" ]]; then
  rm -f "$MARKER_FILE"
  # Reuse the official image's ML dependencies, while pinning EvalScope in its own venv.
  python3 -m venv --system-site-packages "$RUNTIME_DIR"
  "$RUNTIME_DIR/bin/python" -m pip install --disable-pip-version-check "evalscope[service]==$EVALSCOPE_VERSION"
  # Ensure a venv-local CLI even when the base image already has this version.
  "$RUNTIME_DIR/bin/python" -m pip install --disable-pip-version-check --ignore-installed --no-deps "evalscope==$EVALSCOPE_VERSION"
  # ModelScope builds an AST index beside its package; keep that package UID-1000 writable.
  "$RUNTIME_DIR/bin/python" -m pip install --disable-pip-version-check --ignore-installed --no-deps "modelscope==1.38.1"
  "$RUNTIME_DIR/bin/python" - <<'PY'
from importlib.metadata import version
from pathlib import Path
import evalscope
from evalscope.service import create_app
from modelscope.msdatasets import MsDataset
assert version('evalscope') == '1.12.0'
assert version('modelscope') == '1.38.1'
ui = Path(evalscope.__file__).parent / 'web' / 'dist' / 'index.html'
assert ui.is_file(), f'Missing Web UI: {ui}'
app = create_app(outputs='/data/outputs')
with app.test_client() as client:
    assert client.get('/health').status_code == 200
    assert client.get('/').status_code == 200
print('Version, writable ModelScope dataset loader, service dependencies and Web UI verified.')
PY
  printf '%s\n' "$BOOTSTRAP_HASH" > "$MARKER_FILE"
  "$RUNTIME_DIR/bin/python" -m pip freeze > "$DATA_DIR/config/installed-packages.txt"
  "$RUNTIME_DIR/bin/python" - "$BOOTSTRAP_HASH" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
Path('/data/bootstrap/installed.json').write_text(json.dumps({
    'evalscope': '1.12.0', 'modelscope': '1.38.1', 'bootstrap_revision': 2, 'script_sha256': sys.argv[1],
    'installed_at': datetime.now(timezone.utc).isoformat(),
    'runtime': '/cache/runtime/evalscope-1.12.0', 'system_site_packages': True,
}, indent=2) + '\n')
PY
fi

echo "[$(date -u +%FT%TZ)] Starting original EvalScope service on :9000"
trap - ERR
exec "$RUNTIME_DIR/bin/evalscope" service --host 0.0.0.0 --port 9000 --outputs "$DATA_DIR/outputs"
