# OpenClaw image upgrades and recovery

Chart 1.0.48 pins OpenClaw 2026.9.8 (state schema 19, agent schema 24).
The CLI, Gateway and `init-openclaw-state` use the same image. The init container
runs upstream `doctor --fix --non-interactive` before application writers start.
Doctor may repair configuration as well as databases; inspect its report and keep
an application backup. This replaces the chart's legacy-file deletion and private
schema migration code. It does not delete a user's persistent npm installation.

## Normal upgrade

1. Make a verified application backup. For a live SQLite store, use the upstream
   backup workflow or stop all writers before taking a filesystem snapshot;
   copying only a live `.sqlite` file omits possible WAL contents.
2. Upgrade through Olares Market. Do not use `openclaw update` or install a second
   OpenClaw core with npm. `openclaw update status` remains available. Other global
   npm tools retain their existing PATH order. Explicit executable paths, shell
   aliases and user-written startup scripts can bypass the managed CLI and must
   be reviewed separately.
3. Check `init-openclaw-state` logs. Doctor refusal leaves initialization blocked;
   it is not silently ignored. Check the first refusal and its originating cause.
4. Verify the image version, Gateway readiness, real chat, and mobile WebSocket
   access. Test a Pod recreation before declaring recovery durable.

The image is the official multi-architecture GHCR release pinned by digest. No
custom OpenClaw image is built. Environments that require a registry mirror must
mirror that exact digest and validate both amd64 and arm64 before changing it.

## An installation already repaired to 19/24 with a temporary bridge

An ordinary chart update is the first recovery path. A bridge launched only inside
an old Pod ends when that Pod is replaced; the new image can read the repaired
schema, and there is no schema-23 init gate. Do not downgrade schema markers or
restore an old database over newer data just to make an old image start.

Before upgrading, identify how the temporary supervisor is launched. If it is
started by an external service, persisted shell startup file or another workload,
stop that specific supervisor and disable its restart mechanism in a maintenance
window. Stop all other processes writing this state, then back it up. Do not
blindly kill every Node.js process or delete `.npm-global` (it may contain other
tools). The chart deliberately does not guess which custom scripts are safe to
remove.

After replacement, run these read-only checks with the current namespace and Pod:

```bash
NS=clawdbot-YOUR_OLARES_ID
kubectl -n "$NS" get pods -l io.kompose.service=clawdbot
POD=REPLACE_WITH_CURRENT_POD_NAME
kubectl -n "$NS" logs "$POD" -c init-openclaw-state
kubectl -n "$NS" logs "$POD" -c gateway --tail=100
kubectl -n "$NS" exec "$POD" -c clawdbot -- /opt/olares/bin/openclaw --version
kubectl -n "$NS" exec "$POD" -c gateway -- /usr/local/bin/node /app/openclaw.mjs --version
```

Both versions should be 2026.9.8. The readiness probe also requires the Gateway
wrapper's child PID to exist inside its container, so a listener in a sibling
container cannot alone make a failed wrapper Ready. This is a health check, not
cryptographic process attestation.

Only after chat, pairing, restart and rescheduling checks pass, retire the bridge
files and any obsolete OpenClaw-specific npm installation. Retain the backup.

## If Doctor still refuses

Do not repeatedly run a newer npm CLI against the volume. Preserve the init logs,
including `stepId`, `refusal.code` and `originatingRefusal`. Do not remove lease
files, migration receipts or database version markers to force startup.

An administrator can stop all application/bridge writers and mount the same data
in an isolated maintenance container using **the chart's exact image**, uid/gid
1000, HOME `/home/node`, the same `OPENCLAW_STATE_DIR` and workspace variables, and
the same home/state/workspace/plugin mounts. With hostPath storage, pin that
container to the node holding those paths; do not allow it to create empty data
on another node. Run the following inside that maintenance container:

```bash
cd /app
/usr/local/bin/node /app/openclaw.mjs --version
/usr/local/bin/node /app/openclaw.mjs doctor --fix --non-interactive
```

Resolve the reported refusal rather than adding generic deletion or ownership
rewrites to the chart. Doctor owns backup, maintenance ownership and resumption.
After it exits successfully, stop the maintenance container and retry the chart
startup. When initialization is blocked, normal application containers are not
available for `kubectl exec`; use the separate maintenance container, not a loop
of exec attempts into an unstarted CLI container.

## Proxy attribution after rescheduling

Database recovery and HTTP 403 `proxy_attribution_required` are separate checks.
This patch does not add a reported Pod IP to every installation or expand trust
to arbitrary private networks. Existing configuration is retained.

Inspect the Gateway's actual socket peer and the forwarded header chain for each
entrance. The mobile Gateway entrance goes directly to port 18789, whereas
Control UI also passes through the chart's OpenResty. Fixing only OpenResty does
not fix the mobile entrance.

For the affected instance, edit `gateway.trustedProxies` to trust the verified
proxy hop(s), using a stable, constrained proxy CIDR only when the platform's
network policy and header handling enforce that boundary. Preserve custom trusted
entries. The ingress must overwrite or safely rebuild forwarded client headers.
A single reschedulable Pod IP is only a temporary diagnostic fix; do not present
it as durable. If the peer cannot be mapped to an enforced stable trust boundary,
resolve that in the platform/mesh routing before changing application trust.
Keep Gateway token authentication and normal device pairing enabled.

## Validation before release

Local checks:

```bash
node --test clawdbot/tests/startup.test.mjs
olares-cli chart lint ./clawdbot
```

Required runtime checks (use disposable copies, never a user's live databases):

- Fresh install; no model/provider needed for initial readiness.
- Verified 18/23 fixture -> Doctor -> 19/24; history and configuration retained.
- Already-current 19/24 fixture -> restart without the removed schema-23 gate.
- Interrupted migration -> explicit refusal or safe Doctor resumption.
- Persistent npm OpenClaw present -> normal CLI still runs bundled version.
- Wrapper failure while a sibling listens -> readiness remains false.
- Pod recreation, real model response and both ingress WebSocket paths.
- Revalidate Olares skills/local plugins after Doctor and repeat Doctor once.

Sources: [container entrypoint](https://github.com/openclaw/openclaw/blob/v2026.9.8/docker-entrypoint.mjs),
[Doctor migration contract](https://docs.openclaw.ai/cli/doctor/state-migrations),
[release notes](https://github.com/openclaw/openclaw/releases/tag/v2026.9.8).
