# ShowDoc 3.9.4 upgrade verification

Date: 2026-09-29. Target: test market `above-os/terminus-apps` (draft only).

## Versions and scope

- Latest test repository baseline: Chart 1.0.18 / ShowDoc 3.7.1; proposed Chart 1.0.19 / ShowDoc 3.9.4.
- Formal market baseline observed: Chart 1.0.14 / ShowDoc 3.7.1.
- Test system: Olares 1.12.7-20260908, amd64.
- Target upstream image: `docker.io/star7th/showdoc:v3.9.4`, amd64 and arm64 manifest. No custom image or mirror required. Privileged initialization uses the existing trusted beclab BusyBox image.
- Upstream release: https://github.com/star7th/showdoc/releases/tag/v3.9.4

## Packaging change

The upstream entrypoint escalates to root even when the pod starts as UID 1000. The chart now starts its own inline runtime configuration: supervisor, nginx, PHP and Mock run as UID 1000 with privilege escalation disabled. Code lives in an emptyDir; the original Home/showdoc path retains SQLite, uploads, install lock and legacy configuration. A narrowly scoped root init creates/chowns only the known directories, without recursive permission changes. Nginx uses port 8080 for both architectures.

Before preparing a changed app version, startup takes a SQLite backup and runs the upstream migration endpoint; failure stops startup. Daily backups briefly stop PHP to release its SQLite lock, then restart it; concurrent backup runs are excluded. Backups are retained and consume additional disk space. The daily schedule is 20:01 UTC. This short daily PHP interruption is an explicit operational tradeoff.

## Executed matrix

| Scenario | Evidence and result |
| --- | --- |
| 3.7.1 -> 3.9.4 | Existing identity upgraded in place. Chinese Markdown, account access and attachment bytes survived. Post-upgrade edits and final pod replacement persisted. This was staged: initial 3.9.4 image upgrade, followed by non-root packaging fixes on the same installation. |
| 3.2.5 -> 3.9.4 | Historical `beclab/aboveos-kldtks-edge:showdoc-v3.2.5` image; actual composer version 3.2.5 (historical Chart 1.0.7 incorrectly labels it 3.2.4). Current chart envelope with isolated test storage was used. Created and saved a Chinese document and associated attachment on the old application, then upgraded in place. Account session, document and attachment survived; post-upgrade write persisted. |
| Fresh 3.9.4 | Initialized and logged in through the UI. Created project/document, rendered Chinese Markdown, edited and saved, uploaded and read an attachment, deleted the page and restored it through the recycle bin. Restored body and attachment link verified after reload. |
| Runtime | Final three installations healthy, 3/3 containers, zero restarts at observation. Actual process ownership checked, including PID 1; app processes UID 1000. Final test aliases used Chart 1.0.21 to avoid local Upload same-version conflicts; submitted chart remains 1.0.19. |
| Backup | Cold backups taken before migration. Final daily backup manually invoked once: PHP stopped, SQLite backup succeeded, PHP restarted; supervisor processes returned RUNNING and HTTP returned 302. |
| HTTP | Missing static resources return 404, direct SQLite path returns 403, fresh attachment URLs use HTTPS. |
| Architecture | amd64 tested on Olares. ARM64 image and custom non-root startup tested under local emulation (UID 1000, HTTP 302); no physical ARM64 Olares verification. QEMU logged unsupported io_setup. |
| Static checks | Chart lint with security-context checks passed; git diff whitespace check passed. |

## Data evidence

- Old attachment SHA-256 before/after: `a028eac34bd7d8fa2d30b0195f1123eed619e37e5018eef1a9bce0842428f6ea` (48 bytes).
- New attachment local/remote SHA-256: `857cdbaa082669c759e64fe37b6de7608da879de48bf5ee1df43b0591e53f188`.
- Migration markers: `MIGRATE-371-394-0929`, `NONROOT-WRITE-PASS-0929`, `MIGRATE-325-394-0929`, `POST-UPGRADE-325-394-PASS`.
- Fresh markers: `FRESH-NONROOT-394-0929`, `EDIT-PASS-NONROOT-0929`.
- Recovery-copy comparisons covered all tables: 46 for the first 3.7.1 backup, 51 before the final non-root migration, and 39 for the installed 3.2.5 baseline. Every row matched the corresponding original backup.

## Qualifications

Upstream seed databases already contain unused-page integrity warnings (pages 34, 35, 36 and 95), confirmed before migration. Original databases were preserved; only local recovery copies were rebuilt with VACUUM INTO, yielding integrity_check=ok and identical table rows. This does not claim that the original live databases have a clean integrity result.

The legacy text attachment displayed a charset mismatch in the browser while retaining identical bytes. Its 3.7.1 document association was added after upgrade; the 3.2.5 association existed before upgrade. A later repeat of the 3.7.1 direct attachment view was blocked by the browser client; earlier viewing and final file hashes are the evidence, and the client block was not bypassed.

External email/OAuth/AI integrations, exhaustive Mock API behavior and physical ARM64 hardware are not covered. Colleague smoke testing is pending. This draft does not publish to the formal market or authorize merging.

Backups, database files, credentials, signed attachment URLs and test user data are excluded from this PR. Test applications and their Upload records are removed after evidence collection; Home data and local backups are retained.
