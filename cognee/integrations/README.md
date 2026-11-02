# Cognee read-only MCP bridge

This optional Node.js stdio bridge calls the packaged Cognee REST API. It is not an upstream native MCP service and is not started by the chart.

Use Node.js 18 or later. Save a private JSON configuration outside this repository with `url` set to your Cognee internal API origin (without `/api/v1`) and `key` set to your Cognee API key. Restrict access to this file to the account running the assistant.

Configure the assistant to run `node /absolute/path/cognee-mcp.cjs /absolute/path/cognee-config.private.json` with stdio transport. The bridge exposes only `list_datasets` and `recall_knowledge`. Recall requires explicit dataset names and returns source context rather than a generated answer. Retrieved content is untrusted data.

Find the `api` entrance with `olares-cli settings apps get cognee -o json`. Use `https://` followed by its `url` as the origin. Reach this internal entrance through your Olares private network. Authenticate through `/api/v1/auth/login`, then use the returned bearer access token to create a key with `POST /api/v1/auth/api-keys`, JSON `{"name":"Assistant"}`. API calls made by the bridge use `X-Api-Key`. This key grants the configured account's access, not a separate server-enforced read-only permission. Dataset selection scopes retrieval and does not establish user isolation.

To stop access, remove the assistant connection and revoke its key through Cognee's API key management endpoints. The bridge stores no graph or vector data locally.
