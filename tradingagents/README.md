# TradingAgents (Olares)

Olares packaging only. Docker image is built and pushed from the fork [github.com/leolianger/TradingAgents](https://github.com/leolianger/TradingAgents) (see `README-Docker.md` there). This chart deploys `docker.io/goai007/tradingagents`.

- **Entrance**: HTTP on port 8080 (info page; main usage is CLI via exec: `python -m cli.main`).
- **App data**: optional; mount at `/app/data` for config/keys.
