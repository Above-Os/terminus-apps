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

## Webapp and delegation follow-up — 2026-11-05

The previous client-limit conclusion was incomplete: `/delegation` is supplied
by the optional official `advanced-delegation` plugin, not enabled by this image
by default. At the user's request, the chart does not vendor a files directory.
For a missing plugin, initialization uses the official plugin installer pinned
to commit `e404b6816b20237a82f6fbe2749b5a576cf75dba` (version1.0.0). This requires
GitHub access on first installation. Existing plugin directories and explicit
disablement are preserved. Installation errors stop initialization rather than
silently leaving delegation unavailable. No core command or authentication
bypass was added.

Per explicit user choice, the chart adds **Hermes Webapp** (internal Olares
entrance) and enables it when not explicitly configured otherwise. Its own
non-loopback listener keeps upstream Hermes authentication enabled. First-start
initialization generates a random password, stores its scrypt hash in config,
and saves the login information in `/opt/data/webapp/olares-login.txt` (0600).
Open **Hermes CLI**, run `cat /opt/data/webapp/olares-login.txt`, then use those
credentials at **Hermes Webapp**. Existing configured credentials and explicit
Webapp opt-out are preserved; users with existing credentials keep using them.
The first pre-change config is backed up privately before modification.

The proxy preserves upstream authentication and CSP, supports WebSockets,
compresses scripts/styles, and uses Pod-template checksums so ConfigMap updates
restart the runtime and rerun initialization. Main image reference and both
architectures remain unchanged; no new image publication was required.

Validated on a separate `hermesweb227` Upload instance on the authorized Olares
1.12.7/amd64 host; the installed market app was not modified. Test-only Chart
revisions 1.3.52/1.3.53 exercised configuration upgrades without changing the
release candidate's 1.3.51 version. These added integration checks do not claim
that both historical-version upgrade matrices were repeated for this follow-up.

- **CLI:** actual `hermes chat -q '/delegation model_map' --oneshot -Q`
  exited 0 and reported the saved mode, rather than unknown command.
- **Dashboard Chat:** browser `/delegation model_map --now` reported saved
  and applied, with the configured `olares` route. Gateway RPC separately
  covered default, saving model_map, apply-now and refusal of unconfigured routes.
- **Webapp:** internal entrance → independent username/password sign-in →
  workspace → Router **default-chat** returned `OLARES_WEBAPP_227 99303` for
  `237 * 419`. The UI showed model custom/default-chat and low reasoning.
  Anonymous `/api/config` returned 401; authenticated access returned 200.
- **Real delegation:** the browser requested a named-route child. Stored
  `delegate_task` arguments included `option: olares`; the child session's
  source was `subagent`, model `default-chat`, and parent ID matched the Webapp
  conversation. The child returned `OLARES_DELEGATION_227 38771` for `137 * 283`;
  the parent received and displayed the completion. This was not a mock response.
- **Persistence:** the native configuration upgrade kept the generated login
  file byte-identical, preserved Router/routing configuration and both real
  marker conversations, and SQLite integrity_check returned `ok`. A separate
  full Market restart completed successfully; the pre-restart signed-in cookie
  accessed `/api/config` with HTTP 200 without reauthentication. The login file
  remained byte-identical after both native rollouts and restarts.
- **ARM64 initialization:** Docker-emulated aarch64 bootstrap passed; repeated
  initialization preserved password/config, malformed YAML failed without
  overwrite, and explicit Webapp/plugin opt-out stayed intact. This does not
  substitute for native ARM64 Olares workflow coverage.
- **Final proxy:** authenticated script request with Accept-Encoding gzip
  returned gzip content (4408 bytes; decompresses to the original 8264 bytes).

Local evidence: `deliverables/hermesagent-webapp-20261105/`, including sanitized
probe/CLI/database results, bootstrap checks, and browser screenshots
`webapp-delegation.jpg` and `dashboard-delegation.jpg`. Generated credentials,
session cookies and user config are excluded from this repository/PR.

