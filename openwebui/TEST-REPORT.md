Open WebUI 0.12.5 / Chart 1.0.51 - staging validation
Date: 2026-11-03 (Asia/Shanghai)
Environment: Olares 1.12.7, linux/amd64.

Result
Two in-place upgrades and a clean installation passed the tested core,
Router default-chat, browser, data integrity and stop/resume persistence cases.
Each path passed 14 additional functional groups; vector RAG remained blocked
by the unavailable embedding service. This is not an all-integrations pass.

Paths
1. Public-market Chart 1.0.49 / app 0.12.4 -> Chart 1.0.51 / app 0.12.5.
2. Historical Chart 1.0.48 / app 0.12.3 (80175606) -> 1.0.51 / 0.12.5.
3. Chart 1.0.51 / app 0.12.5 with a new database (zero users before signup).

Each used an isolated app alias with matching chart, workload and entrance
references. Upstream images and container data paths were unchanged. Upgrades
retained the same Upload app identity, database and mounts; neither upgrade
was simulated by uninstalling/reinstalling between baseline and verification.
The existing user installation was left untouched.

Migration and integrity
- Registered an admin and created marked chats, a linked folder, note,
  attachment and settings before upgrading; also created a prompt, model
  preset, knowledge collection and nested folder.
- Logged in after upgrading with the original account. Verified IDs, content,
  relationships, settings, table counts, complete upload-file sets and SHA256.
- Verified the persistent WebUI key did not change.
- Created SQLite backup-API snapshots including committed WAL data, ran
  integrity_check, and restored a snapshot into an isolated in-memory database.
  Also backed up configuration, key and persistent files.
- Verified the chart's webui_chart_1.0.51.db backup and its integrity. Init logs
  confirmed existing appData was retained. Post-upgrade create/edit/delete passed.

Router and browser
- Connected Open WebUI to the installed Router's official shared /v1 entrance
  using Olares application identity, no API key. Selected default-chat explicitly;
  did not modify Router providers or default routes.
- Actual backend: unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL.
- Both old releases and the new install passed non-streaming, two-turn context
  recall and SSE streaming; responses were checked, including stream completion.
- Both upgrades retained Router configuration and saved conversation history,
  and completed new calls after upgrading.
- Router usage records confirmed the test caller app IDs, default-chat,
  the served backend, HTTP 200/success, stream mode and token usage.
- All three target instances passed browser login and visible multi-turn chat.
  The upgrade paths returned 42 for 17+25 and then 84 using conversation context.
  The new install recalled its unique code through the follow-up button.
- The new install also passed browser note creation, Chinese input, subpage
  creation/rename, editing after toggling Formatting, and persistence on reload.
- Screenshots, sanitized API results, runtime logs and Router usage evidence
  are retained in the task's full validation artifacts.

Additional functional groups (all three target instances)
PASS: retained prompt/model/knowledge/nested-folder resources.
PASS: chat search, pin/unpin, archive/unarchive and export.
PASS: nested folder rename/expansion.
PASS: note page/subpage create, rename, duplicate, move, edit and delete.
PASS: prompt variables, edit, tags, list and version history.
PASS: model-preset edit/history/export and real Router inference.
PASS: attachment upload, metadata, rename, exact download and delete.
PASS: knowledge metadata edit, file list and export.
PASS: secondary-user isolation for private chats, notes, files and admin APIs.
PASS: calendar/event CRUD and preservation of cross-midnight end times.
PASS: private-channel messages, edits/deletes, thread replies, reactions,
      pin/unpin and members.
PASS: skill CRUD, file listing, history and toggle (no external code executed).
PASS: real text extraction and full-context attachment Q&A with citations.
PASS: real image understanding through default-chat (red rectangle fixture).
Temporary feature flags used for isolated tests were restored.

Persistence, health and platform limitation
- Saved counts for user/auth/chat/folder/note/file/prompt/model/knowledge/skill/
  channel/calendar, attachment hashes and key hash before stop/resume.
- All three retained the complete snapshot, original login, chat history and
  Router configuration; real model calls returned RESTART_OK after recovery.
- Browser reloads after recovery retained login and visible chats/notes.
- Final snapshots before and after recovery showed every container Ready,
  zero unexpected container restarts, target image and API version 0.12.5.
- Market restart requests timed out after stopping the apps and did not finish
  automatic resume. After confirming each stopped state, explicit resume
  recovered it. The one-click restart API is therefore recorded as failed;
  stop/resume and application persistence passed. No blind restart retry.

Blocked / untested
- Vector RAG: process/file returned HTTP 400 because the configured Ollama
  embedding host host.docker.internal:11434 could not resolve. Router had no
  default-embedding target and no local embedding-model cache was present.
  No stub embedding service was substituted. Text extraction/full-context Q&A
  passed, but vector indexing/retrieval still needs an available embedding model.
