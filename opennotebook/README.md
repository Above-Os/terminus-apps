# Open Notebook 部署配置

本配置参考了 [open-notebook 官方 docker-compose 配置](https://github.com/lfnovo/open-notebook/blob/main/docker-compose.full.yml) 和 perplexica 项目的部署风格。

## 快速开始

1. **准备环境变量文件**
   ```bash
   cp docker.env.example docker.env
   # 编辑 docker.env 文件，填入必要的配置
   ```

2. **创建数据目录**
   ```bash
   mkdir -p surreal_data notebook_data notebook_config notebook_uploads
   ```

4. **启动服务**
   ```bash
   docker-compose up -d
   ```
   注意：Open Notebook 会自动等待 SurrealDB 健康检查和初始化容器完成后启动

5. **查看日志**
   ```bash
   docker-compose logs -f
   ```

## 服务说明

### SurrealDB
- **端口**: 8000
- **数据目录**: `./surreal_data`
- **默认用户**: root/root
- **数据库文件**: `/mydata/mydatabase.db`
- **资源限制**: CPU 1核 / 内存 512Mi
- **资源预留**: CPU 100m / 内存 128Mi

### Init Containers (初始化容器)
参考 perplexica 的结构，包含三个初始化容器：

1. **init-getconfigfile**
   - **镜像**: beclab/lfnovo-open-notebook:1.3.1
   - **功能**: 初始化配置文件
   - **配置目录**: `./notebook_config`

2. **init-seed-data**
   - **镜像**: beclab/lfnovo-open-notebook:1.3.1
   - **功能**: 初始化数据库种子数据（如果存在）
   - **数据目录**: `./notebook_data`

3. **init-chmod-data**
   - **镜像**: busybox:1.37
   - **功能**: 设置目录权限（chown 1000:1000）
   - **目录**: `./notebook_data`, `./notebook_config`, `./notebook_uploads`
   - **运行用户**: root (user: 0)

### Open Notebook
- **镜像**: beclab/lfnovo-open-notebook:1.3.1
- **Web UI 端口**: 8502
- **API 端口**: 5055
- **数据目录**: `./notebook_data`
- **配置目录**: `./notebook_config`
- **环境变量**: 从 `docker.env` 文件加载
- **资源限制**: CPU 2核 / 内存 2048Mi
- **资源预留**: CPU 50m / 内存 8Mi

## 配置说明

### 数据持久化
参考 perplexica 的卷挂载结构：
- SurrealDB 数据存储在 `./surreal_data` 目录
- Notebook 数据存储在 `./notebook_data` 目录
- Notebook 配置存储在 `./notebook_config` 目录
- Notebook 上传文件存储在 `./notebook_uploads` 目录
- 初始化容器会自动设置目录权限（1000:1000）
- 确保这些目录有适当的权限

### 网络配置
- 所有服务连接到 `opennotebook-network` 网络
- 服务间可以通过服务名进行通信

### 健康检查
- SurrealDB 和 Open Notebook 都配置了健康检查
- Open Notebook 会等待 SurrealDB 健康后再启动
- 初始化容器会在应用启动前按顺序完成：
  1. 配置文件初始化
  2. 数据库种子数据初始化
  3. 目录权限设置

### 资源限制
- 参考 perplexica 项目的资源分配策略
- SurrealDB: 限制 1核/512Mi，预留 100m/128Mi
- Open Notebook: 限制 2核/2048Mi，预留 50m/8Mi

## 停止服务

```bash
docker-compose down
```

## 清理数据（谨慎操作）

```bash
docker-compose down -v
# 这会删除所有卷数据
```

