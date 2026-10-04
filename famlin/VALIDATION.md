# Validation status

Date: 2026-10-04 (Asia/Shanghai)

## Current draft: 0.0.5

Chart 0.0.5 changes only Olares packaging and documentation: the main entrance defaults to Internal and a system-authentication sub-policy protects `/admin`, `/api/admin`, `/api/auth/setup`, and `/api/auth/register` (including subpaths). It keeps upstream Famlin 0.7.0 and its pinned GHCR image unchanged.

- Chart lint and package/upload passed.
- The same policy was applied to the existing test instance through Olares Settings. With the main entrance Public, anonymous `/` and `/health` returned 200, while `/admin`, `/admin/`, `/admin/users`, `/admin?x=1`, and `/api/admin/users` redirected to Olares authentication (302). Empty POST requests to `/api/auth/setup` and `/api/auth/register` were intercepted by the gateway (303); no accounts were created.
- `/api/auth/setup-status` remained accessible (200), and an empty member-login POST reached Famlin validation (400), rather than the Olares login page.
- Internal mode also protected the administrator paths from unauthenticated requests through the test network. The final live configuration is Internal with default policy `system` and the protected-path sub-policy retained.
- Full 0.0.5 upgrade was attempted but blocked during image resolution by repeated GHCR TLS handshake and DNS timeouts. The operation was canceled; these entrance tests run against the existing 0.0.3 workload, not a completed 0.0.5 rollout. Fresh-install policy provisioning and direct GHCR deployment remain unverified.
- The earlier 0.0.4 revision restored the original GHCR address and verified the 256×256 Olares placeholder icon. The functional results below remain from 0.0.3 through the byte-identical NJU cache.

## Passed on the test device

- Repository fast-forwarded to upstream/main at `367b5366f` before adding the chart.
- Olares `1.12.7-20260919`, amd64; chart `0.0.3`, upstream Famlin `0.7.0`.
- GHCR direct pulls failed with connection resets and DNS errors. NJU GHCR cache returned the byte-identical pinned manifest and successfully downloaded the image on the target device.
- Chart lint, packaging, upload, installation, database migrations and HTTP health passed. All three pod containers became ready.
- Browser opened the administrator dashboard successfully. The owner completed upstream onboarding; no install-time administrator variables are required.
- A separate temporary account verified independent password login, a text-only post, comment, image upload and video upload/post.
- Authenticated media reads returned 200, anonymous reads returned 401. Video byte ranges returned 206 with the requested byte count.
- Uploaded files were written as UID 1000 on the Files-backed volume.
- Test users, group, posts, comments, upload records and test media were removed. The existing owner account was preserved.
- Stop/resume recreated the pod, returned to 3/3 Ready and retained the initialized database and the same SHA-256 signing-key fingerprint. The restart API initially timed out after stopping; explicit resume completed successfully.
- Application secrets are generated or supplied by middleware through Kubernetes Secrets; no fixed credentials are committed.

## Confirmed upstream limitation

An authenticated user outside the test group could read both posted image and video URLs (200). Removing a member from the group also left those URLs readable by that account (200). This confirms upstream 0.7.0's ordinary bound-upload authorization behavior. Group feed filtering is not file isolation. The listing and README disclose this limitation; use one instance only for one trusted family.

## Scope

This is a test-store port, not a production security or performance certification. Local linked-album imports, email delivery, native mobile clients and upgrade-from-an-older-Famlin migration have not been tested. No independent-family isolation is claimed.
