# Famlin for Olares

This chart ports upstream Famlin 0.7.0 without changing its account system or adding mandatory install-time settings. The upstream project is early-stage software.

## First use

1. Install the chart, then open the app's `/admin/` path.
2. Complete Famlin's own onboarding to create an administrator.
3. Create a group, add/invite members, and open `/` for the member feed.

The main entrance defaults to **Internal**. The owner may change it to **Public** in Olares Settings for relatives who only have Famlin accounts. A separate path policy keeps `/admin` (including subpaths), `/api/admin`, `/api/auth/setup`, and `/api/auth/register` behind Olares system authentication in either mode. Keep this sub-policy when changing the entrance level. The read-only `/api/auth/setup-status` and normal member login remain under the main entrance policy. Famlin still authenticates its own users after the Olares gateway check. No OIDC, Olares account mapping, or preset administrator is included.

## Upstream media access limitation

In upstream 0.7.0, `canReadUpload` permits any authenticated user to read a bound, non-circle upload by its URL. Group feed filtering does not enforce the same group boundary on these files. Treat one instance as one trusted family; removing group membership does not revoke an existing account's access to known ordinary upload URLs. This port preserves upstream behavior and does not claim independent-family isolation. See [upstream implementation](https://github.com/TimVanOnckelen/famlin/blob/v0.7.0/backend/src/services/uploads.ts).

## Email configuration

Configure SMTP in Famlin's `/admin/` settings: SMTP host, port, username, password, sender address, and the email notifications switch. Upstream 0.7.0 stores these values in its database; it does not read `SMTP_*` environment variables. This chart does not synchronize Olares mailbox variables or add a startup script.

Upstream uses implicit TLS on port 465 and Nodemailer's default STARTTLS negotiation on other ports (587 by default). The chart allows outbound ports 465 and 587. Famlin requires the SMTP host, username and password to create its mail transport. Actual mail delivery has not been tested.

## Storage

- Files `Home/Pictures/Famlin/uploads` → `/app/uploads`: uploaded media and retained originals.
- Files `Home/Pictures/Famlin/library` → `/media/library`, read-only: optional local albums. Set this path in Famlin's media settings; immediate subfolders become albums. Upstream's local-folder provider does not import HEIC or video files.
- Olares PostgreSQL stores users, groups, posts, comments and application settings. Credentials are supplied by middleware through a Kubernetes Secret.
- The signing key is generated once in `famlin-auth` and reused on upgrades. It is retained across release removal to support reinstalling with retained data. Deliberate deletion rotates sessions.

Back up the database and uploads together. Uninstalling the chart does not delete the user-owned Home directory. Deleting a source file in a linked album can break its reference; this chart does not add a backup importer or LarePass auto-publishing.

## Packaging

- Platform: Olares >= 1.12.6; amd64 only. Upstream's 0.7.0 image currently provides no arm64 image.
- Image: `ghcr.io/timvanonckelen/famlin:0.7.0@sha256:88670a0117919a69f64bca68986b1c718e24e0d7f283ffff109bf2912933f7d2`.
- Registry transport: original upstream GHCR. Chart 0.0.3 was tested using the NJU GHCR cache with the identical manifest digest; this draft restores GHCR as requested. The 2026-10-04 direct GHCR upgrade attempt failed with TLS/DNS timeouts. The test instance uses a separate 0.0.6-test.1 package through the same NJU cache and pinned digest; the PR retains GHCR. See VALIDATION.md.
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
- App and entrance icon: https://app.cdn.olares.com/appstore/famlin/icon.png (256×256 PNG).
