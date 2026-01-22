# LibreChat Helm Chart

This Helm chart deploys LibreChat, an enhanced ChatGPT clone with support for multiple AI models, agents, MCP, and more.

## Overview

LibreChat is an open-source ChatGPT alternative that supports:
- Multiple AI providers (OpenAI, Anthropic, AWS Bedrock, Azure, Google, Vertex AI, custom endpoints)
- Agents & Tools integration
- Code Interpreter with secure sandboxed execution
- Web Search capabilities
- Image generation (DALL-E, Stable Diffusion, Flux)
- Multimodal support (image analysis with Claude, GPT-4, Gemini)
- Multi-user authentication (OAuth2, LDAP, Email)
- Message and conversation search

## Architecture

This chart deploys:
- **LibreChat API**: Node.js service handling AI requests, authentication, and integrations
- **MongoDB**: Document database for conversations, messages, and user data
- **MeiliSearch**: Fast search engine for message and conversation search

**Network Architecture**:
- All services are exposed as ClusterIP (internal only)
- No Nginx or reverse proxy included - relies on your existing gateway/ingress controller
- SSL/TLS termination and domain routing should be configured in your gateway
- Service port: `librechat:3080` (default)

## Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- Olares platform (for Olares-specific features)

## Installation

### Basic Installation

```bash
helm install librechat ./librechat
```

### Custom Configuration

Create a `values-custom.yaml` file:

```yaml
api:
  image: "ghcr.io/danny-avila/librechat:latest"
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "4"
      memory: "8Gi"

mongodb:
  persistence:
    enabled: true
    size: "20Gi"

env:
  OPENAI_API_KEY: "your-openai-key"
  ANTHROPIC_API_KEY: "your-anthropic-key"
  ALLOW_REGISTRATION: "true"
```

Then install:

```bash
helm install librechat ./librechat -f values-custom.yaml
```

## Configuration

### Environment Variables

Key environment variables can be configured in `values.yaml`:

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `GOOGLE_API_KEY`: Google API key
- `MONGO_URI`: MongoDB connection string (if using external MongoDB)
- `MEILI_MASTER_KEY`: MeiliSearch master key (auto-generated if not provided)

### Custom Endpoints

To configure custom AI endpoints, edit the ConfigMap `librechat-config` or modify the `librechat.yaml` in the deployment template.

Example custom endpoint configuration:

```yaml
endpoints:
  custom:
    - name: "Ollama"
      apiKey: "ollama"
      baseURL: "http://ollama-service:11434/v1/"
      models:
        default: ["llama3:latest"]
        fetch: true
```

### MongoDB Configuration

- Default username: `admin`
- Password: Auto-generated if not specified in `values.yaml`
- Data persistence: Enabled by default, stored in `{{ userspace.appData }}/librechat/mongodb`

### MeiliSearch Configuration

- Master key: Auto-generated if not specified
- Data persistence: Enabled by default, stored in `{{ userspace.appData }}/librechat/meilisearch`

## Access

After installation, LibreChat will be available at:
- Internal service: `librechat:3080`
- Frontend (via gateway): Configured through your existing gateway/ingress controller

**Note**: This chart does not include Nginx or any reverse proxy. SSL/TLS termination and domain routing are handled by your existing gateway infrastructure. The service is exposed as ClusterIP and should be configured in your gateway/ingress controller to route traffic to the `librechat` service on port 3080.

## Upgrading

```bash
helm upgrade librechat ./librechat
```

## Uninstallation

```bash
helm uninstall librechat
```

**Note**: This will delete all data unless you have external persistence configured.

## Persistence

Data is persisted to host paths:
- MongoDB: `{{ userspace.appData }}/librechat/mongodb`
- MeiliSearch: `{{ userspace.appData }}/librechat/meilisearch`
- LibreChat data: `{{ userspace.appData }}/librechat/data`

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -l app=librechat
```

### View Logs

```bash
# LibreChat API logs
kubectl logs -l app=librechat,component=api

# MongoDB logs
kubectl logs -l app=librechat,component=mongodb

# MeiliSearch logs
kubectl logs -l app=librechat,component=meilisearch
```

### Check Services

```bash
kubectl get svc -l app=librechat
```

### Access MongoDB Shell

```bash
kubectl exec -it $(kubectl get pod -l app=librechat,component=mongodb -o jsonpath='{.items[0].metadata.name}') -- mongosh -u admin -p
```

## References

- [LibreChat GitHub](https://github.com/danny-avila/LibreChat)
- [LibreChat Documentation](https://librechat.ai/docs)
- [LibreChat Docker Setup](https://librechat.ai/docs/local/docker)

## License

MIT License - See [LibreChat License](https://github.com/danny-avila/LibreChat/blob/main/LICENSE)

