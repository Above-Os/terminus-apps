# Apps pending OAC review

Shared staging branch: `codex/pending-oac-20261113`.

| App | Chart | Upgrade validation | OAC |
| --- | --- | --- | --- |
| Firefox | 1.0.20 | [Passed scoped checks](firefox-1.0.20/upgrade-test.txt) | Pending colleague |
| Chromium | 1.0.18 | [Passed scoped checks](chromium-1.0.18/upgrade-test.txt); Restore pages click needed | Pending colleague |

Both chart updates are included in the base commit. Evidence is stored per application/version. Add future applications as separate commits and update this table; passing an upgrade test does not imply passing OAC. The colleague running OAC should record the checker version, policy, tested chart commit and results here.

No OAC rerun was performed for this Chromium handoff, as requested. Existing Firefox evidence is preserved. No PR or merge is included.
