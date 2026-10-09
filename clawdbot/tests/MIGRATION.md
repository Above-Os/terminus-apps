# OpenClaw migration regression

Target: **2026.9.9**, state schema **19**, agent schema **24**.
The chart runs the bundled `doctor --fix --non-interactive` once per Pod
initialization, before Gateway and CLI writers start. It contains no private
SQLite migration implementation or hard-coded source-schema gate.

## Release coverage

The three-month window is July 9 through October 9, 2026. Include the release
already active at the beginning of the window. The published chart manifests
and actual image tags, not commit titles, define the source runtime.
[Exact release commits](migration-versions.json) are recorded separately.

| Olares chart | Actual runtime | Source state / agent schema | Target |
| --- | --- | --- | --- |
| 1.0.15 / 1.0.19 | 2026.6.9 | 1 / legacy JSON sessions | 19 / 24 |
| 1.0.20 | 2026.7.1 | 1 / legacy JSON sessions | 19 / 24 |
| 1.0.21 | 2026.7.1-1 | 1 / legacy JSON sessions | 19 / 24 |
| 1.0.36 | 2026.9.1 | 15 / 19 | 19 / 24 |
| 1.0.44 | 2026.9.5 | 17 / 21 | 19 / 24 |
| 1.0.47 | 2026.9.6 | 18 / 23 | 19 / 24 |
| Current-state repeat | 2026.9.9 | 19 / 24 | 19 / 24 |

Chart 1.0.36's commit title mentions 2026.8.2, but its manifest and deployment
actually package 2026.9.1. Pre-June legacy state is outside this direct-upgrade
scope. Handle such cases individually; do not remove receipts or decrease
schema versions to force a downgrade.

## Reproduce the native-runtime matrix

Requirements: Python 3, npm and an upstream-supported Node version (tested with
Node 24.19 on macOS arm64). Use a disposable directory with several GB free.
The loopback model fixture never calls a real model provider. Each source
runtime creates its own databases and a real session through the agent command;
the test does not fabricate an old schema using SQL.

```bash
TEST_ROOT=$(mktemp -d)
for version in 2026.6.9 2026.7.1 2026.7.1-1 2026.9.1 2026.9.5 2026.9.6 2026.9.9; do
  npm install --prefix "$TEST_ROOT/runtime-$version" "openclaw@$version" \
    --ignore-scripts --no-audit --no-fund || exit 1
done
python3 clawdbot/tests/migration-native.py --root "$TEST_ROOT" \
  2026.6.9 2026.7.1 2026.7.1-1 2026.9.1 2026.9.5 2026.9.6 2026.9.9
```

For each source, the harness checks:

- SQLite integrity and foreign keys, including any retained WAL. Inspection
  copies the database and its sidecars after all writers exit, then opens the
  copy normally; immutable mode must not silently ignore WAL.
- Direct Doctor upgrade to state 19 / agent 24.
- Original user and assistant messages in the model request after upgrade.
- Workspace marker, Gateway token and provider configuration retention.
- A second Doctor invocation succeeds with unchanged schema versions.

Logs, pre-upgrade backups and the machine-readable `native-results.json` remain
in the disposable directory. Do not run against customer data or commit those
artifacts. Install scripts are intentionally disabled; this exercises the
published JavaScript runtime and Node's built-in SQLite, not optional native
extensions or the Linux image entrypoint.

## Local results (2026-10-09)

See [the recorded results](migration-results.json) for the completed native
matrix. Every listed source reaches 19/24 and retains the tested session,
workspace and configuration. These are generated fixtures, not customer data.

Additional isolated checks passed:

- Start the migrated 2026.6.9 fixture with 2026.9.9 Gateway, stop it and start
  again: authenticated `/readyz` returns HTTP 200 on both starts.
- On separate disposable copies, set the state schema to an unsupported future
  value, or replace its contents with invalid bytes: Doctor returns nonzero and
  leaves that database's SHA-256 unchanged. These are refusal tests, not actual
  interrupted-migration recovery tests.
- All five `startup.test.mjs` regressions, chart lint and seven-locale manifest
  validation pass.

## Release gate

Native tests supplement, but do not replace, deployment validation. Before
publishing, use disposable Olares data to check official Docker Hub image pulls,
fresh installation, upgrade with real Olares plugins/skills, real model chat,
both WebSocket entrances, Pod recreation and rescheduling. Also exercise an
interrupted migration and its supported Doctor resumption/refusal. A generated
healthy fixture does not reproduce the customer's unknown interruption point.

Do not mark these cluster checks passed merely because native migration or
`chart lint` succeeds. Keep the PR draft until the required cluster checks pass.
