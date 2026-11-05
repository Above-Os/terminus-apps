# Official Cognee MCP

The chart runs the official `cognee/cognee-mcp` image in API mode against the backend in the same Pod. Cognee backend and UI use `1.6.6`. MCP uses the explicit `main-df2b4fa` tag, matching the upstream v1.6.6 release commit. Its package version is separate from the backend version.

Create a Cognee API key for the account whose datasets the assistant should use. Set it as the app's editable `MCP_API_KEY` environment variable in Olares Settings, then apply the change. An empty value disables MCP entrance access. Existing account passwords and knowledge storage are preserved.

Find the `mcp` entrance using `olares-cli settings apps get cognee -o json`. The connection URL is its HTTPS origin plus `/mcp`. In Lares settings, select MCP and Add server, select Streamable HTTP, and set Headers to `{"X-Api-Key":"<the-same-key>"}`. Use the same URL and header for Hermes Agent.

The official MCP process connects with one fixed API identity. The entrance requires that exact configured key, rather than accepting another account's valid API key. The process binds loopback, and the authenticated proxy exposes only `/mcp`. A missing key returns 401, a mismatched key returns 403, and unrelated paths return 404. Backend permissions still apply. Rotate the key in both the app environment and clients.

The official tool surface includes `remember`, `recall` and `forget`. This is not a read-only server. Specify dataset names and review requested operations before approving them.

The standalone `cognee-mcp.cjs` is retained as a legacy read-only stdio adapter. The official HTTP connection does not require that adapter, Node.js or an uploaded private configuration file.
