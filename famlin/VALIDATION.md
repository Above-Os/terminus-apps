# Validation status

Date: 2026-10-01 (Asia/Shanghai)

## Current draft: 0.0.4

The draft restores the original `ghcr.io` image address with the same pinned digest and uses the 256×256 Olares default icon as a placeholder. Chart lint passes and the icon URL resolves with the expected dimensions. This revision has not been installed on the test device; runtime results below apply to 0.0.3 through the NJU cache.

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
