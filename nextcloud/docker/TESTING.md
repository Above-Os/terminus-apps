# Nextcloud with integrated Euro-Office: test record

Tested on 2026-10-10 on `olarestest01@olares.com`, Olares `1.12.7-20260908`, an amd64 node. Chart `1.0.29` targets Nextcloud `33.0.9`, Euro-Office connector `11.0.6`, and document server `9.3.4-hotfix.1` (`9.3.4.37`). Nextcloud and the document server are separate workloads installed as one Market app.

## Upgrade coverage

The test-market baseline is `above-os/terminus-apps:main`, Nextcloud chart `1.0.28` / app `31.0.14`. The preceding different application version is chart `1.0.19` / app `31.0.4`, taken from commit `5603c35f0`. Each baseline was installed in its own Upload app, populated with data, and upgraded in place; app identity, database and persistent mount paths were retained.

The old `31.0.4` chart's OpenResty proxy required a test-only writable runtime directory and PID location on this Olares version. Its Nextcloud image and application version remained unchanged. Alias substitutions preserve upstream image names, `/usr/src/nextcloud`, and `nextcloud-init-sync.lock`.

Before upgrading, each instance received four files under `UpgradeProbe`: a unique text marker, a DOCX containing rich text and a table, an XLSX containing formulas and two sheets, and a two-slide PPTX. The baseline record contains each file's ID, byte length and SHA256. The text file was favorited, the account display name was changed and read back, and a system configuration marker was saved.

Initial verification passed for fresh `33.0.9`, `31.0.14 → 33.0.9`, and `31.0.4 → 33.0.9`. All four baseline files retained their IDs, exact contents, lengths and favorite states; the same account and settings remained available. A new post-upgrade file was uploaded and downloaded. Both migrated instances connected to the document server, converted a signed DOCX to PDF, and accepted a signed save callback whose changed contents were verified in the downloaded DOCX. Browser login with the original account passed on both upgraded instances.

Final beclab-image validation passed for all three paths. Test-only alias chart versions `1.0.29`–`1.0.32` were used while correcting the migration script and readiness probe; the submitted chart remains the next patch after the remote baseline, `1.0.29`. The final alias packages contain the submitted runtime templates and images; differences are alias names and test chart versions.

| Final path | Data and application result |
| --- | --- |
| Fresh Nextcloud 33.0.9 | Initialization; original-account browser login; four-file read/write checks; connector check; signed DOCX → PDF; signed save callback; browser edit/save and downloaded DOCX XML marker passed |
| 31.0.14 → 31.0.14 → 32.0.14 → 33.0.9 | Four seeded files retained exact IDs, sizes, SHA256 and favorites; display name and configuration marker preserved; new file write/read; original-account browser login; connector, conversion and callback passed |
| 31.0.4 → 31.0.14 → 32.0.14 → 33.0.9 | Same seeded-data, account, write/read and Office checks passed |

Final main pods were fully ready with zero container restarts. Both local mounts verified `status: ok`, code `0`, in every instance. The final test window (from 11:18 UTC) contained zero Nextcloud log entries at error severity or higher. Machine-readable, credential-free file evidence is recorded in `docker/test-results.json`. Both migration backup directories were mode `0700`; their dump/archive SHA256 checks and archive listings passed.

The final-package run found and fixed three issues: maintenance mode remained enabled when the first bridge already matched the installed code version; an absent background-job-mode setting caused `set -e` to abort; and readiness requests using the pod hostname were rejected as untrusted. The script now disables maintenance before the explicit recovery upgrade, tolerates an unset background-job mode, and sends a trusted `Host: localhost` readiness header. Interrupted test upgrades resumed without reinstalling or losing their seeded data. Background jobs include the upstream updater's randomized delay; this delay was allowed to finish.

The final fresh browser save was verified by downloading the DOCX and finding `Final multiarch package browser save proof 2026-10-10` in `word/document.xml`.

## Automatic migration and recovery

