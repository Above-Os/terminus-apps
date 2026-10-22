# LiteLLM 1.106.2 verification

Tested on 2026-10-22 with Olares 1.12.7-20260908, an amd64 node, and Chart 1.0.23. This is a test-market candidate; independent colleague smoke testing and public-market publication remain outstanding.

## Installation and upgrade paths

| Path | Result |
| --- | --- |
| Market Chart 1.0.22 / LiteLLM 1.103.0 to Chart 1.0.23 / 1.106.2, in place through Upload | Passed |
| Historical Chart 1.0.21 / LiteLLM 1.83.3 to Chart 1.0.23 / 1.106.2, in place through an isolated Upload application | Passed |
| Chart 1.0.23 / 1.106.2 in an isolated application and database | Passed |

Both upgrade paths preserved seeded team/model IDs, virtual-key model permissions and team relations, and the SHA256 of a persistent test file. Existing virtual keys remained usable and team metadata remained writable. PostgreSQL custom-format backups completed before migration; the init container checks that the dump is nonempty and that `pg_restore --list` succeeds. Full restore rehearsal and whole-database row comparisons were not performed.

The historical test alias initially had an incorrect internal proxy Service reference. Its baseline installation was corrected and its seed data recreated **before** starting the recorded in-place migration. No uninstall/reinstall was used to claim migration success.

## Real model integration

The target version was additionally tested through the existing Olares Router's `default-chat` route, which resolved to Qwen3.8-27B via llama.cpp. The default route/provider configuration was unchanged. The test credential was restricted to `default-chat` and had a one-hour expiry. Test models and credentials are runtime data and are absent from this chart.

| Check | Result |
| --- | --- |
| Non-streaming chat through a LiteLLM virtual key | Exact expected response and nonzero usage |
| Streaming chat | Content, multiple SSE chunks, final usage and `[DONE]` received |
| Function calling | Tool name/arguments returned in `choices[0]`; a second request used the supplied tool result |
| Streaming function calling | Tool-call arguments reconstructed correctly and stream completed |
| Parallel function calling | Both requested functions returned with distinct IDs |
| Strict JSON schema output | Parsed JSON matched the requested values |
| Anthropic Messages-compatible endpoint | Expected text and usage returned through Router |
| Responses-to-chat bridge | Expected final message returned; reasoning and final-message items kept separate |
| Virtual-key model allowlist | Unauthorized model returned HTTP 403 |
| Usage logging | Model calls and token totals appeared in LiteLLM SpendLogs and Router usage |
| Restart persistence | Same model IDs and virtual key worked after an application restart; stored Router credential forwarded successfully |

The bridge used a separate runtime `custom_openai/default-chat` model configuration, so a chat-only upstream could serve the Responses-compatible request through translation. It is not a claim that Router offers a native Responses provider for this model.

## Relevant newer-version behavior

- `/v1/messages/count_tokens` returned a positive token count and `litellm_count_source=local_estimate`; this is an estimate, not a claim of the provider's exact tokenizer count.
- An exhausted test key returned HTTP 422, without successful inference.
- `/v1/responses/compact` rejected an unmanaged `previous_response_id` with HTTP 403.
- `PATCH /credentials/{name}` rejected renaming with HTTP 400 when supplied with the required request fields. Dummy credentials were cleaned up.
- An isolated master-key rotation re-encrypted three stored values. Original model/key relationships still worked, and another restart with the old-key migration variable removed succeeded.
- Browser login, the new Home usage summary, command-palette search/navigation, and the redesigned Usage page were checked. A real Playground call returned the expected text and displayed token/latency information. Reasoning could be collapsed separately.

Expected authorization/budget denials appear as failed requests in the usage UI; they are intentional negative tests. Early Responses assertions incorrectly concatenated reasoning with the final message, and an early credential update omitted a required field. Corrected test requests/assertions passed; neither required a chart or application-code workaround.

## Compatibility and limits

