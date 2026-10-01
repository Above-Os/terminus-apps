# Famlin for Olares

This chart ports upstream Famlin 0.7.0 without changing its account system or adding mandatory install-time settings. The upstream project is early-stage software.

## First use

1. Install the chart, then open the app's `/admin/` path.
2. Complete Famlin's own onboarding to create an administrator.
3. Create a group, add/invite members, and open `/` for the member feed.

The entrance defaults to **Private** to protect the unclaimed first administrator. After completing onboarding, the owner may set the entrance to **Public** in Olares Settings for relatives who only have Famlin accounts. Public here removes the Olares gateway sign-in; Famlin still authenticates its own users. No OIDC, Olares account mapping, or preset administrator is included.

## Upstream media access limitation

In upstream 0.7.0, `canReadUpload` permits any authenticated user to read a bound, non-circle upload by its URL. Group feed filtering does not enforce the same group boundary on these files. Treat one instance as one trusted family; removing group membership does not revoke an existing account's access to known ordinary upload URLs. This port preserves upstream behavior and does not claim independent-family isolation. See [upstream implementation](https://github.com/TimVanOnckelen/famlin/blob/v0.7.0/backend/src/services/uploads.ts).

## Storage

- Files `Home/Pictures/Famlin/uploads` → `/app/uploads`: uploaded media and retained originals.
- Files `Home/Pictures/Famlin/library` → `/media/library`, read-only: optional local albums. Set this path in Famlin's media settings; immediate subfolders become albums. Upstream's local-folder provider does not import HEIC or video files.
- Olares PostgreSQL stores users, groups, posts, comments and application settings. Credentials are supplied by middleware through a Kubernetes Secret.
- The signing key is generated once in `famlin-auth` and reused on upgrades. It is retained across release removal to support reinstalling with retained data. Deliberate deletion rotates sessions.

Back up the database and uploads together. Uninstalling the chart does not delete the user-owned Home directory. Deleting a source file in a linked album can break its reference; this chart does not add a backup importer or LarePass auto-publishing.

## Packaging

- Platform: Olares >= 1.12.6; amd64 only. Upstream's 0.7.0 image currently provides no arm64 image.
- Image: `ghcr.nju.edu.cn/timvanonckelen/famlin:0.7.0@sha256:88670a0117919a69f64bca68986b1c718e24e0d7f283ffff109bf2912933f7d2`.
- Registry transport: NJU GHCR cache. The image manifest digest is byte-identical to upstream GHCR; layers are content-addressed and verified by the runtime.
- Source revision: `3923743fc2b0d43280f6f9541edba389d2dec7a3`.
- Effective UID/GID: 1000. The trusted permissions init container only prepares the exact directory roots, without recursive ownership changes.
- One replica with Recreate strategy; upstream runs database migrations before starting the web/API process.
- Entrance timeout: 600 seconds. Upload limits inside Famlin and outside the application proxy still apply.
- No custom PWA, native mobile fork, OIDC, or new media format support is added by this port.

## Validation

See `VALIDATION.md` for results on the deployment target. Do not infer production readiness from installation alone.

## Sources

- [Upstream source and MIT license](https://github.com/TimVanOnckelen/famlin/tree/v0.7.0)
- [Upstream setup documentation](https://famlin.app/docs/server-setup)
- The listing icon is the unchanged upstream mobile app icon from v0.7.0.
