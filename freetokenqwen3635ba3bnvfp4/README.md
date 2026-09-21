# FreeToken Qwen3.6 NVFP4 chart

`templates/wrappers.yaml` 的 ConfigMap 直接包含 `freetoken.sh`、
`freetoken-healthcheck.py` 和 `prepare-ftw.py`，统一挂载到 `/llm-init/wrappers`。
编辑该模板即可修改脚本，chart 不再使用独立的 `files/*.py` 文件。

## 启动和健康检查

FreeToken 的 `/v1/models` 只表示模型已登记；`/health` 在加载或出错时也会返回
HTTP 200。因此三个 Kubernetes 探针都执行 chart 下发的
`/llm-init/wrappers/freetoken-healthcheck.py`，解析 JSON。
该脚本与 `deploy/freetoken/healthcheck.py` 保持一致，升级 chart 即可更新，
不依赖镜像中旧版 Docker HEALTHCHECK 脚本：

| 探针 | 成功条件 | 周期 / 超时 / 连续失败次数 |
| --- | --- | --- |
| startup | `status=ok` 且 `maintenance=serving` | 10s / 5s / 8640 |
| readiness | 同上 | 5s / 5s / 1 |
| liveness | `--live`：`status=loading` 或 `ok`，且 `maintenance` 不是 `failed` | 30s / 5s / 10 |

startup 为首次下载、FTW 转换和加载提供最多 24 小时，期间不执行 liveness。
探针失败时输出 status、maintenance 和 phase，便于从 Pod 事件定位。
readiness 不通过时，`sglang` Service 不向这个 Pod 转发流量。llm-init 的
`/livez` 探针保留，使 Model Console 在引擎准备期间仍可访问。
liveness 为 Model Console 触发的进程重启预留约 5 分钟；如更换量化后端导致
重新转换超过此时间，应重启整个 Pod，以重新获得完整 startup 等待窗口。

## FTW 缓存

`freetoken.ftw.enabled: true` 默认启用。包装脚本等待下载完成后，使用镜像内的
官方 `ft checkpoint --model <HF snapshot> --out <temporary directory>
--moe-backend offload`，成功后用 FTW 目录启动 `ft serve`。
原始 HF 缓存只读，不会被覆盖。转换与推理顺序运行，不会同时驻留两套专家 bank。

- 输出保存在 `appCache/freetoken-ftw`，容器重建后保留；需额外约一份模型的磁盘空间。
- 缓存按源文件版本、FreeToken 实现、GPU compute capability、dtype 和
  `--quant-backend` 区分。上下文长度、KV 和并发参数变化不触发重新转换。
- 转换先写 `.partial`，检查索引和所有分片长度，再写完成标记并重命名。
  转换失败时不会继续提供服务；重试会清理同一缓存键的半成品。
- 0.1.3 的转换器通过 layer sink 写出并释放每层专家；其 CLI 没有
  `--expert-load` 参数。serve 阶段仍保留 `--expert-load serial`，FTW 自动走快速路径。
- `OMP_NUM_THREADS` 和 `MKL_NUM_THREADS` 默认都是 4，可通过
  `freetoken.cpuThreads` 修改。它们同时影响首次转换和启动。
- 设 `freetoken.ftw.enabled: false` 可回退到原始 HF checkpoint。
  该开关不删除已有 FTW；不同版本的旧缓存也不会自动删除。

Chart 的 `checksum/wrappers` 保证脚本更新会重建引擎 Pod。

参考：[FreeToken CLI](https://github.com/FlashML-org/FreeToken/blob/main/docs/cli.md#ft-checkpoint)、
[转换实现](https://github.com/FlashML-org/FreeToken/blob/main/python/freetoken/checkpoint/convert.py)、
[Kubernetes 探针](https://kubernetes.io/docs/concepts/workloads/pods/probes/)。
