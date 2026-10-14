#!/usr/bin/env bash
# Let the Olares desktop's browser play through the Bluetooth headset that
# Note (or anything else in the host's audio session) picked.
#
# `start-desktop` runs olares-desktop with a sound server of its own: a
# PipeWire as user olaresd, runtime /run/olares-desktop/runtime. The browser
# in the desktop plays there, and that server has only the box's ALSA cards.
# Bluetooth headsets are in the olares user's session (/run/user/<uid>),
# which is where Note records from and picks the output (yaotest005,
# 2026-10-13: Chromium's stream RUNNING on HDMI in olaresd's server, nothing
# in olares's). This adds one output, "One", to the desktop's server that
# forwards to the host session's default output, and makes it the desktop's
# default, so a meeting played in the desktop comes out of that headset.
#
# Temporary: Olares' next release handles Bluetooth and voice itself. Then
# `uninstall` takes all of this away; nothing here is written outside /run,
# this script's copy, its unit and the list of Notes using it.
#
#   olares-desktop-audio-bridge.sh check       read-only: what is in place
#   olares-desktop-audio-bridge.sh up          bridge once (nothing to do without a desktop)
#   olares-desktop-audio-bridge.sh watch       up every 10 s, quiet while all is well (the unit runs this)
#   olares-desktop-audio-bridge.sh install     copy to /usr/local/sbin, install and start the unit
#   olares-desktop-audio-bridge.sh uninstall   stop and remove the unit, the output, the mount, the copy
#   olares-desktop-audio-bridge.sh attach ID   note that the Note in namespace ID uses the bridge, and install
#   olares-desktop-audio-bridge.sh detach ID   forget it; uninstall once no Note on this host is left
#
# Every Note on a host shares one bridge: the release note and a renamed
# preview (notefigma) each run the job below their chart, and Olares lets no
# other two Notes share a box (a shared app is one per cluster, from one
# source, never cloned). So the Note's job attaches at install and upgrade,
# and its pre-delete hook detaches; the bridge goes with the last one. A Note
# removed without its hook (a release before 0.6.2, a namespace deleted by
# hand) leaves its name in the list, and the bridge stays: what it did before.
#
# How the desktop reaches the host session: olaresd cannot enter
# /run/user/<uid> (0700), and widening that would also open the session bus,
# pipewire-0 and other 0666 sockets there to it. A hard link cannot cross into
# that tmpfs ("Invalid cross-device link"). So the host's pulse directory is
# bind-mounted under /run/olares-audio/desktop, a directory only olaresd may
# enter (root:olaresd 0750); other users are refused there (tried as nobody).
# pipewire-pulse recreates its directory when it restarts, which leaves the
# mount on the old one; watch sees the inode change and mounts it again, and
# loads the output again when its connection was dropped.
#
# The output's stream into the host session is placed once, on what was the
# host's default when it connected, and stays there (node.dont-reconnect):
# when a headset goes from hands-free to A2DP its sink is a new one, and the
# stream sat on HDMI while the default was the headset (yaotest005,
# 2026-10-13: Note took the headset from its recording to play, nothing
# came out). The host will not move it either: move-sink-input answers
# "Invalid argument" for a tunnel's stream, by name or by index (same box).
# A tunnel connects to whatever is the host's default when it is loaded, so
# watch loads the output again whenever its stream is not on the host's
# default, and puts what the desktop plays back on it: a cut of a moment,
# when a headset changes profile or someone picks another default.
# `pactl subscribe` tells watch when the default or the sinks change.
# The output itself goes away with the host sink its stream was on: each
# profile change of a headset, so at every start of a Note recording from it
# and when playing takes it back, the desktop had no "One" until the next
# round, up to ten seconds (yaotest005, 2026-10-13). So the desktop's server
# is followed too, and the output loaded again as soon as it is gone; rounds
# are two seconds apart for what an event misses.
set -uo pipefail
export LC_ALL=C

