#!/opt/venv/bin/python
"""FreeToken /health also returns HTTP 200 while loading or after an error."""

import json
import os
import sys
import urllib.error
import urllib.request

# The port the engine was told to listen on. `ft serve --port` and both
# launch paths (image CMD, deploy/wrappers/freetoken.sh) read the same
# FREETOKEN_PORT, so a probe that ignored it would check the wrong socket.
PORT = os.environ.get("FREETOKEN_PORT") or "1919"


def healthy(state, *, live=False):
    if not isinstance(state, dict):
        return False
    if live:
        # FreeToken reports status=ok even when a failed cache rebuild has
        # latched maintenance=failed; generation then requires a restart.
        return state.get("status") in ("loading", "ok") and state.get("maintenance") != "failed"
    return state.get("status") == "ok" and state.get("maintenance", "serving") == "serving"


def main():
    try:
        # Ignore HTTP_PROXY for a probe of the local engine.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{PORT}/health", timeout=3) as response:
            state = json.load(response)
        live = "--live" in sys.argv[1:]
        if healthy(state, live=live):
            return 0
        if isinstance(state, dict):
            detail = " ".join(f"{key}={state.get(key, 'unset')}" for key in ("status", "maintenance", "phase"))
        else:
            detail = "health response is not a JSON object"
        print(f"FreeToken {'liveness' if live else 'readiness'} failed: {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"FreeToken health request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
