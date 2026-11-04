# Hermes Agent 0.22.7 — test-market validation

Initial validation: 2026-11-04 (Asia/Shanghai), Olares 1.12.7 / linux/amd64.
Multi-architecture image follow-up: 2026-11-05 (Asia/Shanghai).
Candidate: app 0.22.7 / Chart 1.3.51. This is a draft for the test market;
reviewer smoke testing and full release acceptance remain pending.

## Changes

- Upgrade from the remote Chart 1.3.50 / app 0.22.2 baseline.
- Retain the UID/GID 1000 compatibility overlay and hindsight-client 0.10.2.
- Use the verified versioned image tag without a digest suffix; preserve mobile support.
- Rename the entrance to **Hermes Dashboard**.
- Synchronize the root and seven localized upgrade descriptions.
- Provide compatible **amd64 and arm64** image manifests and declare both architectures.
  ARM64 passed image-level checks and a Docker-emulated startup/Dashboard smoke;
  native ARM64 Olares upgrade and full workflow testing remain unperformed.

Image:
`beclab/harveyff-hermes-agent:v0.22.7-uid1000-multiarch`

The image was built and tested locally, pushed to the authorized harveyff source
repository, and transferred through the Olares image-locker API. It was not
pushed directly to beclab. Source and target image configs and all 41 ordered
layer digests match for **each architecture**; manifest/index digests may differ
after format conversion. The amd64 config is unchanged from the image used for
the original Olares deployment and workflow tests.

## Upgrade and fresh-install matrix

| Path | Actual validation | Result |
| --- | --- | --- |
| Market Chart 1.3.49 / app 0.22.2 to target | In-place replacement with saved values/data; preserved session IDs, titles, messages, attachment/skill hashes, profile and SSH key permissions; real old-session continuation | Pass |
| Historical Chart 1.3.48 / app 0.21.5 to target | In-place replacement; same data checks and real old-session continuation | Pass |
| Fresh target install | Clean initial state; interactive setup; Router chat; code/file tools; Dashboard; restart and persistence | Pass |
| Additional 0.22.2 to target instance | Separate feature-validation run and live entrance-title check | Pass |

The two upgrade baselines each had five consistent SQLite backups with
`integrity_check=ok`. Configuration schema migrations (50/46 to 52) were reviewed
against upstream code; model and terminal settings were preserved. Expected
changes removed obsolete/default-only keys and added the default gateway
multiplex setting. SSH directories remained 700 and private keys 600, UID 1000.
The test-only keys were never authorized on an external host.

The real pre-upgrade conversations were resumed with the same IDs. The follow-up
prompt did not repeat the old marker; the model recalled it correctly and wrote
new messages (2 to 4). Fresh-install restart preserved config/file hashes and
the original conversations. Main services, terminal and proxies were Ready with
zero restarts in the final runtime snapshots.

## Official-doc onboarding and Router default-chat

