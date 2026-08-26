# Note

Turn recordings and videos into transcripts you can read, replay and export

- Chart version: **0.1.11**
- App version: **2.0.45**
- Image: `docker.io/olareshzy/note:2.0.45-1b5092ee` (bundles the binary — nothing to upload after install)
- Arch: amd64 · Olares >= 1.12.6

## Why each permission

| Permission | Why |
|---|---|
| `appData` | Stores the original recordings and the audio extracted from them. Originals are never deleted. |
| `appCache` | Upload staging. **Must sit on the same filesystem as the final directory**, otherwise "move file" degrades into copying a 1 GB file. |
| `userData: Home/` | So users can import a recording from their own drive. Only the user knows which folder their recordings live in — narrowing the path would mean guessing for them. Two mitigations: **the mount is readOnly**, and the file browser only lists audio/video extensions and re-checks the path before importing. |
| `needsSharedAccess` | Calling Router needs the platform-issued app identity (caller JWT). **Without this the Secret is never created**, and calls fail with `missing_credentials`. |

## Model gateway address

Normally **nothing to fill in**: the chart renders `https://router.<owner zone>` from
`.Values.user.zone`. Note the address carries **no `/v1` suffix** — the app appends it.

To point at a different OpenAI-compatible gateway, set `GATEWAY_URL` at install time,
or change it later in the app's settings page (takes effect immediately, no reinstall).

## Dependency

Depends on Router, deliberately **without `mandatory: true`**: this app has been named
differently on different Olares instances, and pinning a name plus making it mandatory
welds the chart to one generation of that naming.
