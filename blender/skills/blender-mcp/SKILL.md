---
name: blender-mcp
description: Drive the Olares Blender agent session via ahujasid/blender-mcp.
---

# Blender MCP (Olares)

The browser-visible Blender loads the upstream
[blender-mcp](https://github.com/ahujasid/blender-mcp) addon. Agents and the
Selkies UI operate on the same live Blender scene. Save work under `Home` so
it remains visible in Olares Files and survives app restarts.

The addon socket is `127.0.0.1:9876` (no auth — not exposed). HTTP/SSE is
published through one internal entrance, `blendermcp` (Service `blendermcp`
port 8765). It is marked invisible because an SSE stream is not a web page.

The browser GUI is the app's primary private entrance (`blender` :3000).

## From another Olares app

Use the MCP entrance URL shown by `olares-cli settings apps get blender`:

`https://<mcp-entrance-hash>.<user>.olares.com/sse`

## From Codex / OpenCode / Hermes on your laptop

Keep 9876 private. Forward only the SSE port, then point the client at localhost.

```bash
olares-cli profile use olarestest01@olares.com
olares-cli cluster pod list | findstr blender
# then kubectl/olares port-forward the blender pod 8765:8765
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.blender]
url = "http://127.0.0.1:8765/sse"
```

OpenCode:

```json
{
  "mcp": {
    "blender": {
      "type": "remote",
      "url": "http://127.0.0.1:8765/sse",
      "enabled": true
    }
  }
}
```

Hermes still expects stdio `uvx blender-mcp` against `localhost:9876`. Either
use the SSE URL if your Hermes build supports remote MCP, or port-forward 9876
only on a trusted local machine and run `hermes mcp install blender`.

Do not expose 9876 to the network. Enable `BLENDER_MCP_SAFE_MODE=1` is already
set on the in-cluster MCP server.