NAME=olares-desktop-audio-bridge
HOST_USER=${OLARES_AUDIO_USER:-olares}
DESK_USER=${OLARES_DESKTOP_USER:-olaresd}
DESK_RUN=${OLARES_DESKTOP_RUNTIME:-/run/olares-desktop/runtime}
# start-desktop announces this address ("audio: sound server ready at
# /run/olares-desktop/pulse/native"); the one under its PipeWire's runtime
# directory answers too (yaotest005, 2026-10-13). The announced one first.
DESK_SOCKS=("${OLARES_DESKTOP_PULSE:-/run/olares-desktop/pulse/native}" "$DESK_RUN/pulse/native")
DIR=/run/olares-audio/desktop
MNT=$DIR/pulse
SINK=olares-host
SBIN=/usr/local/sbin/$NAME
UNIT=/etc/systemd/system/$NAME.service
INTERVAL=${OLARES_DESKTOP_BRIDGE_INTERVAL:-2}
# One file per Note namespace that uses the bridge. Not under /run: a reboot
# must not forget them, or the next detach would take the bridge from Notes
# still installed. The lock is outside the directories uninstall removes.
USERS=/var/lib/$NAME/users
USERS_LOCK=/run/lock/$NAME.users
# A pulse client run by root "secures" its own runtime directory; give it one
# of its own so neither user's pulse directory is touched.
CLIENT_RUN=/run/$NAME/client

HOST_UID=$(id -u "$HOST_USER" 2>/dev/null) || { echo "no user $HOST_USER (set OLARES_AUDIO_USER)"; exit 2; }
HOST_PULSE=/run/user/$HOST_UID/pulse

pa() { local s=$1; shift; PULSE_RUNTIME_PATH=$CLIENT_RUN timeout -k 1 5 pactl -s "unix:$s/native" "$@" </dev/null 2>/dev/null; }
desk_sock() { local s; for s in "${DESK_SOCKS[@]}"; do [ -S "$s" ] && { echo "$s"; return 0; }; done; return 1; }
desk() { local s; s=$(desk_sock) || return 1; pa "${s%/native}" "$@"; }
host() { pa "$HOST_PULSE" "$@"; }
desk_up() { desk info >/dev/null; }
host_up() { [ -S "$HOST_PULSE/native" ] && host info >/dev/null; }
same_dir() { [ "$(stat -c %d:%i "$MNT" 2>/dev/null)" = "$(stat -c %d:%i "$HOST_PULSE" 2>/dev/null)" ]; }
mount_ok() { mountpoint -q "$MNT" && same_dir; }
dir_ok() { [ "$(stat -c '%U:%G %a' "$DIR" 2>/dev/null)" = "root:$DESK_USER 750" ]; }
# Module ids of this output, and of the hand-made one tried first (to-olares).
tunnel_ids() { desk list short modules | awk -F'\t' -v s="$1" '$2 == "module-tunnel-sink" && $3 ~ ("sink_name=" s "( |$)") { print $1 }'; }
sink_there() { desk list short sinks | awk -F'\t' -v s="$SINK" '$2 == s { f = 1 } END { exit !f }'; }
desk_default() { desk info | sed -n 's/^Default Sink: //p'; }
host_default() { host info | sed -n 's/^Default Sink: //p'; }
# "<input index> <sink index>" for each stream this desktop's output sends
# into the host session; PipeWire names it "Tunnel for <user>@<host>".
forward_inputs() {
  host -f json list sink-inputs | python3 -c '
import json, sys
user = sys.argv[1]
try:
    inputs = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for i in inputs:
    name = str((i.get("properties") or {}).get("media.name", ""))
    if name.startswith("Tunnel for " + user + "@"):
        print(i.get("index"), i.get("sink"))
' "$DESK_USER"
}
sink_index() { host list short sinks | awk -F'\t' -v n="$1" '$2 == n { print $1; exit }'; }

need_root() { [ "$(id -u)" = 0 ] || { echo "run as root"; exit 2; }; }

ensure_mount() {
  mkdir -p "$DIR" "$CLIENT_RUN" && chmod 700 "$CLIENT_RUN"
  dir_ok || { chown "root:$DESK_USER" "$DIR" && chmod 750 "$DIR"; } || return 1
  mkdir -p "$MNT"
  if mountpoint -q "$MNT" && ! same_dir; then umount -l "$MNT" && echo "host pulse directory was recreated; mounting it again"; fi
  if ! mountpoint -q "$MNT"; then mount --bind "$HOST_PULSE" "$MNT" && echo "mounted $HOST_PULSE at $MNT"; fi
  mount_ok
}

# Loads the output when it is missing, makes it the desktop's default and
# moves what plays to it. Only then: afterwards someone may pick another
# output in the desktop, and that choice stays.
ensure_tunnel() {
  local id mod
  for id in $(tunnel_ids to-olares); do desk unload-module "$id" && echo "removed the hand-made to-olares output (module $id)"; done
  if [ -n "$(tunnel_ids "$SINK")" ] && sink_there; then return 0; fi
  for id in $(tunnel_ids "$SINK"); do desk unload-module "$id"; done
  mod=$(desk load-module module-tunnel-sink "server=unix:$MNT/native" "sink_name=$SINK" "sink_properties=device.description=One") \
    || { echo "cannot load the output into the desktop's sound server"; return 1; }
  desk set-default-sink "$SINK"
  for id in $(desk list short sink-inputs | cut -f1); do desk move-sink-input "$id" "$SINK" || echo "cannot move desktop stream $id to $SINK"; done
  echo "desktop plays through the host session's default output now (module $mod)"
}

