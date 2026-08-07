# OpenClaw（Olares）首次 Onboarding 与 Skills 依赖说明

本文档说明 **经典 Onboarding** 过程中，Skills 依赖安装**可能失败或耗时很长**的原因，以及用户可自行尝试的处理办法。

适用：Olares 市场版 **OpenClaw（clawdbot）**，通过 **OpenClaw CLI** 或 Control UI 完成首次引导。

---

## 背景

OpenClaw 上游在经典 Onboarding 中会**批量安装**官方 Skills 及其系统依赖（多数通过 **Linuxbrew / Homebrew** 安装 CLI 工具，如 `go`、`gh`、`uv`、`1password-cli` 等）。

在 Olares 容器环境里，这会遇到几类限制：

1. **网络**：拉取 GitHub、ghcr.io、Homebrew bottle 时可能 TLS 超时、checksum 不一致（多为链路不稳定，非 chart 配置错误）。
2. **并发**：Onboarding 会**并行**触发多个 `brew install`，容易出现 download lock 冲突（`*.incomplete` 文件被锁）。
3. **第三方 Tap**：部分 Skills 依赖 `steipete/tap`；Homebrew 4.x 要求 **tap trust**，未信任时会直接失败。
4. **基础工具缺失**：例如 `1password-cli` cask 解压需要 **`unzip`**，若 PATH 中找不到会报 `unzip: No such file or directory`。

Olares chart 已在 brew-base 镜像与 init 中尽量缓解（预装 `unzip`、init 信任 `steipete/tap`），但**无法保证** Onboarding 期间所有上游 Skills 依赖一次装成功——尤其在外网不稳定时。

**重要：Skills 安装失败通常不阻止 Gateway 核心功能。** 你可以先完成 Onboarding 的主流程（模型、Gateway Token、渠道），日后再按需安装单个 Skill。

---

## 常见报错与处理

### 1. `unzip: No such file or directory`（如 1password-cli）

**原因**：Skill 安装脚本调用 `unzip`，但运行时 PATH 中无该命令。

**处理（chart 1.0.21+ / brew-base 2026.8.7-2-cli 起已预装）**：

```bash
which unzip
# 应能找到；若没有：
brew install unzip
```

升级 chart 后若 brew volume 很旧，重启 Pod 让 init 刷新 brew-base，或手动 `brew install unzip`。

---

### 2. `brew install go` / download **already locked**（exit 124）

**原因**：多个 Skill 同时 `brew install`，争抢同一 cache 文件。

**处理**：

```bash
# 等待 2–5 分钟让进行中的 brew 结束；仍卡住则：
pkill -f "brew install" 2>/dev/null || true
rm -f /home/node/.cache/Homebrew/downloads/*.incomplete
```

然后**不要立刻重跑整段 Onboarding**；在 CLI 中逐个重试失败的 Skill，或运行：

```bash
openclaw doctor
```

---

### 3. `steipete/tap` **not trusted**

**原因**：Homebrew 4.x 默认不信任第三方 tap。

**处理**：

```bash
brew trust steipete/tap
```

Chart 1.0.22+ 的 init 会尝试预先 trust；若 volume 在升级前已存在，手动执行一次即可。

---

### 4. Git / TLS / SSL 错误（clone tap、下载 bottle 失败）

示例：

```text
GnuTLS recv error (-110): The TLS connection was non-properly terminated
curl: (35) OpenSSL SSL_connect: SSL_ERROR_SYSCALL
Failed to download resource "fmt"
Bottle reports different checksum
```

**原因**：多为**外网不稳定**或 CDN 中断；偶发 checksum 不一致也可能是下载不完整。

**处理**：

```bash
# 清理不完整下载后重试
rm -f /home/node/.cache/Homebrew/downloads/*.incomplete
brew cleanup -s
# 单独重试某一个 formula，例如：
brew install go
brew install gh
```

若 Olares 节点外网受限，需管理员检查出口网络或配置代理；**这不是 OpenClaw 应用本身能单独修复的**。

---

### 5. 某 Skill 显示 Install failed，但 Onboarding 继续

**预期行为**：上游 Onboarding **允许**部分 Skill 依赖失败并继续；失败项可之后再装。

**建议**：

```bash
openclaw doctor          # 查看 skills + requirements 状态
openclaw skills list     # 列出已装 skills（如 CLI 支持）
```

仅当你**确实需要**某个 Skill 时，再单独安装其依赖，不必在首次 Onboarding 追求「全部绿色」。

---

## 推荐首次安装策略（Olares）

1. **先完成核心配置**：模型 Provider、Gateway Token、至少一个消息渠道（Telegram 等）。
2. **Skills 批量安装失败可跳过**：不影响基本对话与 Gateway。
3. **外网不好时**：避免反复重跑 Onboarding；网络稳定后再 `openclaw doctor` 或手动 `brew install`。
4. **容器内重启 Gateway** 用 `restart-gateway`，不要用 `openclaw gateway restart`。

---

## Chart 侧已做的缓解（1.0.21+）

| 措施 | 说明 |
|------|------|
| brew-base 预装 `unzip` | apt + `brew install unzip`，减少 1password-cli 等 cask 失败 |
| brew-base 预 trust + tap `steipete/tap` | 构建时写入 brew volume 模板，减少 Onboarding 时 clone/trust 失败 |
| init 信任 `steipete/tap` | 旧 brew volume 升级时的兜底（新装以镜像 bake 为主） |
| PATH 优先 Linuxbrew | 含 `opt/unzip/bin`，brew 工具优先可见 |
| OpenClaw **v2026.7.1-1** | 上游修复 Memory Core 启动循环、managed plugin npm lock 等 |

升级 chart **前**需构建并推送 brew-base：`clawdbot/docker/Dockerfile.brew-base-cli` → `beclab/harveyff-openclaw-brew-base:2026.8.7-2-cli`。

---

## 参考

- OpenClaw Skills 文档：https://docs.openclaw.ai/skills
- 上游 v2026.7.1-1：https://github.com/openclaw/openclaw/releases/tag/v2026.7.1-1

---

*文档维护：Olares OpenClaw 打包团队。*
