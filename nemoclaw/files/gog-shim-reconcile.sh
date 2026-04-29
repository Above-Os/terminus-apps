#!/bin/sh
# Also embedded in templates/configmap-sandbox-bridge.yaml (key gog-shim-reconcile.sh):
# Olares chart hydration has no Helm .Files — edit the ConfigMap copy, then sync this file.
#
# gogcli is meant to be installed only via OpenClaw: `openclaw config --section skills`
# (which runs brew against NemoClaw's Linuxbrew tree). Do not rely on ad-hoc copies
# under ~/.linuxbrew or manual `brew install` outside that flow.
# Installed into the sandbox as /sandbox/.nemoclaw-reconcile-gog-shim.sh by skill-env + bridge.
set -u
SHIM_MAGIC="# nemoclaw-gog-shim:v17"
SHIM_TMP="$(mktemp /tmp/.gog-shim.XXXXXX)"
cat > "$SHIM_TMP" <<'SHIM'
#!/bin/sh
# nemoclaw-gog-shim:v17
# Counteracts openclaw skill-spawn sanitization (XDG override + GOG_* env filter)
# and exec's the real gog via a path on the OpenShell GOOGLE_BINS allowlist.
#
# NemoClaw pins Homebrew to /sandbox/.linuxbrew (see /etc/environment + profile.d).
# Install gogcli only through: openclaw config --section skills
#
# v17: no-proxy OpenShell fork — all proxy/CA handling removed; shim only fixes
#      HOME/XDG and injects keyring password, then exec's the real gog.
export HOMEBREW_PREFIX="${HOMEBREW_PREFIX:-/sandbox/.linuxbrew}"
export HOMEBREW_REPOSITORY="${HOMEBREW_REPOSITORY:-/sandbox/.linuxbrew/Homebrew}"
export HOMEBREW_CELLAR="${HOMEBREW_CELLAR:-/sandbox/.linuxbrew/Cellar}"
REAL=""
for c in \
  /sandbox/.linuxbrew/Homebrew/opt/gogcli/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.13.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.14.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.15.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.16.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.17.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.18.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.19.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.20.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.21.0/bin/gog \
  /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/0.22.0/bin/gog \
  /sandbox/.linuxbrew/opt/gogcli/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.13.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.14.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.15.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.16.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.17.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.18.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.19.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.20.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.21.0/bin/gog \
  /sandbox/.linuxbrew/Cellar/gogcli/0.22.0/bin/gog \
  /sandbox/.local/opt/gogcli/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.13.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.14.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.15.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.16.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.17.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.18.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.19.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.20.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.21.0/bin/gog \
  /sandbox/.local/Cellar/gogcli/0.22.0/bin/gog \
; do
  case "$c" in
    /usr/local/bin/gog) continue ;;
    /sandbox/.linuxbrew/Homebrew/bin/gog) continue ;;
  esac
  if [ -x "$c" ]; then REAL="$c"; break; fi