up() {
  desk_up || return 0   # no desktop running: nothing to bridge
  host_up || { echo "the host audio session does not answer at $HOST_PULSE/native"; return 1; }
  ensure_mount || { echo "cannot mount $HOST_PULSE at $MNT"; return 1; }
  ensure_tunnel
}

# Puts the forward stream on the host's current default output, by loading
# the output again: the stream cannot be moved.
follow() {
  local def idx input sink stale="" id
  desk_up || return 0
  def=$(host_default); [ -n "$def" ] || return 0
  idx=$(sink_index "$def"); [ -n "$idx" ] || return 0
  while read -r input sink; do
    [ -n "$input" ] && [ "$sink" != "$idx" ] && stale="$input on $sink"
  done < <(forward_inputs)
  [ -n "$stale" ] || return 0
  for id in $(tunnel_ids "$SINK"); do desk unload-module "$id" || echo "cannot unload output module $id"; done
  echo "forward stream $stale was not on the host default $def ($idx); loading the output again"
  ensure_tunnel
}

# One at a time: the round and the two event followers may all find the
# output gone at once, and would load it twice.
locked() { ( flock 9; "$@" ) 9>"/run/$NAME/lock"; }

# Runs `$2` on the events of the sound server at socket `$1` that match the
# extended regex `$3`. pactl subscribe ends with that server; the loop
# starts it again.
on_events() {
  local sock=$1 run=$2 match=$3 line
  while :; do
    if [ -S "$sock" ]; then
      while read -r line; do
        if [[ $line =~ $match ]]; then locked "$run"; fi
      done < <(PULSE_RUNTIME_PATH=$CLIENT_RUN pactl -s "unix:$sock" subscribe </dev/null 2>/dev/null)
    fi
    sleep "$INTERVAL"
  done
}

# What the desktop lost: the output gone means it plays to HDMI until up.
gone_up() {
  desk_up || return 0
  if [ -z "$(tunnel_ids "$SINK")" ] || ! sink_there; then echo "the desktop's output $SINK is gone; loading it again"; fi
  up
}

watch() {
  local last="" out desk_sock
  mkdir -p "/run/$NAME"
  on_events "$HOST_PULSE/native" follow " on server| on sink #|'new' on sink-input" &
  desk_sock=$(desk_sock || echo "${DESK_SOCKS[0]}")
  on_events "$desk_sock" gone_up "'remove' on module|'remove' on sink #|'new' on sink #" &
  trap 'kill $(jobs -p) 2>/dev/null' EXIT
  while :; do
    out=$(locked gone_up 2>&1; locked follow 2>&1); [ -n "$out" ] && [ "$out" != "$last" ] && echo "$out"
    last=$out
    sleep "$INTERVAL"
  done
}

check() {
  local bad=0 def
  ok() { printf '  ✅ %s\n' "$*"; }
  no() { printf '  ❌ %s\n' "$*"; bad=$((bad + 1)); }
  echo "Desktop audio bridge ($DESK_USER's sound server -> $HOST_USER's session):"
  if dpkg -s olares-desktop >/dev/null 2>&1; then ok "olares-desktop installed"; else echo "  ·  olares-desktop not installed: nothing to bridge"; fi
  if ! desk_up; then echo "  ·  no desktop sound server at ${DESK_SOCKS[*]} (desktop not started): nothing to bridge now"
  else
    ok "desktop sound server answers ($(desk_sock))"
    if host_up; then ok "host session answers ($HOST_PULSE)"; else no "host session does not answer at $HOST_PULSE/native"; fi
    if dir_ok; then ok "$DIR is root:$DESK_USER 750"; else no "$DIR is $(stat -c '%U:%G %a' "$DIR" 2>/dev/null || echo missing)"; fi
    if mount_ok; then ok "host pulse directory mounted at $MNT"; else no "$MNT is not the host's current pulse directory"; fi
    if [ -n "$(tunnel_ids "$SINK")" ] && sink_there; then ok "output $SINK (\"One\") in the desktop"; else no "no output $SINK in the desktop"; fi
    def=$(desk_default)
    if [ "$def" = "$SINK" ]; then ok "desktop default output is $SINK"; else echo "  ·  desktop default output is ${def:-?}: the browser plays there, not through the host"; fi
    [ -n "$(tunnel_ids to-olares)" ] && echo "  ·  the hand-made to-olares output is still loaded (up removes it)"
    local hdef hidx input sink
    hdef=$(host_default); hidx=$(sink_index "$hdef")
    while read -r input sink; do
      [ -n "$input" ] || continue
      if [ "$sink" = "$hidx" ]; then ok "forward stream $input is on the host default $hdef"
      else no "forward stream $input is on host sink $sink, not the host default $hdef ($hidx)"; fi
    done < <(forward_inputs)
  fi
  if [ -f "$UNIT" ]; then
    if [ "$(systemctl is-active "$NAME" 2>/dev/null)" = active ]; then ok "$NAME.service running"; else no "$NAME.service is $(systemctl is-active "$NAME" 2>/dev/null)"; fi
  else echo "  ·  $NAME.service not installed (install keeps the bridge up across desktop and audio restarts)"; fi
  echo "  ·  used by: $(ls -A "$USERS" 2>/dev/null | tr '\n' ' ' | sed 's/ $//; s/^$/no Note recorded (installed by hand, or before 0.6.2)/')"
  [ "$bad" -eq 0 ]
}

