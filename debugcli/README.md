# debugcli (Olares)

Packaging for **`docker.io/beclab/debug-cli-ubuntu22.04:v0.0.1`**: an Ubuntu 22.04 image with common CLI tools, exposed in Olares via the **web terminal** pattern (same idea as `tradingagents`, slimmer than `texttoimagesearch`).

## Layout (vs `texttoimagesearch`)

| Piece | Role |
|--------|------|
| `templates/deployment.yaml` | Workload pod: `debugcli-shell` (`sleep infinity`) + in-pod **nginx** (port 80, `index.html` from ConfigMap). |
| `templates/configmap-nginx-workload.yaml` | `default.conf` + `index.html` for the sidecar nginx. |
| `templates/service-web.yaml` | `ClusterIP` **:80** → in-pod nginx (OpenResty 8080 proxies here). |
| `templates/terminal.yaml` | `beclab/terminal` + RBAC to exec into `debugcli-shell`. |
| `templates/ingress.yaml` | OpenResty: **8080** → `{{ .Release.Name }}-web:80`; **8081** → terminal. |

`texttoimagesearch` is nginx + SPA + search3 RBAC; this app uses a small static page plus a separate **terminal** entrance.

## Entrances (`OlaresManifest.yaml`)

- **8080** (`debugcli`): default — static **index.html** (in-pod nginx).
- **8081** (`debugcliTerminal`): web shell into the Ubuntu `debugcli-shell` container.

`metadata.entrances[].host` is **`debugcliingress`**, matching Service `{{ .Release.Name }}ingress` when the Helm release name is **`debugcli`**. If your platform uses another release name, rename the host to `<release>ingress` accordingly.

## Persistence

Host path `{{ .Values.userspace.appData }}` is mounted at **`/workspace`** in the CLI container.

## Local render

```bash
helm template debugcli . --namespace demo \
  --set userspace.appData=/tmp/debugcli-data
```