done
if [ -z "$REAL" ]; then
  for c in /sandbox/.linuxbrew/Homebrew/Cellar/gogcli/*/bin/gog \
           /sandbox/.linuxbrew/Cellar/gogcli/*/bin/gog \
           /sandbox/.local/Cellar/gogcli/*/bin/gog; do
    [ -x "$c" ] || continue
    REAL="$c"; break
  done
fi
if [ -z "$REAL" ] && command -v brew >/dev/null 2>&1; then
  _pfx=$(brew --prefix gogcli 2>/dev/null || true)
  case "$_pfx" in
    /sandbox/.linuxbrew*|/sandbox/.local*)
      [ -n "$_pfx" ] && [ -x "$_pfx/bin/gog" ] && REAL="$_pfx/bin/gog"
      ;;
  esac
fi
unset _pfx 2>/dev/null || true
if [ -z "$REAL" ]; then
  echo "[gog-shim] FATAL: no gogcli binary under /sandbox/.linuxbrew or /sandbox/.local (Cellar/opt)" >&2
  echo "[gog-shim] Install via: openclaw config --section skills (not manual brew)." >&2
  exit 127
fi
if [ -z "${HOME:-}" ] || [ "$HOME" = "/" ] || [ "$HOME" = "/root" ] || [ "$HOME" = "/tmp" ]; then
  export HOME=/sandbox
fi
export XDG_CONFIG_HOME=/sandbox/.config
if [ -z "${GOG_KEYRING_PASSWORD:-}" ] && [ -r /sandbox/.gog-keyring-password ]; then
  export GOG_KEYRING_BACKEND=file
  export GOG_KEYRING_PASSWORD="$(cat /sandbox/.gog-keyring-password)"
fi
{
  echo "=== $(date -Is 2>/dev/null) pid=$$ ppid=$PPID ==="
  echo "argv: $*"
  echo "real: $REAL"
  echo "XDG=${XDG_CONFIG_HOME:-unset}  HOME=$HOME  PW_LEN=${#GOG_KEYRING_PASSWORD}"
} | tee -a /tmp/gog-shim.log /var/log/nemoclaw-gog-shim.log >/dev/null 2>&1 || true
exec "$REAL" "$@"
SHIM
chmod 0755 "$SHIM_TMP" 2>/dev/null || true
# /usr/local/bin may be read-only; WARN is OK when PATH prefers /sandbox/.local/bin.
for SLOT in /sandbox/.local/bin/gog /sandbox/.linuxbrew/Homebrew/bin/gog /usr/local/bin/gog; do
  slotdir=$(dirname "$SLOT")
  mkdir -p "$slotdir" 2>/dev/null || true
  if [ ! -d "$slotdir" ]; then
    echo "[gog-shim] WARN: $slotdir missing; skipping $SLOT" >&2
    continue
  fi
  if [ -d "$SLOT" ]; then
    rm -rf "$SLOT" 2>/dev/null || true
  fi
  rm -f "$SLOT" 2>/dev/null || true
  cp "$SHIM_TMP" "$SLOT.new" 2>/dev/null || {
    echo "[gog-shim] WARN: cp to $SLOT.new failed; skipping" >&2
    continue
  }
  chmod 0755 "$SLOT.new" 2>/dev/null || true
  chown sandbox:sandbox "$SLOT.new" 2>/dev/null || true
  mv -f "$SLOT.new" "$SLOT" 2>/dev/null && \
    echo "[gog-shim] installed shim at $SLOT ($(wc -c < "$SLOT" 2>/dev/null) bytes)" || \
    echo "[gog-shim] WARN: mv $SLOT.new -> $SLOT failed" >&2
done
rm -f "$SHIM_TMP" 2>/dev/null || true
for stale in \
  /usr/local/bin/gog.real \
  /sandbox/.linuxbrew/Homebrew/bin/gog.real \
  /sandbox/.linuxbrew/bin/gog.real \
; do
  if [ -f "$stale" ] && ! head -2 "$stale" 2>/dev/null | grep -Fq "$SHIM_MAGIC"; then
    rm -f "$stale" 2>/dev/null
  fi
done
# OAuth via Olares connect sometimes runs gog with HOME=/tmp and no XDG_CONFIG_HOME;
# gogcli then writes under /tmp/.config/gogcli while normal CLI reads /sandbox/.config/gogcli.
if [ -d /tmp/.config/gogcli ]; then
  mkdir -p /sandbox/.config/gogcli/keyring 2>/dev/null || true
  if [ -f /tmp/.config/gogcli/credentials.json ] && [ ! -f /sandbox/.config/gogcli/credentials.json ]; then
    cp -a /tmp/.config/gogcli/credentials.json /sandbox/.config/gogcli/ 2>/dev/null && \
      echo "[gog-shim] migrated credentials.json from /tmp/.config/gogcli" >&2
  fi
  if [ -d /tmp/.config/gogcli/keyring ]; then
    for _kf in /tmp/.config/gogcli/keyring/*; do
      [ -f "$_kf" ] || continue
      _kb=$(basename "$_kf")
      [ -e "/sandbox/.config/gogcli/keyring/$_kb" ] && continue
      cp -an "$_kf" /sandbox/.config/gogcli/keyring/ 2>/dev/null && \
        echo "[gog-shim] migrated keyring/$_kb from /tmp/.config/gogcli" >&2
    done
  fi
  chown -R sandbox:sandbox /sandbox/.config/gogcli 2>/dev/null || true
fi
echo "[gog-shim] done. In bash run: hash -r   # if gog was cached before" >&2
