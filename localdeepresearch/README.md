# Local Deep Research on Olares

This Chart runs Local Deep Research 1.10.7 with persistent application storage. AI Router and SearXNG v3 are required. The Router dependency uses its Market Chart version, not the upstream gateway program version.

## Setup

1. Configure a callable chat model in AI Router.
2. Copy the SearXNG HTTPS entrance URL from Olares Settings and provide it as `SEARXNG_URL`, without `/search`.
3. Open the application and register an application account. Keep the password safe: the encrypted account database has no password recovery.
4. Enter a question and choose a research mode.

The default model is Router's `default-chat` route. To select a specific model, set `LDR_LLM_MODEL` to a name returned by Router's OpenAI-compatible `/v1/models` endpoint. A failed cloud provider credential must be repaired in Router, or a callable model can be selected explicitly for this application.

Leave `LDR_LLM_OPENAI_ENDPOINT_URL` and `LDR_LLM_OPENAI_ENDPOINT_API_KEY` blank to use the installing user's Router endpoint without an application API key. For another OpenAI-compatible service, supply its base URL including `/v1`, model name and optional API key in application environment settings. The Chart injects a supplied key through a Kubernetes Secret.

## Storage and validation

Application data uses app-private persistent storage. The main process runs as UID/GID 1000, with one replica and Recreate deployment strategy. Uninstalling without deleting application data preserves encrypted account databases; users may need to log in again after restarting or reinstalling.

Chart 0.0.12 was verified on Olares 1.12.7 amd64 by uninstalling without deleting data and reinstalling, logging in with the previous account, opening the library, completing a Quick Summary with local Qwen through Router and SearXNG, checking saved history, and exporting readable PDF and Markdown reports. Both image architectures are available; arm64 runtime and the full set of research modes have not been exhaustively tested.
