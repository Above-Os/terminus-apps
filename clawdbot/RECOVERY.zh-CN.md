# OpenClaw 升级与客户恢复

Chart 1.0.48 使用官方 Docker Hub 镜像
`docker.io/openclaw/openclaw:2026.9.9`。CLI、Gateway 和启动前的 Doctor
使用同一个版本，支持 state schema 19 / agent schema 24。

## 已由临时 2026.9.8 修复到 19/24 的实例

优先通过 Olares Market 更新 chart。新版本可读取该数据库格式，且已移除
只接受旧 schema 的自定义迁移。正常升级不需要重新安装 npm 版 OpenClaw。

1. 安排维护窗口，确认临时 bridge/supervisor 的启动位置。如果还有外部进程、
   其他 workload 或持久化启动文件会重新拉起 bridge，先停止并禁用**这一项**。
   不要批量终止 Node 进程，也不要删除整个 `.npm-global`。
2. 停止所有共享此状态目录的写入进程，再备份完整应用数据，包括 SQLite
   主文件和 WAL、配置、凭据及工作区。仅复制运行中的 `.sqlite` 主文件不可靠。
3. 通过 Market 更新。只存在于旧 Pod 中的临时进程会随 Pod 替换结束；
   chart 不会自动删除用户自建的脚本或 npm 包。
4. 检查新 Pod 的初始化日志和版本。以下命令在具有集群权限的管理终端执行，
   替换 namespace 与 Pod 名称：

```bash
NS=clawdbot-YOUR_OLARES_ID
kubectl -n "$NS" get pods -l io.kompose.service=clawdbot
POD=REPLACE_WITH_CURRENT_POD_NAME
kubectl -n "$NS" logs "$POD" -c init-openclaw-state
kubectl -n "$NS" logs "$POD" -c gateway --tail=100
kubectl -n "$NS" exec "$POD" -c clawdbot -- /opt/olares/bin/openclaw --version
kubectl -n "$NS" exec "$POD" -c gateway -- /usr/local/bin/node /app/openclaw.mjs --version
kubectl -n "$NS" get pod "$POD"
```

两处版本均应为 2026.9.9，初始化应成功，Gateway 应 Ready。
继续验证已有会话、真实模型回复和手机配对；在维护窗口通过 Market 重启应用，
并验证 Pod 替换后仍可连接。需要另行验证重新调度后的代理身份归属。
全部通过后，再删除已确认无用的 bridge 文件及对应 npm OpenClaw 包，保留备份。

## 初始化仍被 Doctor 阻止

先保存 `init-openclaw-state` 日志中的首个错误以及 `stepId`、`refusal.code`
和 `originatingRefusal`（如有）。不要删除迁移凭据、锁或 schema 标记来绕过检查，
也不要反复更换 npm 版本写入同一数据目录。

如果需要手动修复，由管理员停止应用及所有 bridge 写入者，用 **chart 的同一镜像**
创建独立维护容器，使用 uid/gid 1000，并挂载原有 home、state、工作区及插件目录。
保持与 chart 相同的环境变量；hostPath 数据必须在原数据所在节点上挂载，不能在
其他节点创建空目录冒充旧数据。具体挂载路径以该实例 Deployment 为准。

在维护容器内部执行：

```bash
cd /app
/usr/local/bin/node /app/openclaw.mjs --version
/usr/local/bin/node /app/openclaw.mjs doctor --fix --non-interactive
```

依据 Doctor 的具体拒绝原因修复。成功后停止维护容器，再恢复应用。
初始化失败时普通 CLI 容器尚未启动，不能对它反复尝试 `kubectl exec`。
六月以前的遗留状态不属于本次直接升级范围，届时根据用户实际状态提供桥接版本方案。

## 更新后仍出现代理身份归属 403

这与数据库迁移是两件事。先查看当前配置：

```bash
kubectl -n "$NS" exec "$POD" -c clawdbot -- \
  /opt/olares/bin/openclaw config get gateway.trustedProxies
```

由管理员确认实际 socket peer、入口代理和 Linkerd 的转发头处理，再在
`gateway.trustedProxies` 中保留原条目并加入经过验证的代理地址或受网络策略约束的
稳定代理网段。代理必须覆盖或安全重建客户端转发头。客户未提供实际网络拓扑，
因此这里不能给出一个可通用于所有实例的 CIDR。

不要使用 `0.0.0.0/0` 或整个私有地址空间来解除报错；单个 Pod IP 也不能作为
持久修复。若平台没有稳定且受约束的信任边界，应先修复入口/mesh 路径。
手机入口直接连接 Gateway，Control UI 还经过 OpenResty，需要分别验证。
保留 Gateway token 认证与设备配对。

测试范围与证据见 [迁移回归说明](tests/MIGRATION.md)。
