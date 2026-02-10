# PaddleOCR Client Chart

PaddleOCR 前端客户端 Helm Chart，用于在 Olares 系统中部署 PaddleOCR 前端界面。

## 概述

此 Chart 部署 PaddleOCR 前端应用，使用 `paddleocr-frontend` Docker 镜像。前端镜像已经包含了 Nginx 和前端静态文件，通过 ConfigMap 覆盖 Nginx 配置来代理后端 API 请求。

## 结构

```
paddleocr/
├── Chart.yaml              # Chart 元数据
├── values.yaml             # 默认配置值
├── templates/
│   ├── configmap.yaml     # Nginx 配置 ConfigMap
│   ├── deployment.yaml    # 前端 Deployment
│   └── service.yaml       # 前端 Service
└── README.md              # 本文档
```

## 配置说明

### values.yaml

主要配置项：

- `image.repository`: 前端镜像仓库（默认: `paddleocr-frontend`）
- `image.tag`: 镜像标签（默认: `latest`）
- `backend.service`: 后端服务名称（默认: `paddleocr-svc`）
- `backend.namespace`: 后端服务命名空间（默认: `paddleocr-server-shared`）
- `backend.port`: 后端服务端口（默认: `8080`）
- `replicas`: 副本数（默认: `1`）
- `resources`: 资源限制和请求

### Nginx 配置

Nginx 配置通过 ConfigMap 挂载，主要功能：

1. **前端静态文件服务**: 提供 React 前端应用
2. **API 代理**: `/api` 路径代理到后端服务
3. **CORS 支持**: 配置了 Olares 标准的 CORS 头
4. **PDF Worker 支持**: 正确配置了 PDF.js worker 文件的 MIME 类型
5. **健康检查**: `/health` 端点用于健康检查

## 部署说明

### 在 Olares 系统中

此 Chart 作为 `paddleocr` 应用的子 Chart 部署：

1. **主 Chart**: `paddleocr`
2. **子 Charts**:
   - `paddleocrserver` (shared: true) - 后端服务
   - `paddleocr` - 前端客户端（本 Chart，必须与主 Chart 同名）

### 入口配置

在 `OlaresManifest.yaml` 中配置了前端入口：

```yaml
entrances:
- name: paddleocr-client
  port: 80
  host: paddleocr-svc
  title: PaddleOCR Frontend
  authLevel: private
  openMethod: window
```

### 服务发现

前端通过 Kubernetes DNS 访问后端服务：
- 后端服务地址: `paddleocr-svc.paddleocr-server-shared:8080`
- 前端通过 `/api` 路径代理到后端

## 与 heygemv2 的对比

### 相同点

1. 都使用 ConfigMap 配置 Nginx
2. 都通过 Nginx 代理后端服务
3. 都配置了 CORS 支持
4. 都使用类似的资源限制

### 不同点

1. **镜像类型**:
   - `heygemv2`: 使用 `bitnami-openresty` 作为纯代理
   - `paddleocr`: 使用 `paddleocr-frontend` 镜像，包含前端静态文件

2. **配置方式**:
   - `heygemv2`: 使用 openresty 的 server_blocks 配置
   - `paddleocr`: 直接覆盖 nginx 的 default.conf

3. **端口**:
   - `heygemv2`: 监听 8080 端口
   - `paddleocr`: 监听 80 端口（前端标准端口）

## 注意事项

1. **后端服务依赖**: 前端依赖后端服务 `paddleocr-svc` 在 `paddleocr-server-shared` namespace 中运行

2. **镜像拉取**: 确保 `paddleocr-frontend` 镜像在集群中可访问

3. **资源限制**: 前端资源需求较小，但需要确保有足够的内存加载 PDF.js

4. **健康检查**: 使用 `/health` 端点进行健康检查，确保 Nginx 正常运行

## 更新日志

- v1.0.0: 初始版本，基于 heygemv2 客户端部分结构创建