Reference: [Olares Hermes guide](https://www.olares.com/docs/use-cases/hermes),
Olares 1.12.7 route. The following was executed in the actual browser terminal
of a fresh target install:

1. Run `hermes setup` and select Full setup.
2. Select Custom endpoint and enter the current Router **Apps in Olares** Base
   URL, including `/v1`; use the non-secret `olares` placeholder, as permitted by
   the guide. No Router API key was created.
3. Select Auto-detect. With one model detected, answer `n`, then manually enter
   **default-chat**.
4. Enter the live model's configured context size, **104448**, and display name
   `router-chat`; retain supported reasoning effort **medium**.
5. Select the Local backend. Skip unconfigured messaging platforms and optional
   providers; select No thanks for usage sharing. Reach **Ready to go**.
6. Start `hermes`, send an actual request through Router, and exit with `/exit`.

The current Router default was the local Qwen3.8-27B llama.cpp model. The terminal
conversation actually called `execute_code` (237 × 419 = **99303**), wrote
`OLARES_FRESH_0227_OK` into a disposable workspace file, and read it back. The
session database records the three tool calls. A separate Dashboard conversation
returned **OLARES_DASHBOARD_0227_OK**. Configuration capture confirms
`model.default=default-chat`, `provider=custom` and `terminal.backend=local`.
The model conversation and files were checked again after restart.

Thus the documented initialization/setup and Router conversation path passed.
This statement does not cover Discord pairing, container-side Olares CLI account
login, Gateway API/Open WebUI, or every optional section of the guide.

Documentation gaps observed in 0.22.7: an additional reasoning-effort selector,
extra optional-tool/provider prompts and a usage-sharing prompt; pressing Enter
at Tools for CLI retains selected defaults rather than skipping all tools.
`olares-cli -v` and installed Olares skills were checked, but authenticated
Olares-management operations from the container were not exercised.

## New-feature checks after upgrade

Sources: official [0.22.3](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.3),
[0.22.5](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.5),
[0.22.6](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.6) and
[0.22.7](https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.7)
release notes, plus the exact tagged implementations and upstream acceptance tests.

| Feature | Test scope and result |
| --- | --- |
| `/model reset` | Browser conversation pinned to a specific Router model, reset to default-chat, then correctly recalled old history; same ID and four messages — pass |
| Skill content locks | Real curator lock; file/patch writes and terminal write checks refused; reads allowed, hash unchanged, unlocked control writable — tool integration pass |
| `cron cancel` | Start a real 120-second script, cancel its running execution, observe cancelled ledger/reason and no completion file; schedule preserved — pass |
| Per-job missed-run policy | Seed past next-run times in an isolated real store; skipped versus single catch-up selection and missed-run ledger verified — scheduler integration pass |
| `/loop` countdown | Real model wakeup; countdown changes and status observed; stop command verified, no active loops left — pass |
| Prepared compaction | Opt-in isolated config with an explicit local summary-model route; real HTTP 200 summary, splice hit, live transcript unchanged during preparation, new tail contents preserved — component integration pass with this configuration |
| MCP progress | Real local stdio server/SDK round trip, 20 progress notifications, throttled first/final events, correct call ID and final 100% — protocol/tool callback pass |
| Catalog minimum Hermes version | Isolated catalog metadata through the real Dashboard install handler; incompatible version refused before plugin execution, compatible version predicate allowed — integration pass; real update/pin-retention flow not covered |

These eight checks do not establish full coverage of every upstream change or
every UI renderer. Raw test records and screenshots are retained in the local
run artifacts; no device hostname, credentials or private keys are committed.

## ARM64 image follow-up (2026-11-05)

- Built the same UID/GID 1000 and hindsight-client 0.10.2 overlay for linux/arm64.
- Executed its ARM64 binaries under Docker emulation: machine aarch64, application
  UID 1000, install stamp 0.22.7 / b200f5bc60e, Hindsight import 0.10.2.
- Started s6/gateway/Dashboard using the Chart's loopback binding; Dashboard
  returned HTTP 200 on 127.0.0.1:19119. No host ports were published.
- Reused the already tested amd64 image unchanged and published one source tag
  with amd64 and arm64 descriptors, then transferred through the Olares API.
- The image-locker API refused overwriting the existing beclab tag, so the
  verified content was transferred under the fresh -multiarch tag.
- Verified both target platform configs/layer sequences against the source and
  anonymous availability. All four auxiliary Chart images also provide both
  architectures (busybox, brew/CLI base, nginx, terminal).
- Restored supportArch to [amd64, arm64]. The Chart now references exactly
  `beclab/harveyff-hermes-agent:v0.22.7-uid1000-multiarch`, without an @sha256 suffix.
- Native ARM64 Olares installation/data migration/default-chat workflows were
  not repeated; the existing full amd64 results remain valid for the unchanged
  amd64 image content. Review smoke and the other listed limitations remain.

## Known limitations and remaining review

- Full Olares deployment/migration/workflow tests were on amd64. ARM64 was
  built and started under Docker emulation, not on a native ARM64 Olares device.
- `/delegation` is unavailable in the current exposed clients: Dashboard reports
  it is not available on the shared gateway; classic CLI reports unknown command.
  Backend code existing in the image is not an end-to-end pass.
- Gateway Webapp is default-off and is not a new entrance in this chart. Desktop
  group-chat/lead-routing and related UI features are not validated here.
- Automatic title generation requests `reasoning_effort=none`, rejected by the
  current local model (low/medium/xhigh only). Main chat/continuation passes; the
  title helper warning also occurred on the old baseline.
- Prepared compaction's initial default auxiliary route did not finish within
  the 75-second test bound. The explicit local summary route passed; default
  routing under all model configurations and sustained long-chat load are unproven.
- Voice wake needs unconfigured STT. Discord, WhatsApp/Slack/Telegram, real LAN
  SSH tasks, external Hindsight, plugin OAuth/update workflows, Gateway API/Open
  WebUI and container-side CLI login remain outside verified coverage.
- The declared manifest minimum Olares version predates the tested 1.12.7 host;
  minimum-version runtime compatibility was not tested in this run.

All four dedicated test instances and their Upload records were removed after
explicit user approval; data/backups were retained. The original installed
market application remains on 0.22.2 with the same Pod UID and image. This draft
does not claim reviewer smoke approval or authorize a merge/public release.
