# NOFX (Olares)

Olares packaging only. Image is built and pushed from [github.com/leolianger/nofx](https://github.com/leolianger/nofx):

```bash
cd /path/to/nofx
./scripts/docker-build-push-goai007.sh
# optional: TAG=v1.0.0 ./scripts/docker-build-push-goai007.sh
```

Default image: `docker.io/goai007/nofx:<tag>`. After push, set **values.yaml** `image.tag` to the same tag the script printed (or use `latest` if you tagged that way).

- **Entrance**: HTTP 8080 (nginx + API reverse proxy per `railway/start.sh`).
- **App data**: SQLite at `/app/data/data.db` (mount under `userspace.appData`).
