# Runtime provenance

Deployed image: `docker.io/harveyff/concat:0.2.2-olares-r9`

Digest: `sha256:9557bad989488855e88cc591ed42d7e18c87f38857f0dd3fff8bd3d424defb9f`

The browser desktop uses LinuxServer Selkies on Ubuntu Resolute, originally
`ghcr.io/linuxserver/baseimage-selkies:ubunturesolute@sha256:468108db1ab73d876a718d40addbff0509bf29be413dae6b8da680bba109affd`.
Concat desktop is the upstream `Concat-0.2.2-linux-x86_64.tar.gz` release asset
(SHA256 `ab9d6c90b8dc67ea7ae172e66e3207471208eaaf705ef336ec4b1059ba413721`).
The unmodified CLI was built from the same upstream commit with
`cargo build --locked --profile quick -p concat-cli`.
Upstream source: https://github.com/jub0t/Concat/tree/39f24d9ab158fb384acdd2a7ab974bf768f80d73

`api/server.py`, `api/commands.json` and `start-concat` are the exact files
retrieved from the tested r9 container. No tokens or user configuration are
embedded in these files. The API uses Python's standard library and launches
the upstream JSON-line CLI at `/opt/concat-cli/concat-cli`.

`Dockerfile` is a maintenance overlay for updating these files on the pinned
runtime, not a clean-room rebuild of the desktop base. This submission does
not rebuild the existing r9 image. The base includes FFmpeg and Noto CJK fonts.

To build the overlay from this directory:

```sh
docker build --platform linux/amd64 -t YOUR_REGISTRY/concat:YOUR_TAG .
```

Concat is AGPL-3.0-or-later; the full upstream license is in `LICENSE`.
The custom bridge and launcher in this directory are provided under the same
license. Third-party runtime components retain their own licenses.