- Empty/public master keys such as `sk-1234` must be replaced. If an old key encrypted stored credentials, set `LITELLM_MIGRATE_FROM_MASTER_KEY` with the old key alongside the new key, verify migration success, then clear the old-key field and update callers as necessary. Existing secure keys are preserved.
- UI users must sign in again after the old session-format transition. stdio MCP defaults and upstream MCP credentials, cache message limits, and Responses WebSocket session limits require review for customized installations.
- The Olares CLI environment editor rejected an update because it also submitted the noneditable `SMTP_ENABLED` field. Rotation was verified using isolated test-only chart overrides; the Olares settings UI rotation workflow itself was not tested.
- Main container UID/GID 1000, actual workload image, healthy database readiness, successful migration logs, and zero restart counts were checked. An existing `trusted_proxy_ranges` warning does not block the tested workflows. The environment-credential-login warning is handled by the administrator onboarding workflow below.
- Image availability and matching source/destination config digests were checked for amd64 and arm64; runtime verification was amd64 only. No independent signature verification was performed.
- No tests claim coverage of standalone Lens/ClickHouse, Decisions providers, Bedrock-specific counting, real paid-provider pricing, OAuth, SMTP delivery, large-batch pricing, MCP servers, or long-running WebSocket behavior, since those services were not configured for this run.
- v1.103.0 is in the affected range of [GHSA-7hp6-4w63-5g45](https://github.com/BerriAI/litellm/security/advisories/GHSA-7hp6-4w63-5g45); the target includes that fix. The separate [October 21 supply-chain incident](https://docs.litellm.ai/blog/security-incident-oct-21-2026) recommends pinning 1.106.2. This verification is not a penetration test or a claim of zero remaining vulnerabilities.

Cleanup completed: the test application was uninstalled, its Upload record removed, and both inventories checked for absence. The temporary scoped Router key was disabled and its status verified. The default-chat target was unchanged. No --delete-data operation was used.


## Independent administrator login and red-banner migration

`DISABLE_ENV_CREDENTIAL_LOGIN` is a new editable Olares boolean (default `false`). It renders a real YAML boolean in `general_settings.disable_env_credential_login`. It is also mapped into the Deployment environment so an Olares Apply changes the pod template and restarts the process; a ConfigMap subPath alone would retain the old configuration until restart. Existing values without the new field render `false`.

User workflow (also included in the listing and upgrade notes in all seven supported locales):

1. Sign in with the existing `UI_USERNAME` / `UI_PASSWORD` bootstrap account.
2. Under **Internal Users**, create a separate **Proxy Admin** with an email address different from the bootstrap username. Generate/copy its invitation link, and use that link to set the account's own password. Copying the invitation link does not require SMTP delivery.
3. Verify the independent account in a private browser window, including an admin-only page. Keep bootstrap access enabled until this succeeds.
4. Open **Olares Settings → Applications → LiteLLM → Manage environment variables**. Edit `DISABLE_ENV_CREDENTIAL_LOGIN` to `true`, confirm, then **Apply**.
5. Wait for the automatic application restart and sign in with the independent account. The environment-credential red warning is no longer advertised by readiness details. The old bootstrap username/password is rejected; master API authentication remains available.
6. To recover bootstrap access if the independent account is unavailable, use the same Olares settings page to set the field back to `false` and Apply. This deliberately restores the warning as well.

The default stays `false` for both new installs and upgrades: automatically disabling the only verified login before the user creates an account would lock administrators out. Changing the Olares UI_PASSWORD field does not change an independent database account's password. Existing sessions are not asserted to be revoked by this toggle.

Follow-up validation on `olarestest01`, amd64, LiteLLM 1.106.2, isolated `litellmlogin622`:

- Created an independent Proxy Admin through `/user/new`, `/invitation/new`, and the onboarding token/claim flow; the user set its own password through the invitation API. No direct database edits or SMTP sends were used.
- Initial bootstrap and independent account login returned HTTP 303. Independent session authorized `/user/info`, and readiness details showed the environment warning.
- After disabling, the same independent account still returned 303 and authorized an admin read; bootstrap login returned 401, `show_env_credential_login_warning=false`, and master-key `/model/info` remained available.
- The Olares **settings UI**, rather than the CLI editor, successfully saved/applied the setting. The CLI editor still fails because it resubmits noneditable `SMTP_ENABLED`.
- The first draft changed only the ConfigMap and did not restart on Apply. The final Deployment mapping fixes that; UI changes between false and true produce replacement pods. Recovery to false restored bootstrap login (303) and the warning, without losing the independent administrator.

The isolated testing chart used alias-specific app/database names and random disposable bootstrap defaults; these are not included in this chart. Its test-only chart patch is 1.0.24 so the corrected Deployment could be upgraded in place; the submitted chart stays 1.0.23, the single patch above the remote baseline.

Final follow-up: a second UI Apply to `true` replaced the recovered pod, and all disabled-login assertions passed again. Browser sign-in with the independent administrator succeeded on the final configuration; Home displayed the Admin account with no environment-credential warning. The warning was not dismissed using browser storage or hidden by a UI patch. The temporary login credential file was deleted immediately after filling the browser form.

Cleanup: the follow-up test application and both Upload versions were removed, with absence verified. No persistent data/backup purge was requested or performed.
