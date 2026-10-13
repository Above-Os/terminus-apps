# Installation verification

Verified on 2026-10-13 using Olares olarestest01 (amd64).

- Goose 1.54.0 backend and management terminal reached Ready with no restart loop.
- Native Windows Goose Desktop connected to the remote backend.
- ACP health returned HTTP 200; an authenticated ACP probe returned HTTP 406 as expected for a request without SSE headers.
- ACP entrance uses internal authentication level. Both ACP and Terminal report running / Running.
- Goose image mirrored with Olares Image Locker to beclab/aaif-goose-goose:1.54.0. The upstream and mirrored image configuration digests match. The mirror index includes amd64 and arm64; only amd64 was runtime-tested.
- Terminal uses beclab/terminal:v0.0.14.
- UID/GID 1000 and persistent configuration/session paths were checked. Existing desktop deployment data was retained and backed up before conversion.
- Model conversation succeeded both through Router and direct model access. A fresh session with GOOSE_DISABLE_SESSION_NAMING=true returned NAMING_OFF_OK through Router.
- Automatic titles remain disabled by default. Model provider, endpoint and credentials remain configurable and are not embedded in the chart.
- Listing metadata and CDN references pass chart lint. Public assets: official upstream icon plus two all-English architecture/workflow illustrations; no generated product screenshots.

The published chart uses a multi-architecture index pin. Its amd64 platform is the same mirrored version verified in the running deployment. arm64 runtime and third-party MCP extension dependencies require further testing.

- Default AI Router provider verified through https://router.<user-domain>/v1/chat/completions using platform application identity and no model API key; returned ROUTER_DEFAULT_OK. The chart declares Router as an application dependency.
