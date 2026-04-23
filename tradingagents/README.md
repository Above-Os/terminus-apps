# TradingAgents (Olares)

Olares packaging only. Docker image is built and pushed from the fork [github.com/leolianger/TradingAgents](https://github.com/leolianger/TradingAgents) (see `README-Docker.md` there). This chart deploys `docker.io/goai007/tradingagents`.

Chart layout mirrors **context7** / **whisperwebuiv2**:

- **`tradingagentsingress`**: OpenResty routes **8080** → static info (`serve.py` in the app container), **8081** → `beclab/terminal` WebSocket for pod exec.
- **`tradingagents` workload**: **`tradingagents-shell`** (`sleep infinity`, no probes) for web terminal; **`tradingagents`** runs `serve.py` on **8080** (startupProbe only; **no liveness** — avoids probe killing the HTTP container).
- **`terminal`**: RBAC + `beclab/terminal` apiserver (`pods/exec` → **`tradingagents-shell`**).

**Entrances** (see `OlaresManifest.yaml`):

| Name | Port | Use |
|------|------|-----|
| `tradingagentsTerminal` | 8081 | **Default**: web terminal (same `apiserver` flags as context7 — no `--shell`); run `python -m cli.main` in `/home/appuser/app` |
| `tradingagents` | 8080 | Info page + HTTP probes; `invisible: true` in manifest so the launcher favours the terminal |

**App data / `.env` (nofx-style)**:

- **hostPath** = `userspace.appData` only (one `Data/...` segment; no `/Release/tradingagents` suffix).
- **`templates/configmap-dotenv.yaml`** inlines default keys. Init seeds **`/app/data/.env`**. Chart runs **`ln -sf /app/data/.env`** → **`/home/appuser/app/.env`** in both containers (does **not** rely on image `entrypoint-web.sh`). Mount **`/app/data`** only (**no** `subPath` `.env`).
- Reports are persistent: **`/home/appuser/app/reports`** is symlinked to **`/app/data/reports`** at container startup.
