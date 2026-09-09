# Note

Turn recordings and videos into transcripts you can read, replay and export

- Chart version: **0.4.12**
- App version: **0.4.12**
- Image: `docker.io/beclab/note:0.4.12` (amd64 + arm64, frontend embedded in the binary)
- Arch: amd64, arm64 · Olares >= 1.12.6

## What changed in 0.4.12

The implementation behind this app was replaced. It is now a Go service that runs
a nine-stage pipeline (extract → chunk → enhance → diarize → segment → transcribe
→ align → translate → summarize) against the audio model applications installed
on the same Olares, reached through Router.

🔴 **There is no upgrade path from 0.2.0.** The app changes from per-user to a
shared workspace install, so app-service refuses the transition — and the two
implementations do not share a data layout. Uninstall the old version first.

## Why each permission

| Permission | Why |
|---|---|
| `appData` | Holds the original recordings, the audio extracted from them, and the rendered artefacts. Originals are never deleted. |

Two permissions the previous implementation asked for are **no longer needed**:

- `appCache` — uploads land straight on this app's own volume, so there is no
  staging directory to keep on the same filesystem.
- `userData: Home/` — importing from the user's drive goes **through the Files
  app** rather than mounting Home into this pod. The user still picks a file from
  their own drive; this app never sees the rest of the tree.

## Shared workspace app

`options.shared: true` — one instance serves everyone on this Olares rather than
one per user. The app reads the user directory from lldap over NATS so it can
attribute a recording to the person who uploaded it.

## Model gateway address

Normally **nothing to fill in**: the chart points the app at Router's shared
gateway entrance, which is stable across users. The app sends its own identity
as `x-caller-appid`, so Router bills and routes per application.

## Middleware

Declares a Postgres database (`note`) through the platform's middleware, not a
bundled instance. Schema migrations run on startup.

## Dependency

Depends on Router, deliberately **without `mandatory: true`**: this app has been
named differently on different Olares instances, and pinning a name plus making
it mandatory welds the chart to one generation of that naming.
