# LibreSpeed 1.0.13 verification

Date: 2026-09-11. Environment: Olares 1.12.6, Linux amd64.

## Fix

Chart 1.0.12 selected the LinuxServer PR image `lspipepr/librespeed:version-v6.2.1`, but retained the official LibreSpeed image's `WEBPORT=8080`, `MODE`, and `/servers.json` configuration. The container initialized but its port 8080 probes were refused, causing repeated liveness restarts.

Chart 1.0.13 uses `beclab/librespeed-speedtest:6.2.1`, mirrored from the official `ghcr.io/librespeed/speedtest:6.2.1`. The app version stays at 6.2.1. Database declarations, persistent paths, user settings, probes, and service ports are unchanged.

The mirror task completed successfully and exposes amd64 and arm64 images. Both image config digests match their upstream architecture variants. Runtime validation below covers amd64 only.

## Results

| Check | Result |
|---|---|
| `olares-cli chart lint` (admin and regular-user rendering) | Pass |
| Fresh install of 1.0.13, isolated app identity | Pass: application 1/1 Ready, ingress 2/2 Ready, zero restarts |
| Fresh-install HTTP startup | Pass: homepage probes and frontend asset requests returned HTTP 200 |
| Existing broken instance repaired with target image | Pass: application 1/1 Ready, zero restarts after replacement |
| Existing application entrance | HTTP 200 |
| Modern HTML, JavaScript, settings, server list, stability page, worker | HTTP 200 |
| Ping endpoint | HTTP 200 |
| 64 KiB upload to `backend/empty.php` | HTTP 200 |
| Download from `backend/garbage.php?ckSize=1` | HTTP 200, at least 1 MiB |
| Served server list versus persistent user configuration | Equal |
| Existing database and server configuration | Backup verified; original database fingerprint and server-list SHA256 unchanged |

The existing telemetry table was empty. A PostgreSQL 17.5 client produced a custom-format dump and successfully listed it with `pg_restore --list`; a restore rehearsal was not performed.

Validation scope was explicitly reduced to fresh-install readiness and the completed repair checks. Two-version migration tests, telemetry-write/statistics-login checks, and an automated browser speed-test run were not completed. Do not interpret these results as that broader coverage.

## Deployment notes

The existing instance came from `market.test`. Olares rejected an attempt to upgrade it from `upload` with `unmatched chart source`; it was repaired through the authenticated workload API without uninstalling it. Its Market source/package remains unchanged until this Chart is released through that source. The fresh-install test used an isolated Upload app with only its app/workload identity adjusted.

The initial target-image download encountered a transient layer digest mismatch. A full independent download verified the expected layer checksum, and the node's subsequent pull succeeded. Apache's non-blocking ServerName warning remained; HTTP checks and readiness passed.

Temporary validation jobs and backup setup are excluded from this release Chart. Existing data backups are preserved.

## Upstream evidence

- [v6.2.1 release](https://github.com/librespeed/speedtest/releases/tag/v6.2.1)
- [Official Docker configuration](https://github.com/librespeed/speedtest/blob/v6.2.1/doc_docker.md)
- [Official entrypoint](https://github.com/librespeed/speedtest/blob/v6.2.1/docker/entrypoint.sh)
