# FlowStudio

All-in-one AI workflow production on Olares: import ComfyUI workflows, resolve models
and custom nodes, allocate GPU per project, and generate on PC / mobile.

Current Chart version: **0.3.28** (must match `Chart.yaml` / `OlaresManifest.yaml`).

## Requirements

| Item | Requirement |
|------|-------------|
| Olares | >= 1.12.6 |
| GPU | NVIDIA (bind accelerator on install or resume) |
| Arch | `amd64` |
| Suggested VRAM | >= 6 GiB free for lite image templates |

Resource envelope (`spec.accelerator`; must cover business API + engine):

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 2 | 12 |
| Memory | 4Gi | 40Gi |
| Disk | 2Gi | 10Gi |
| GPU Memory | 6Gi | 24Gi |

## Install

1. In Olares **Market**, search **FlowStudio** (test or public source, depending on release).
2. Bind an NVIDIA GPU when prompted.
3. When status is running, open the **FlowStudio** entrance from the desktop.

Maintainer lint / package:

```bash
olares-cli chart lint deploy/flowstudio
olares-cli chart package deploy/flowstudio
```

## First-time setup

1. **Network & download sources:** pick domestic / global for your region, then save.
2. **Environment & engine:** run GPU detect and lock the recommended engine (GPU-backed init cannot finish without a lock).
3. **(Optional) Engine management:** confirm current / recommended image versions.

## How to use

1. In Admin, create a project from a recommended template or a valid ComfyUI Save JSON.
2. Review the parse report (nodes, models, VRAM, custom-node precheck), then confirm.
3. Follow init progress (model download, node install, engine pre-pull); on failure, follow on-screen recovery actions.
4. After init succeeds, tune parameters in the workspace and submit a job; preview results in history.

Admins own project definition and environment; published projects can be used by normal users when multi-role is enabled.

## Workloads and images

| Workload | Role |
|----------|------|
| `flowstudio` | Business API + dual frontend static (entrance `:8080`) |
| `flowstudioengine` | Static engine placeholder; with default `dynamicEngine.enabled=true`, engines are created per project |

| Image | `values.yaml` field |
|-------|---------------------|
| App | `appImage` / `image` (prefer bumping `appImage` when upgrade sticks values) |
| Engine | `engineImage`; optional `engineImageAmd` |

Release packages must set `dev.hotReload: false`.

## Router catalog declaration

The Manifest declares `options.LLMGatewaySupported: true` and an `envs` entry pinning
`MODEL_MODE` to `image_generation`. Neither value reaches a chart template: Market lifts
them out of the Manifest and serves them in its provider catalog, which is how Olares
Router files FlowStudio under the Creative capability domain before anything is installed.
Every model application carries category AI, so `MODEL_MODE` is the only thing that
distinguishes one domain from another.

`MODEL_SUPPORTS` is declared empty. It exists for `llm-init`-backed applications to build a
model card from, and Router's `supports_*` whitelist has no image-generation key to put
there. FlowStudio does not run `llm-init`.

The declaration makes FlowStudio visible and installable from Router; it does not make it
routable. FlowStudio is not a shared application and exposes no `sharedEntrances`, so the
projected provider row has a placeholder base URL and Router cannot forward model calls to
it.

## Storage and middleware

- **appData:** user projects and business data (`USER_DATA_DIR` → `{owner_id}/comfyui/…`)
- **appCommon:** shared model root (`MODELS_DIR`) — **public across apps/projects on the node**
- **Postgres:** system middleware database `flowstudio` (do not declare as an app dependency)

## Uninstall

Default: uninstall **without** deleting persistent data so the shared model library under
`appCommon` (`/olares/rootfs/Common/comfyui` on typical Olares) is left alone.

```bash
olares-cli market uninstall flowstudio --watch
```

Only pass `--delete-data` when you intentionally want appData wiped (projects / userdata).
**Ask before using it** — models live on the shared Common volume and must not be treated as
disposable per-app cache. The chart pre-delete hook removes dynamic engines and this app's
GPUBindings only; it never deletes model weights.

## Upgrade

Bump together:

1. `Chart.yaml` `version` / `appVersion`
2. `OlaresManifest.yaml` `metadata.version` and `spec.versionName`
3. If code or deps changed: push new image tags and update `values.yaml` `appImage` / `engineImage`
   (**tag only** for Chat/test-market PRs — do **not** append `@sha256:…`; GitBot digest checks false-404)
4. Fill `spec.upgradeDescription` (and `i18n/*/OlaresManifest.yaml`)

After upgrading from Market: reopen the app; if GPU binding was lost, re-bind under Olares Accelerators, then start again.

Manifest `upgradeDescription` tracks `spec.versionName`, the app release, and currently
covers 0.3.24. Chart versions 0.3.25–0.3.28 are chart-only bumps that ship the same image.  
QA: [`../../docs/test-cases-v0.3.20.zh.md`](../../docs/test-cases-v0.3.20.zh.md) / [`../../docs/test-cases-v0.3.20.md`](../../docs/test-cases-v0.3.20.md).

## Chart layout

```text
flowstudio/
  Chart.yaml
  OlaresManifest.yaml
  values.yaml
  owners
  templates/
  i18n/en-US/OlaresManifest.yaml
  i18n/zh-CN/OlaresManifest.yaml
  icons/                 # local source; Market icon must be a public URL
  README.md
```

Product delivery overview: [`../README.md`](../README.md).  
Test-market publish steps: [`../../docs/olares-test-market.md`](../../docs/olares-test-market.md).
