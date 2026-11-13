# Apps pending OAC review

Shared staging branch: `codex/pending-oac-20261113`.

| App | Chart | Upgrade validation | OAC |
| --- | --- | --- | --- |
| Firefox | 1.0.20 | [Passed scoped checks](firefox-1.0.20/upgrade-test.txt) | Pending colleague |
| Chromium | 1.0.18 | [Passed scoped checks](chromium-1.0.18/upgrade-test.txt); Restore pages click needed | Pending colleague |
| Gitea | 1.0.27 | [28.2.0 and 1.27.3 upgrades; fresh install](gitea-1.0.27/upgrade-test.txt). 28.2.0 path has setup and pre-upgrade backup exceptions. | Pending colleague |

Firefox and Chromium chart updates are included in the base commit. Gitea 1.0.27 adds an upstream upgrade and read-only timezone mounts. Evidence is stored per application/version. Add future applications as separate commits and update this table; passing an upgrade test does not imply passing OAC. The colleague running OAC should record the checker version, policy, tested chart commit and results here.

No OAC rerun was performed for these handoffs, as requested. Existing Firefox evidence is preserved. No PR or merge is included.