unit_body() {
  cat <<UNIT
[Unit]
Description=Forward the Olares desktop's sound to the host audio session (Bluetooth headsets)
After=user@$HOST_UID.service

[Service]
Type=simple
Environment=OLARES_AUDIO_USER=$HOST_USER
ExecStart=$SBIN watch
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
}

install() {
  local self changed="" tmp
  self=$(readlink -f "${BASH_SOURCE[0]}")
  if [ "$self" != "$SBIN" ] && ! cmp -s "$self" "$SBIN"; then
    # A new file, not an overwrite: bash reads a running script as it goes.
    tmp=$SBIN.new; cp "$self" "$tmp" && chmod 755 "$tmp" && mv -f "$tmp" "$SBIN" && changed=1
  fi
  if ! unit_body | cmp -s - "$UNIT"; then unit_body > "$UNIT" && changed=1; fi
  systemctl daemon-reload
  systemctl enable "$NAME" >/dev/null 2>&1
  if [ -n "$changed" ]; then systemctl restart "$NAME"; echo "installed $SBIN and $UNIT, started"
  else systemctl start "$NAME"; echo "already installed"; fi
}

uninstall() {
  local id
  if [ -f "$UNIT" ]; then systemctl disable --now "$NAME" >/dev/null 2>&1; rm -f "$UNIT"; systemctl daemon-reload; echo "removed $UNIT"; fi
  if desk_up; then
    # The desktop falls back to its own default once the output is gone.
    for id in $(tunnel_ids "$SINK") $(tunnel_ids to-olares); do desk unload-module "$id" && echo "removed output module $id"; done
  fi
  if mountpoint -q "$MNT"; then umount -l "$MNT" && echo "unmounted $MNT"; fi
  rmdir "$MNT" "$DIR" 2>/dev/null
  rm -rf "/run/$NAME"
  [ -f "$SBIN" ] && rm -f "$SBIN" && echo "removed $SBIN"
  rm -rf "/var/lib/$NAME"
  return 0
}

# A namespace name, nothing that could walk out of $USERS.
valid_id() { [[ "${1:-}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || { echo "not a namespace name: '${1:-}'"; exit 2; }; }
# Under one lock, so a Note installing while another is removed cannot see the
# bridge gone after it attached, or keep a bridge nobody is left to remove.
users_locked() { mkdir -p "${USERS_LOCK%/*}"; ( flock -w 10 9 || { echo "another attach or detach holds $USERS_LOCK"; exit 1; }; "$@" ) 9>"$USERS_LOCK"; }

attach() {
  mkdir -p "$USERS" && touch "$USERS/$1" && echo "bridge used by $1"
  install
}

detach() {
  local left
  rm -f "$USERS/$1"
  left=$(ls -A "$USERS" 2>/dev/null | tr '\n' ' ')
  if [ -n "$left" ]; then echo "bridge kept, still used by: ${left% }"; return 0; fi
  echo "no Note on this host uses the bridge any more"
  uninstall
}

need_root
case "${1:-}" in
  check) check ;;
  up) up ;;
  watch) watch ;;
  install) install ;;
  uninstall) uninstall ;;
  attach) valid_id "${2:-}"; users_locked attach "$2" ;;
  detach) valid_id "${2:-}"; users_locked detach "$2" ;;
  *) sed -n '19,25p' "$0"; exit 2 ;;
esac
