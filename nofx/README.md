# NOFX (Olares)

Olares 应用包（Chart、OlaresManifest、Deployment/Service）。  
Docker 镜像在 **nofx 源码仓库** 中构建并推送到 Docker Hub（默认 `docker.io/goai007/nofx`），见该仓库 `scripts/docker-build-push-goai007.sh` 与 `docker/Dockerfile.olares`。

## 分工

| 位置 | 用途 |
|------|------|
| **nofx 仓库** | 源码、`docker/Dockerfile.olares`、一键构建推送脚本 |
| **本目录** | Olares：`values.yaml` 中配置要拉取的镜像与 tag |

## 构建并推送镜像（在 nofx 仓库根目录）

```bash
cd /path/to/nofx
docker login
./scripts/docker-build-push-goai007.sh
# 或指定 tag：TAG=1.0.0 ./scripts/docker-build-push-goai007.sh
```

## 与 Olares 中的版本对齐

推送新镜像后，将 **values.yaml** 中的 `image.tag` 改为与推送 tag 一致；必要时更新 **Chart.yaml** / **OlaresManifest.yaml** 中的 `appVersion`、`metadata.version`。

## 数据

SQLite 与运行数据使用 `DB_PATH=/app/data/data.db`，持久化目录为 `userspace.appData/{{ Release.Name }}/nofx`，在容器内为 `/app/data`。
