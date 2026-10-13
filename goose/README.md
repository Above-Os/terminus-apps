# Goose on Olares

This chart runs the Goose ACP backend. Install the matching native Goose Desktop client on your computer; the Olares app does not stream a Linux desktop.

## Connect

1. Find the Goose ACP entrance URL in Olares Settings.
2. Open the Goose Terminal entrance. Run `printenv GOOSE_SERVER__SECRET_KEY` and copy the key privately.
3. In Goose Desktop, open Settings > goose Server. Enable the external server, enter its HTTPS URL and secret key, and set the remote working directory to `/config/workspace`.
4. Configure a model through the connected Desktop client or the Olares app environment settings.

The internal ACP entrance (gooseapi) uses Goose authentication and accepts HTTP/WebSocket through the Olares HTTPS proxy. It does not require a browser login. Network reachability follows the Olares VPN configuration. Do not disable Goose authentication: the official Desktop connection check expects an authenticated endpoint.

## Model configuration

For OpenAI-compatible APIs, use `GOOSE_PROVIDER=openai`, `GOOSE_MODEL`, `OPENAI_HOST` (server root without `/v1`), `OPENAI_BASE_PATH=v1/chat/completions`, and `OPENAI_API_KEY`. Do not use `OPENAI_BASE_URL`.

Credentials supplied in Olares settings are rendered into Kubernetes Secrets. Headless provider configuration uses `GOOSE_DISABLE_KEYRING=1`; credentials entered through Goose itself may be saved in its file-based secret store in application Data.

## Storage and execution

- `/config`: persistent application Data; retains the previous desktop deployment's Goose configuration and sessions.
- `/config/workspace`: default persistent execution workspace.
- `/cache`: disposable application Cache.
- `/config/Home` and `/config/External`: optional mounts, disabled by default.

Tools execute on Olares, not on the client computer. The official runtime includes shell, Git and curl; additional language runtimes or browser automation dependencies need a derived image. No Docker socket or Olares administration credentials are mounted.

## Deployment

The official 1.54.0 amd64 image is mirrored through Olares Image Locker to beclab/aaif-goose-goose:1.54.0 and pinned by digest. Startup does not download or install packages. HTTP `/status` probes check the actual Goose process. The backend runs as UID/GID 1000. A separate authenticated management terminal has namespace-scoped exec access.

The server connection key is generated once and reused on upgrades. Preserve the `goose-server` Secret when retaining application data. Rotate the key explicitly if access should be revoked, then update each client.

Model streams have no entrance timeout. Enable scheduled recipes in Goose when needed; the backend starts with scheduler support.

## Models with one concurrent request

Automatic session naming is disabled by default with GOOSE_DISABLE_SESSION_NAMING=true. Change this editable Olares app variable to false to enable it. Changes restart the backend. When enabled, Goose can generate a session title in the background at the same time as the main response. With a Router model limited to one concurrent request, title generation can occupy the only slot and the conversation receives `model_at_capacity` (503).

Explicitly rename a saved session to mark its title as user-provided, then resume it:

```sh
goose session list
goose session rename --session-id <ID> --new-name my-chat
goose run --resume --session-id <ID> --no-profile --max-turns 1 -t 'Reply only OK. Do not use tools.'
```

For an existing session, use `goose session rename --session-id <session-id> --new-name <new-name>`; check `goose session rename --help` for the installed version. In Desktop, rename the session before retrying. Supporting automatic naming concurrently requires sufficient model capacity and matching Router limits; increasing only a limit does not create engine capacity.
