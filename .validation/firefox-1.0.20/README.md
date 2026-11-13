# Firefox 1.0.20 temporary validation branch

This branch contains the Firefox 1.0.20 chart already merged in PR #4471 and the additional in-place upgrade evidence collected on 2026-11-13.

- Base: above-os/terminus-apps main, commit 92f65c082a5fd253319c161a290d70db96bbe9da.
- Chart is unchanged from this base and matches the chart used for the upgrade test.
- Verified upgrade: Chart 1.0.19 -> 1.0.20; Firefox 151.0.1 -> 160.0.
- Existing bookmark, history and file checksum preserved; new bookmark/history and UID-1000 file writes verified after upgrade.
- Browser UI checked; internal HTTP/HTTPS services healthy; direct external probe of node port 30002 refused the connection.
- Existing application and test data retained. See upgrade-test.txt for scope and limitations, and upgrade-verified.png for the UI evidence.
- `olares-cli chart lint firefox`: PASS.

## OAC handoff

OAC rerun is pending and assigned to the colleague who runs it. This branch does not claim an OAC pass. A local Windows attempt could not run the checker's Linux/macOS-only isolated renderer; no application security verdict is inferred from that attempt. Per user instruction, further OAC execution was stopped.

Run OAC against the `firefox/` chart on this branch. Record the checker commit and policy configuration. Include both ordinary rendering and `deviceName: Olares One`, with admin-owner and non-admin-owner scenarios, if supported by the team's test procedure.

No release version bump, market publication, PR creation, or merge is included in this handoff.