- OCR, STT/TTS, image/video generation and web search had no configured Router
  targets. OAuth/LDAP/SCIM, email, cloud drives, MCP/Open Terminal and external
  tool integrations had no configured test endpoints/credentials.
- Future scheduled jobs, outgoing webhooks, hardware audio/video, load testing were not exercised. Note collaboration was subsequently
  covered in the supplemental test round below.
- arm64 image availability was verified; no arm64 runtime test was performed.
- Initial invalid non-UUID page requests and an unrefreshed new-model list were
  corrected and the affected tests passed. Original attempts remain in artifacts.

Logs and cleanup
Checked main-container, backup/migration-init and settings-sidecar logs.
Existing CORS wildcard, pydub and grpcio warnings remain; occasional release
update-check network warnings did not affect the tested cases. The intentional
embedding test failure is a documented dependency blocker, not a passing case.
All three temporary test apps and their generated data were removed, their
Upload records deleted, and both installed/Upload lists checked for absence.
No peer smoke test or production-market approval is claimed.


Supplemental 0.12.5 feature regression — 2026-11-03
Environment and chart/image are unchanged. Recreated isolated aliases on
one@olares.fashion; original openwebui was not changed. This is additional
coverage, not a replacement for the complete core test round above.

Across both real old-version upgrades (0.12.4 and 0.12.3) and a clean 0.12.5:
- PASS: legacy-shaped note text attachment and inline image normalize to the
  first page; original file hashes stay identical; repeated save does not
  duplicate links. The clean install checks legacy API-shape compatibility,
  not an old database migration.
- PASS: chat search text, pinned, tag and archived filters.
- PASS: repeated usage snapshots in four OpenAI SSE chunks persist as one
  snapshot: input 11, output 7, total 18 (not 72). Analytics session list,
  token-range filter, detail and execution trace agree. This case uses a
  loopback protocol fixture; it is not a Router billing measurement.
- PASS: real Router default-chat native display_file call for uploaded
  legacy.txt. Saved function_call is completed and function_call_output has
  exists=true, displayed=true with the correct file ID. No embedding stub.
- PASS: interface visibility boolean setting is persisted and restored;
  a string instead of a boolean returns HTTP 422. This verifies config/API,
  not ordinary-user control hiding in the browser.
- PASS: final actual image v0.12.5; all containers Ready, zero restarts;
  latest 300 main-container log lines contained no ERROR/Traceback.

Additional browser / collaboration cases on the clean install:
- PASS: model A -> B without sending, manually selected Code Interpreter,
  A -> B again and reload retain B and the manual feature selection.
  Regenerating the old response creates an assistant message for model B;
  database confirms chat.models=[delta-model-b] and assistant.model=B.
  Both presets use the same Router base model; output identity is not used
  as evidence for preset selection.
- PASS: Analytics overview, Sessions and session details render, including
  the fixture's 18-token total.
- PASS: note presence via two authenticated WebSocket sessions; second
  user's page ID and cursor position are delivered; browser shows the
  Delta collaborator avatar and clicking jumps to that exact page ID.
  Leaving removes presence. User explicitly approved this ordinary test
  account and read/write grants only for the one synthetic note. Grants
  were revoked; account absence and empty note ACL were checked via API.
- PASS: real Router display_file for a file attached to model knowledge;
  completed tool call returns exists=true and displayed=true. Uploaded-file
  browser view renders DELTA_LEGACY_ATTACHMENT_637 and download control.
  This does not test vector indexing or knowledge retrieval.
- PASS: manual Chinese chat rename survives reload.
- PASS: remove New Chat keyboard binding, reload -> Unassigned; pressing
  the former shortcut keeps the note open; Reset Defaults restores binding.
- OBSERVED ONLY: provider connection edit fields and the administrator's
  Visible controls categories render. Other providers and ordinary-user
  visibility behavior are not claimed to pass.

Corrections and remaining limits:
- Initial collaboration attempt with write-only ACL could not read/join;
  separate read grant was explicitly approved before the successful retry.
- Initial display_file API request omitted session_id, so builtin tools
  were intentionally not injected. A genuine authenticated UI WebSocket
  session and waiting for asynchronous completion resolved the test.
- Initial visibility assertion assumed nested config export; export uses
  flat keys. Corrected assertion and roundtrip passed on all three paths.
- Real IME composition plus Backspace remains unverified: browser automation
  supports Unicode insertion, not actual OS input-method composition.
- Embedding query/document prefixes and batching, OCR options, Open Terminal
  timeout, MCP/OAuth and failure webhooks need configured services and remain
  untested; earlier vector RAG/restart limitations still apply. No new claim
  of arm64 runtime, load tests, peer smoke test or production approval.
- No application/Chart changes were required by this supplemental round.
  Evidence: local openwebui-new-feature-evidence.zip and screenshots.
