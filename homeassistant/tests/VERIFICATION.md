# Home Assistant installation and upgrade verification

Date: 2026-10-08. Profile: olarestest01@olares.com. Olares: 1.12.7-20260908.

Two isolated Upload applications were used. Only Chart/manifest application identity, workload replica references and overlay workload references were renamed. Container names, services within isolated namespaces, images and bootstrap code remained those of the corresponding source Chart. The original homeassistant instance was not modified.

## Previous version upgrade: PASS

- Baseline source: repository HEAD Home Assistant Chart 1.0.37, Core 2026.9.1, beclab/homeassistant-home-assistant:2026.9.1.
- Target tested: local Chart 1.0.42, Core 2026.10.0, beclab/homeassistant-home-assistant:2026.10.0.
- App: haqaup. Installed baseline, created an administrator and persistent script, automation, scene and downloadable attachment. Restarted baseline after creating www to register the static route.
- Configuration backup archive and consistent SQLite backup downloaded locally. Archive contains .storage/auth; SQLite integrity_check returned ok.
- Upgraded the same Upload app in place without uninstalling or replacing storage.
- Same administrator login passed; user ID, HTTP stable settings, exact script/automation/scene file hashes and downloaded attachment SHA256 matched baseline.
- Retained script and automation executed with observed events; entity create/read/delete passed after upgrade.
- Recorder integrity_check returned ok. All baseline rows retained in states (53), states_meta (20), state_attributes (22), compared by IDs and corresponding state/entity/attribute values.
- Bootstrap log: existing HTTP configuration left unchanged.
- Official check_config exit code 0. All four containers ready, zero restarts, actual Core image 2026.10.0.
- Evidence: seed-result.json, upgrade-result.json, recorder-result.json, haqaup-final-status.json.

## Fresh installation: PASS

- App: haqafresh, new distinct identity and storage; distinct core.uuid from haqaup. Target tested: local Chart 1.0.42 / Core 2026.10.0.
- First-time onboarding and administrator creation completed. Bootstrap initialized stable reverse-proxy configuration.
- 13 authenticated checks passed: password login/token exchange; API config/states/services; entity create/read/update/delete; authenticated WebSocket and states; script execution and automation event action; original configurations restored; session revoked.
- Official check_config exit code 0. Four containers ready, zero restarts, actual image 2026.10.0.
- Evidence: fresh-functional-result.json, haqafresh-final-status.json.

## Scope and diagnostics

Tests exercised application APIs through the packaged nginx and runtime files/SQLite. Browser visual interactions, external OAuth and physical devices were not tested. Both Core versions emitted a rich library SyntaxWarning about return in a finally block; no blocking startup or migration error was observed.

The initial migration harness expected the very next WebSocket event to be the automation result. A queued event caused that assertion to fail; the harness was corrected to wait for the expected automation event and the check passed. No production change was required.

The missing-stable repair scenario on the original instance was verified in the preceding test round; this round verifies the normal previous-version stable-preserving upgrade and fresh installation.

Local backup archives contain private test account information and must not be committed or published. Temporary test instances and Upload entries are removed after verification; original homeassistant is retained.

## Submission package

Submitted Chart 1.0.39 is based on above-os/terminus-apps main Chart 1.0.38. Local test Chart 1.0.42 was used for repeated Upload iterations. The submitted HTTP bootstrap and deployment behavior match the tested local build; only the Chart version, localized release notes and test documentation differ. All seven localized upgrade descriptions preserve the remote baseline release history.

Earlier verification: Core 2026.8.3 / Chart 1.0.35 installed, HTTP stable manually removed, then upgraded to local Chart 1.0.42 / Core 2026.10.0. Bootstrap repaired stable with an exact original-file backup and Core/nginx started successfully. Authenticated basic and new-feature tests were subsequently performed on this target.

New features: Template Climate config flow creation, heat mode and target temperature; user/person name sync and avatar upload/512px retrieval; map TileJSON/vector tile fetch; trigger-ID automation branches passed through APIs. Eleven new integration forms opened, three infrared integrations correctly reported missing emitters, and Willow requires an external account. ESPHome form opened; physical outgoing connection not tested.

Eight HTTP bootstrap regression tests passed using the actual installed Core 2026.10.0 schema. The final submitted bootstrap was re-tested the same way. Chart lint and git diff --check passed.

The fetched remote baseline Core 2026.9.3 / Chart 1.0.38 was subsequently tested directly against submitted Chart 1.0.39, as detailed below. Browser UI and hardware checks remain pending.

## Remote previous version → submitted package: PASS

- Date: 2026-10-08. Isolated Upload app haqalatest on the same Olares test profile.
- Baseline: actual Core 2026.9.3 / Chart 1.0.38 from above-os/main. Target: submitted Chart 1.0.39 / Core 2026.10.0, with only isolated application/workload identity substitutions.
- Created a test administrator, script, automation, scene and downloadable attachment on baseline. Verified execution and writes before upgrade; downloaded and validated configuration archive plus consistent SQLite backup.
- Upgraded the same installed app in place, preserving identity and storage. Actual new Pod uses beclab/homeassistant-home-assistant:2026.10.0.
- Same account login and user ID passed. HTTP stable settings and exact script/automation/scene bytes matched baseline. Attachment bytes and SHA256 matched through nginx download. Retained script and automation executed; post-upgrade entity create/read/delete passed.
- Recorder SQLite integrity_check passed. All baseline rows retained: states 49, states_meta 21, state_attributes 23, comparing IDs and state/entity/shared-attribute values.
- Repeated 13 authenticated functional checks: all passed. Official check_config: exit 0. Four containers ready with zero restarts. Bootstrap reported existing HTTP configuration left unchanged; no stable or blocking startup/migration error.
- Test harness was made tolerant of unrelated queued events and uses a unique temporary entity name per run to prevent collision. Final migration check and separate functional check both passed.
- Evidence retained locally: latest-seed-result.json, latest-upgrade-result.json, latest-recorder-result.json, latest-functional-result.json, latest-final-status.json. These contain no account secrets. Private backup files are excluded from the PR.
- Temporary isolated app, its private test data and both uploaded versions were removed after verification. Original homeassistant instance retained.
