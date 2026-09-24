# Concat for Olares

Concat 0.2.2 Beta, packaged as an amd64 browser-accessible desktop, with a
separate authenticated HTTP/MCP bridge. Upstream: https://github.com/jub0t/Concat

## Storage and editing

Use **Files > Home > Documents > Concat** for source media, projects and exports.
This maps to `/config/Projects`. Desktop settings use the private app-data volume.
The desktop runs as UID/GID 1000; an init container sets ownership of the two
mount roots without recursively changing existing user files.

The app uses CPU rendering. GUI and API editing share one engine workspace;
`concat_begin_edit` pauses the GUI, and `concat_finish_edit` restores it.
Always finish the session, including after an error. Idle sessions expire after
15 minutes. Do not run multiple editing clients concurrently.

## MCP connection

The invisible `concatapi` entrance serves `/mcp` on port 8080. The chart keeps
this entrance internal; remote access must also satisfy Olares entrance policy.
Do not disable application authentication to work around entrance access.

Configure an HTTP MCP client with the entrance URL followed by `/mcp`, and
`Authorization: Bearer <installation-token>`. The random token is generated in
the `concat-api` Kubernetes Secret and retained by Helm lookup on upgrades.
An administrator can retrieve it from that Secret; the application also writes
`/config/api-token` with mode 0600. Never publish either value.

Call `concat_help` and `concat_status` first, then `concat_begin_edit`.
Use `concat_request` for supported engine requests and `concat_job` for render
jobs. Finish with `concat_finish_edit`. `concat_list_files` lists project files.
`GET /healthz` is unauthenticated; editing, files and MCP endpoints require the token.

Paths are restricted to the project root. Upload source files through Olares
Files before importing them. Text `fontSize` is a fraction of frame height
(e.g. 0.045), not a pixel count. CJK titles default to Noto Sans CJK SC when no
font is explicitly selected. Custom fonts must live inside the project root.

## Version and source

The runtime image is pinned by digest in `templates/concat.yaml`. The desktop
and CLI are from upstream v0.2.2, commit
`39f24d9ab158fb384acdd2a7ab974bf768f80d73` (AGPL-3.0-or-later).
The exact deployed bridge and launcher sources are included in `build/`, along
with the upstream license. See `build/README.md` for image provenance.

Only amd64 is declared and validated. ARM64, GPU acceleration and optional AI
model features have not been validated in this package. This is a Beta editor.
See `TESTING.md` for the English end-to-end validation record.
