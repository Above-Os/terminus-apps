# Lares

Chat on Olares, wired to Router.

Current chart version: **0.26.28** — `version` in `Chart.yaml` matches the
manifest version.

Current app version: **0.26.27** — `appVersion` in `Chart.yaml`, the manifest's
`spec.versionName`, and the image tag in `values.yaml` match the application release.

## Chart ownership (test / public index)

`owners` (no extension) must list the **GitHub login** used to open index PRs:

```yaml
owners:
- ffkijjkokok
```

## Requirements

| Item | Requirement |
|------|-------------|
| Olares | >= 1.12.7 |
| Dependency | Router (`>=1.0.0`) |
| Arch | `amd64`, `arm64` |

## Install

1. Install from Market (Chat test source URL: `https://appstore-server-test.bttcdn.com`).
2. Confirm Router is running.
3. Open the Lares entrance and chat.

Auth is the in-cluster app identity (`x-caller-appid`). The default model, web search, and voice input are chosen in Settings.
