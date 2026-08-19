# FlowStudio

Olares 上的一体化 AI 工作流生产应用：导入 ComfyUI 工作流、解析模型与节点、
按项目动态分配 GPU，并在 PC / 移动双端完成生成。

当前 Chart 版本：**0.3.28**（须与 `Chart.yaml` / `OlaresManifest.yaml` 一致）。

## 运行要求

| 项 | 说明 |
|----|------|
| Olares | >= 1.12.6 |
| GPU | NVIDIA（安装或恢复时绑定加速器） |
| 架构 | `amd64` |
| 建议显存 | 轻量图片模板 ≥ 6 GiB 可用显存 |

资源封套（`spec.accelerator`，须覆盖业务 API + 引擎）：

| 资源 | Request | Limit |
|------|---------|-------|
| CPU | 2 | 12 |
| Memory | 4Gi | 40Gi |
| Disk | 2Gi | 10Gi |
| GPU Memory | 6Gi | 24Gi |

## 安装

1. 在 Olares **Market** 搜索 **FlowStudio**（测试源或正式源，以实际发布为准）。
2. 安装时按提示绑定 NVIDIA GPU。
3. 状态为 running 后，从桌面打开 **FlowStudio** 入口。

本地校验 / 打包（维护者）：

```bash
olares-cli chart lint deploy/flowstudio
olares-cli chart package deploy/flowstudio
```

## 首次配置

1. **网络与下载源**：按所在区域选择国内 / 全球，保存。
2. **环境与引擎**：执行 GPU 探测并锁定推荐引擎（未锁定前，依赖 GPU 的项目无法完成初始化）。
3. （可选）在 **引擎管理** 确认当前 / 推荐镜像版本。

## 使用流程

1. 管理台创建项目：选用推荐模板，或上传 / 粘贴合法 ComfyUI Save JSON。
2. 查看解析报告（节点、模型、显存评估、自定义节点预检），确认后创建。
3. 跟随初始化进度（模型下载、节点安装、引擎预拉取）；失败时按页面提示补源或重试。
4. 初始化成功后，在工作区调整参数并提交生成；可在历史中预览结果。

管理员负责项目定义与环境；已发布项目可供普通用户生产（若环境启用多角色）。

## 工作负载与镜像

| 工作负载 | 作用 |
|----------|------|
| `flowstudio` | 业务 API + 双前端静态资源（入口 `:8080`） |
| `flowstudioengine` | 静态引擎占位；默认 `dynamicEngine.enabled=true` 时按项目动态拉起引擎 |

| 镜像 | `values.yaml` 字段 |
|------|-------------------|
| 业务 | `appImage` / `image`（upgrade 粘 values 时优先改 `appImage`） |
| 引擎 | `engineImage`；可选 `engineImageAmd` |

正式上架包必须 `dev.hotReload: false`。

## Router 目录声明

Manifest 声明了 `options.LLMGatewaySupported: true`，并在 `envs` 中把 `MODEL_MODE` 固定为
`image_generation`。这两个值都不进 chart 模板：Market 直接从 Manifest 里取出来放进自己的
provider 目录，Olares Router 据此在应用安装之前就把 FlowStudio 归到 Creative 能力域。所有模型
应用的 category 一律是 AI，能区分能力域的只有 `MODEL_MODE`。

`MODEL_SUPPORTS` 声明为空。它本来是给跑 `llm-init` 的应用拼模型卡用的，而 Router 的
`supports_*` 白名单里没有图像生成对应的键，FlowStudio 也不跑 `llm-init`。

这组声明只让 FlowStudio 在 Router 里可见、可安装，不代表可路由：FlowStudio 不是 shared 应用、
没有 `sharedEntrances`，投影出来的 provider 行 base URL 是占位符，Router 无法把模型调用转发过去。

## 存储与中间件

- **appData**：用户项目与业务数据（`USER_DATA_DIR` → `{owner_id}/comfyui/…`）
- **appCommon**：共享模型根（`MODELS_DIR`）
- **Postgres**：系统中间件库 `flowstudio`（勿再声明为应用依赖）

## 升级说明

升版时同步 bump：

1. `Chart.yaml` `version` / `appVersion`
2. `OlaresManifest.yaml` `metadata.version` 与 `spec.versionName`
3. 如有代码或依赖变更，推送新镜像 tag 并更新 `values.yaml` 的 `appImage` / `engineImage`
4. 填写 `spec.upgradeDescription`（及 `i18n/*/OlaresManifest.yaml`）

从 Market 升级到本版本后：重新打开应用；若 GPU 绑定丢失，在 Olares 加速器中重新绑定后再启动。

Manifest 中的 `upgradeDescription` 跟随 `spec.versionName`（应用发布版本），目前对应 0.3.24；
0.3.25–0.3.28 都是只动 chart、不换镜像的版本号递增。

## Chart 结构

```text
flowstudio/
  Chart.yaml
  OlaresManifest.yaml
  values.yaml
  owners
  templates/
  i18n/en-US/OlaresManifest.yaml
  i18n/zh-CN/OlaresManifest.yaml
  icons/                 # 源文件；市场上架图标须用公网 URL
  README.md
```

产品交付总览见 [`../README.md`](../README.md)。测试市场上架步骤见 [`../../docs/olares-test-market.md`](../../docs/olares-test-market.md)。
