# Lares

Chat shell on Olares: DeepSeek Harness (dsh web) UI wired to Olares Router.

Current Chart version: **0.23.0** (must match `Chart.yaml` / `OlaresManifest.yaml`).

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
| Arch | `amd64` |

## Install

1. Install from Market (Chat test source URL: `https://appstore-server-test.bttcdn.com`).
2. Confirm Router is running.
3. Open the Lares entrance and chat.

Auth is the in-cluster app identity (`x-caller-appid`). The default model, web search, and voice input are chosen in Settings.