## Known limitations and remaining review

- Full Olares deployment/migration/workflow tests were on amd64. ARM64 was
  built and started under Docker emulation, not on a native ARM64 Olares device.
- Official delegation `model_map` was tested end to end; `profile_routes` is
  registered but cross-profile delegation was not exercised. Desktop group-chat,
  lead-routing, remote Nous sign-in and optional Webapp integrations remain untested.
- Webapp's first browser load was slow in the test browser. The final proxy
  compresses scripts/styles; no cross-network performance guarantee is claimed.
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

The original four dedicated test instances and their Upload records were removed
after explicit user approval. The follow-up `hermesweb227` was also uninstalled
with delete-data=false and its Upload records deleted after validation; all
data/backups and evidence were retained. Local task containers were stopped.
At the end of isolated validation, the original market application had been left
on 0.22.2 with its original Pod UID and image. The subsequent explicitly
authorized existing-instance deployment is recorded below. This draft does not
claim reviewer smoke approval or authorize a merge/public release.


## Authorized existing-instance deployment — 2026-11-05

The user subsequently requested the upgrade of the existing installation and
explicitly selected uninstall followed by Upload installation. Market rejected
an in-place cross-source upgrade from market.olares to upload. After a private
on-device full-home backup and consistent SQLite snapshots, the existing app was
uninstalled with delete-data=false and the candidate installed under the same
app name from upload. The original platform environment values were restored
without publishing their contents. The new application and its Upload record
are intentionally retained for the user, rather than treated as disposable tests.

The Webapp entrance is appended after the existing hidden API entrance. This
retains indexes terminal=0, dashboard=1, api=2 and assigns webapp=3. Before/after
Settings URLs for all three original entrances were compared and are identical.
This ordering prevents the existing Gateway API address from changing.

Native amd64 checks passed: displayVersion 0.22.7 and the pinned upstream commit,
UID1000, all original session IDs and message rows retained, five databases
passing integrity_check, unchanged model configuration, successful default-chat
conversation, registered delegation command, generated Webapp login at mode0600,
anonymous Webapp API rejected with 401 and authenticated API/HTML returning200.
The original API key is unchanged and authenticates /v1/models successfully. Updates to bundled skills matched their previous origin hashes. All other protected files were preserved apart from the expected config and bundle-manifest updates.
Python project metadata uses the placeholder version0.0.0, so the release stamp
and upstream commit were used to verify the application version.

The existing settings are retained in a private backup on the device. Local
sanitized evidence is in deliverables/hermesagent-live-20261105. The deployed
package SHA256 is `06cd2f4f18e8d1638b5840b888a443033477f668b6b1dd02f055ce99f96899ee`. Image tag and architectures are unchanged.

## Remove chart files directory — 2026-11-05

Per user instruction, the entire hermesagent/files directory is removed from
the PR. No plugin source, license copy, provenance file or independent Python
file is shipped in the chart. The plugin ConfigMap and projected mounts are
removed. Missing plugins are installed through Hermes' official installer at
the same immutable official revision, and the configuration is reloaded before
Webapp defaults are saved. Existing installations and explicit opt-outs are
preserved. The first plugin installation now requires GitHub access. Failures
stop initialization; they are not silently treated as successful delegation.

New Docker tests: fresh official installation on amd64 and emulated arm64,
delegation CLI registration, gateway slash execution, refusal of an unconfigured
model-map route, idempotence, unchanged login/config, malformed-config refusal
and explicit opt-out preservation. Installed Python source matches the six
previously tested upstream files byte-for-byte. Webapp anonymous API401 and
authenticated API200 passed after another initialization with the existing
plugin. The package contains no files directory or independent .py files.

The working user installation was not reinstalled for this packaging change.
The earlier native Olares functional tests and live deployment used the
previous vendored initializer; native first-install GitHub access for the new
installer was not separately exercised. Local evidence is retained in
deliverables/hermesagent-no-files-20261105.