The chart upgrades installed Nextcloud 31 through `31.0.14` and `32.0.14` before starting `33.0.9`, following the [Nextcloud upgrade rules](https://docs.nextcloud.com/server/33/admin_manual/maintenance/upgrade.html). The intermediate steps use non-root init containers. Each step repeats `occ upgrade` to finish a database upgrade interrupted after the new code was copied, runs the background job entrypoint three times, and preserves the configured background job mode.

Before the first step, maintenance mode is enabled and the Nextcloud database is dumped with PostgreSQL client 17. Configuration, data, custom apps, themes and the version file are archived. Both backups are listed and hashed before the completion marker is written. The backup is stored in `data/.olares-upgrade-backups/pre-office-31`, mode `0700`, outside normal file listings. Existing backups are reused on restart. Failures stop the init sequence; installations older than Nextcloud 31 are rejected. Sufficient free space for the database and file backup is required.

Recovery requires restoring the matching database dump and file archive together into an isolated installation of the original version. Starting an older image on an upgraded database is not a rollback. Archive and dump listing/checksum checks passed; a full restore drill has not been performed.

The runtime hook enables the built-in external-storage app and ensures the existing Olares `External Storage` and `Home Storage` mounts are available. Existing mount configurations with those names are retained. Both mounts passed `files_external:verify` on fresh and upgraded instances; restart preserved the data checks.

## Browser and Office tests

Fresh-install browser login, DOCX open/edit/save and Nextcloud file write-back passed. The editor reported all changes saved; the downloaded document contained `Fresh install browser save proof 2026-10-10`.

The earlier migrated main instance additionally passed:

| Test | Verified result |
| --- | --- |
| DOCX editing | English/Chinese text, bold paragraph, undo/redo, 2×2 table; downloaded XML retained formatting and contents |
| XLSX editing | Multiplication, SUM, IF, recalculation and second-sheet reference; saved values `62.5`, `40`, `102.5`, `PASS`, `102.5`; reopen retained both sheets |
| PPTX editing | Two slides, titles/body text, mixed English/Chinese bullets, save and slideshow rendering; downloaded PPTX retained both slides |
| Signed conversion | DOCX → PDF with a valid `%PDF-` result |
| Signed callback | Document contents changed in the file downloaded from Nextcloud |
| Restart | User files and callback-saved contents persisted |

Browser automation can cancel the trailing Chinese composition if Escape is sent immediately after typing. The first PPTX subtitle retained only `中文与 English：保存、`; it is not counted as a complete Chinese-input test. The second-slide Chinese bullet was committed with Enter and persisted.

## Scope and remaining limits

Native arm64 cluster installation, concurrent editing, large imported documents, charts/images, dedicated IME behavior, slideshow navigation, a full backup restore, and separately configured third-party apps are not covered by the amd64 functional tests. Architecture availability and any emulated arm64 checks are reported separately from native cluster coverage. Colleague smoke testing and public Market release are still required after this test-market draft PR.

All task-created auxiliary instances and every associated Upload chart version were uninstalled/deleted and confirmed absent from the Upload catalog. The five local ARM smoke-test containers, network and Nextcloud volume were also removed. The original main application and its earlier backup are retained for manual review. Test passwords, JWTs, database credentials and live secrets are excluded from this repository.

## Upstream components

- [Euro-Office connector 11.0.6](https://github.com/Euro-Office/eurooffice-nextcloud/releases/tag/v11.0.6), archive SHA256 verified in the Dockerfile.
- [Euro-Office document server 9.3.4-hotfix.1](https://github.com/Euro-Office/DocumentServer/releases/tag/v9.3.4-hotfix.1), patched for UID/GID 1000, port 8080 and pre-generated font caches.

## Multiarchitecture images

All four images were rebuilt for `linux/amd64` and `linux/arm64`, pushed to `harveyff`, mirrored to `beclab`, and checked platform by platform. Image configurations match. Filesystem layers match, including decompressed SHA256 verification where registry manifest conversion recompressed a layer. Registry index digests differ legitimately after OCI/Docker manifest conversion.

| beclab image | Verified index digest |
| --- | --- |
| `harveyff-nextcloud:31.0.14-bridge.2` | `sha256:1c53eea97753a63272e97b8592ae0ddf0bb534d8aa2460feb6fa800e54be3c1d` |
| `harveyff-nextcloud:32.0.14-olares.3` | `sha256:aa5e5f5e6e2726df3a7d8052995363cae2fe9b2b062f8ac54e9c2682cc7fd468` |
| `harveyff-nextcloud:33.0.9-office.3` | `sha256:97f3bed56024fc3f65aa62ce9c69ebbc21e893ffccb3e5f4a7e3f20c7feb3b31` |
| `harveyff-euro-office:9.3.4-hotfix.1-olares.6` | `sha256:a09d43c26590ffe117cabe0387766d80183c891e54fe2711a28b250106b7c6d7` |

The ARM images additionally ran under Docker Desktop emulation on amd64 Windows: Nextcloud 33.0.9 initialized against PostgreSQL 17; authenticated DOCX upload/download preserved SHA256 after restart; the connector checked document server 9.3.4.37 successfully. The document server ran as UID 1000 with generated font caches and converted a signed DOCX to a valid 75,239-byte PDF. The ARM PostgreSQL 17 backup client produced a dump readable by `pg_restore --list`. This is emulation coverage, not an Olares ARM node test.