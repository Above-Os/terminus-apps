#!/usr/bin/env bash
# What Note keeps on an Olares host, and its lifecycle: the Bluetooth helper,
# which pairs headsets for Note (see BT_DIR below), and where olares-desktop
# is, the desktop bridge, which lets the desktop's browser play through the
# Bluetooth headset that Note (or anything else in the host's audio session)
# picked. Until 0.6.3 this was olares-desktop-audio-bridge, the bridge alone;
# attach removes what that left (legacy_cleanup below).
#
# The bridge: `start-desktop` runs olares-desktop with a sound server of its
# own: a PipeWire as user olaresd, runtime /run/olares-desktop/runtime. The
# browser in the desktop plays there, and that server has only the box's ALSA
# cards. Bluetooth headsets are in the olares user's session
# (/run/user/<uid>), which is where Note records from and picks the output
# (yaotest005, 2026-10-13: Chromium's stream RUNNING on HDMI in olaresd's
# server, nothing in olares's). This adds one output, "One", to the desktop's
# server that forwards to the host session's default output, and makes it
# the desktop's default, so a meeting played in the desktop comes out of
# that headset.
#
# Temporary: Olares' next release handles Bluetooth and voice itself. Then
# `uninstall` takes all of this away; nothing here is written outside /run,
# this script's copy, its units and the list of Notes using it.
#
#   olares-note-host.sh check       read-only: what is in place
#   olares-note-host.sh up          bridge once (nothing to do without a desktop)
#   olares-note-host.sh watch       bridge, kept up (the bridge's unit runs this)
#   olares-note-host.sh install     copy to /usr/local/sbin, install and start the units
#   olares-note-host.sh uninstall   stop and remove the units, the output, the mount, the copy
#   olares-note-host.sh attach ID   note that the Note in namespace ID uses these, and install
#   olares-note-host.sh detach ID   forget it; uninstall once no Note on this host is left
#   olares-note-host.sh bt-serve    answer one Bluetooth request on stdin (the helper's unit runs this)
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

NAME=olares-note-host
# What Note 0.6.1 and 0.6.2 installed, under the bridge's old name.
OLD=olares-desktop-audio-bridge
OLD_UNIT=/etc/systemd/system/$OLD.service
OLD_SBIN=/usr/local/sbin/$OLD
OLD_USERS=/var/lib/$OLD/users
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
BRIDGE=olares-note-desktop-bridge
UNIT=/etc/systemd/system/$BRIDGE.service
INTERVAL=${OLARES_DESKTOP_BRIDGE_INTERVAL:-2}
# One file per Note namespace that uses the bridge. Not under /run: a reboot
# must not forget them, or the next detach would take the bridge from Notes
# still installed. The lock is outside the directories uninstall removes.
USERS=/var/lib/$NAME/users
USERS_LOCK=/run/lock/$NAME.users
# A pulse client run by root "secures" its own runtime directory; give it one
# of its own so neither user's pulse directory is touched.
CLIENT_RUN=/run/$NAME/client

# The Bluetooth helper: Note asks it to pair, connect and forget, and it runs
# bluetoothctl here as root. Note used to run bluetoothctl in its container
# against the host's system bus mounted in, as the uid Olares gives app pods
# (1000); the system bus refuses a uid with no account on the host, and on
# olaresusa0001 (olares is 1001, no 1000) Bluetooth was "not ready" for good
# (2026-10-14). Through the helper no uid matters: systemd listens on the
# socket and starts bt-serve as root for each request. The socket is open to
# any uid; who reaches it is who mounts its directory, which only Note's
# chart does, the way it mounts the pulse link. What bt-serve does is the
# guard: a fixed list of bluetoothctl commands, Bluetooth addresses only, each
# one bounded in time.
BT_DIR=/run/olares-audio/bt
BT_SOCK=$BT_DIR/helper.sock
# Pairing sessions take turns: two at once would each register an agent and
# scan, and answer each other's devices. Tests point it at a scratch file.
BT_LOCK=${OLARES_NOTE_BT_LOCK:-$BT_DIR/session.lock}
BT_SOCKET_UNIT=/etc/systemd/system/olares-note-bt.socket
BT_SERVICE_UNIT=/etc/systemd/system/olares-note-bt@.service

# Resolved where it is needed: the helper works on a host whatever its users.
host_uid() {
  [ -n "${HOST_UID:-}" ] && return 0
  HOST_UID=$(id -u "$HOST_USER" 2>/dev/null) || { echo "no user $HOST_USER (set OLARES_AUDIO_USER)"; return 2; }
  HOST_PULSE=/run/user/$HOST_UID/pulse
}
HOST_UID="" HOST_PULSE=""

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
    if [ "$(systemctl is-active "$BRIDGE" 2>/dev/null)" = active ]; then ok "$BRIDGE.service running"; else no "$BRIDGE.service is $(systemctl is-active "$BRIDGE" 2>/dev/null)"; fi
  else echo "  ·  $BRIDGE.service not installed (install keeps the bridge up across desktop and audio restarts)"; fi
  if [ "$(systemctl is-active olares-note-bt.socket 2>/dev/null)" = active ] && [ -S "$BT_SOCK" ]; then ok "Bluetooth helper listening at $BT_SOCK"
  else no "Bluetooth helper not listening at $BT_SOCK (attach installs it)"; fi
  if [ -f "$OLD_UNIT" ] && [ ! -L "$OLD_UNIT" ]; then no "the old $OLD.service is still here (attach removes it)"; fi
  local used; used=$(users_left)
  echo "  ·  used by: ${used:-no Note recorded (installed by hand, or before 0.6.2)}"
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

# --- The Bluetooth helper ---------------------------------------------------

BT_MAC='([0-9A-F]{2}:){5}[0-9A-F]{2}'
# BlueZ before 5.65, whose bluetoothctl has no "devices <filter>".
bt_old_bluez() {
  local v major minor
  v=$(timeout -k 1 3 bluetoothctl --version </dev/null 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
  [ -n "$v" ] || return 1
  major=${v%%.*} minor=${v#*.}
  [ "$major" -lt 5 ] || { [ "$major" -eq 5 ] && [ "$minor" -lt 65 ]; }
}
# One bluetoothctl call, as Note's btpair makes them; nothing else runs.
bt_run_ok() {
  local a="$*"
  [[ "$a" =~ ^(show|devices|devices\ Paired|power\ on)$ ]] && return 0
  [[ "$a" =~ ^(info|connect|disconnect|remove)\ $BT_MAC$ ]] && return 0
  [[ "$a" =~ ^--timeout\ ([1-9]|[12][0-9]|30)\ (scan\ on|connect\ $BT_MAC)$ ]] && return 0
  return 1
}
# One step of the pairing session: a command, and the seconds to wait after it.
bt_step_ok() {
  [[ "$1" =~ ^(power\ on|agent\ NoInputNoOutput|default-agent|scan\ on|scan\ off|quit)$ ]] \
    || [[ "$1" =~ ^(pair|trust|connect)\ $BT_MAC$ ]] || return 1
  [[ "$2" =~ ^([0-9]|1[0-5])$ ]]
}
# Only audio devices are paired: a keyboard paired to the host is input to
# the host. Note checks this before asking, and the helper checks it again,
# so a Note that is not itself is still held to it. The same reading as
# btpair's parseInfo: an audio icon, or a hands-free/headset profile on
# something that is not a phone, a computer or an input device; and never a
# HID profile.
bt_audio_ok() {
  local info icon
  info=$(timeout -k 2 10 bluetoothctl info "$1" </dev/null 2>/dev/null) || return 1
  grep -qE '\((00001124|00001812)-' <<<"$info" && return 1
  icon=$(sed -n 's/^[[:space:]]*Icon: //p' <<<"$info" | head -1)
  case "$icon" in
    audio-*) return 0 ;;
    phone|computer|input-*) return 1 ;;
  esac
  grep -qE '\((0000111e|00001108)-' <<<"$info"
}

# One pairing session: the steps go to one bluetoothctl (a scan's devices are
# forgotten when it ends, and a pair in another call then finds none), and
# each step's wait is how long it may take at most, not how long it takes.
# What bluetoothctl prints is read as it comes: a step goes on at its success
# line and the session stops at a failure line. A fixed pause per step made
# every pairing take 23 s, a headset paired in two included (2026-10-14).
# A step whose line never comes waits its full time, as before; the session
# is bounded at 90 s in all. Returns 1 when a step failed.
bt_session() {
  local f cmd wait mac="" ok fail line deadline failed=0 pid io
  for f in "$@"; do cmd=${f%|*}; [[ "$cmd" == pair\ * ]] && mac=${cmd#pair }; done
  # Two fifos rather than coproc, which bash 3.2 (the tests' on a Mac) lacks.
  io=$(mktemp -d) && mkfifo "$io/in" "$io/out" || return 1
  # stdbuf: bluetoothctl's stdout is a fifo here, which stdio would buffer.
  # The whole session is bounded by timeout, not by a sleeping watchdog: a
  # watchdog's sleep holds the answer's stdout open until it ends.
  timeout -k 2 90 ${BT_STDBUF:-stdbuf -oL -eL} bluetoothctl <"$io/in" >"$io/out" 2>&1 & pid=$!
  exec 7>"$io/in" 8<"$io/out"
  for f in "$@"; do
    cmd=${f%|*} wait=${f##*|}
    # The peer may have exited after quit or a failed step. Confine SIGPIPE
    # to the writer so this helper can still return its protocol trailer.
    (printf '%s\n' "$cmd" >&7) 2>/dev/null || break
    [ -n "${OLARES_NOTE_BT_NO_WAIT:-}" ] && continue
    case "$cmd" in
      "scan on") ok=${mac:+"Device $mac"} fail="" ;;
      pair\ *) ok="Pairing successful|AlreadyExists|already paired" fail="Failed to pair" ;;
      trust\ *) ok="trust succeeded" fail="Failed to set trusted|not available" ;;
      connect\ *) ok="Connection successful" fail="Failed to connect" ;;
      *) ok="" fail="" ;;
    esac
    deadline=$((SECONDS + wait))
    while [ "$SECONDS" -lt "$deadline" ]; do
      IFS= read -r -t "$((deadline - SECONDS))" line <&8 || break
      if [ -n "$fail" ] && [[ "$line" =~ $fail ]]; then failed=1; break 2; fi
      if [ -n "$ok" ] && [[ "$line" =~ $ok ]]; then break; fi
    done
  done
  (printf 'quit\n' >&7) 2>/dev/null || true
  exec 7>&-
  # Whatever it still prints is drained, so it never blocks on a full fifo.
  cat <&8 >/dev/null 2>&1
  exec 8<&-
  wait "$pid" 2>/dev/null
  rm -rf "$io"
  return "$failed"
}

# bt-serve answers one request on its standard input, which systemd connects
# to the socket. A request is one line of tab-separated fields:
#   run<TAB>arg<TAB>arg...           one bluetoothctl call
#   session<TAB>cmd|wait<TAB>...     commands fed to one bluetoothctl, pausing
#   host                             what the host has, as key=value lines:
#                                    adapter=yes|no, blocked=yes|no,
#                                    service=<systemctl is-active bluetooth>
# The answer is what bluetoothctl printed, then a last line
# "olares-note-bt exit <status>"; 64 is a request refused, 65 a pairing of
# a device that is not an audio device.
bt_serve() {
  local line kind f cmd wait rc=0
  local -a args=() steps=()
  IFS= read -r -t 5 line || { echo "olares-note-bt exit 64"; return 0; }
  IFS=$'\t' read -r -a f <<<"$line"
  kind=${f[0]:-}
  case "$kind" in
    run)
      args=("${f[@]:1}")
      if [ "${#args[@]}" -eq 0 ] || ! bt_run_ok "${args[@]}"; then echo "refused: ${args[*]}"; echo "olares-note-bt exit 64"; return 0; fi
      # Connecting is held to audio devices as pairing is: a keyboard paired
      # some other way would otherwise be connected through here.
      if [ "${args[${#args[@]}-2]:-}" = connect ] && ! bt_audio_ok "${args[${#args[@]}-1]}"; then
        echo "not an audio device: ${args[${#args[@]}-1]}"; echo "olares-note-bt exit 65"; return 0
      fi
      # "devices Paired" is BlueZ 5.65's; the host's own bluetoothctl runs
      # here, and Ubuntu 22.04 has 5.64, which knows only paired-devices
      # (hzydemo01, 2026-10-14: the status read exited 1). Note used to run
      # its image's newer bluetoothctl and never met it.
      if [ "${args[*]}" = "devices Paired" ] && bt_old_bluez; then args=(paired-devices); fi
      timeout -k 2 40 bluetoothctl "${args[@]}" </dev/null 2>&1; rc=$?
      ;;
    session)
      steps=("${f[@]:1}")
      if [ "${#steps[@]}" -eq 0 ] || [ "${#steps[@]}" -gt 12 ]; then echo "olares-note-bt exit 64"; return 0; fi
      for f in "${steps[@]}"; do
        cmd=${f%|*} wait=${f##*|}
        bt_step_ok "$cmd" "$wait" || { echo "refused: $f"; echo "olares-note-bt exit 64"; return 0; }
      done
      # Every step naming a device: pairing, and trusting and connecting,
      # which a session without a pair step would otherwise do to a keyboard
      # (review, 2026-10-14: trust and connect of one went through).
      for f in "${steps[@]}"; do
        cmd=${f%|*}
        if [[ "$cmd" =~ ^(pair|trust|connect)\ ($BT_MAC)$ ]] && ! bt_audio_ok "${BASH_REMATCH[2]}"; then
          echo "not an audio device: ${BASH_REMATCH[2]}"; echo "olares-note-bt exit 65"; return 0
        fi
      done
      # A failed step is not the request failing: btpair reads the device
      # afterwards and says which of pairing or connecting did not take.
      # Up to as long as a session may take; then this one goes regardless.
      if command -v flock >/dev/null && { exec 8>>"$BT_LOCK"; } 2>/dev/null; then flock -w 100 8 || true; fi
      bt_session "${steps[@]}"; rc=0
      ;;
    host)
      # Tests point OLARES_NOTE_BT_SYS at a scratch directory.
      if compgen -G "${OLARES_NOTE_BT_SYS:-/sys/class/bluetooth}/hci*" >/dev/null; then echo adapter=yes; else echo adapter=no; fi
      if rfkill list bluetooth 2>/dev/null | grep -q 'blocked: yes'; then echo blocked=yes; else echo blocked=no; fi
      echo "service=$(timeout -k 1 5 systemctl is-active bluetooth 2>/dev/null || true)"
      ;;
    *) echo "olares-note-bt exit 64"; return 0 ;;
  esac
  echo "olares-note-bt exit $rc"
}

bt_socket_body() {
  cat <<UNIT
[Unit]
Description=Note's Bluetooth helper: pair, connect and forget headsets for Note

[Socket]
ListenStream=$BT_SOCK
SocketMode=0666
DirectoryMode=0755
Accept=yes
# Room for a few dialogs at once: a status read is several requests in a
# row, a scan holds one for its length, and a request refused here reads as
# a device gone from the list.
MaxConnections=32

[Install]
WantedBy=sockets.target
UNIT
}
bt_service_body() {
  cat <<UNIT
[Unit]
Description=Note's Bluetooth helper, one request
After=bluetooth.service

[Service]
ExecStart=$SBIN bt-serve
StandardInput=socket
StandardOutput=socket
StandardError=journal
RuntimeMaxSec=120
UNIT
}

# --- Install and uninstall --------------------------------------------------

# Copies this script to $SBIN and installs what the host needs: the
# Bluetooth helper always, the desktop bridge where olares-desktop is and
# OLARES_NOTE_DESKTOP_BRIDGE is not "off" (the chart's desktopBridge).
install() {
  local self changed="" bt="" tmp
  self=$(readlink -f "${BASH_SOURCE[0]}")
  if [ "$self" != "$SBIN" ] && ! cmp -s "$self" "$SBIN"; then
    # A new file, not an overwrite: bash reads a running script as it goes.
    tmp=$SBIN.new; cp "$self" "$tmp" && chmod 755 "$tmp" && mv -f "$tmp" "$SBIN" && changed=1 bt=1
  fi
  if ! bt_socket_body | cmp -s - "$BT_SOCKET_UNIT"; then bt_socket_body > "$BT_SOCKET_UNIT" && bt=1; fi
  if ! bt_service_body | cmp -s - "$BT_SERVICE_UNIT"; then bt_service_body > "$BT_SERVICE_UNIT" && bt=1; fi
  systemctl daemon-reload
  systemctl enable olares-note-bt.socket >/dev/null 2>&1
  if [ -n "$bt" ]; then systemctl restart olares-note-bt.socket; echo "Bluetooth helper installed at $BT_SOCK"
  else systemctl start olares-note-bt.socket; echo "Bluetooth helper already installed"; fi

  if [ "${OLARES_NOTE_DESKTOP_BRIDGE:-on}" = off ] && ! bridge_wanted; then
    uninstall_bridge; echo "desktop bridge turned off"; return 0
  fi
  if ! dpkg -s olares-desktop >/dev/null 2>&1; then echo "no olares-desktop here: no desktop bridge"; return 0; fi
  host_uid || return 0
  if ! unit_body | cmp -s - "$UNIT"; then unit_body > "$UNIT" && changed=1 && systemctl daemon-reload; fi
  systemctl enable "$BRIDGE" >/dev/null 2>&1
  if [ -n "$changed" ]; then systemctl restart "$BRIDGE"; echo "installed $SBIN and $UNIT, started"
  else systemctl start "$BRIDGE"; echo "already installed"; fi
}

uninstall_bridge() {
  local id
  if [ -f "$UNIT" ]; then systemctl disable --now "$BRIDGE" >/dev/null 2>&1; rm -f "$UNIT"; systemctl daemon-reload; echo "removed $UNIT"; fi
  if host_uid >/dev/null && desk_up; then
    # The desktop falls back to its own default once the output is gone.
    for id in $(tunnel_ids "$SINK") $(tunnel_ids to-olares); do desk unload-module "$id" && echo "removed output module $id"; done
  fi
  if mountpoint -q "$MNT"; then umount -l "$MNT" && echo "unmounted $MNT"; fi
  rmdir "$MNT" "$DIR" 2>/dev/null
  rm -rf "/run/$NAME"
  return 0
}

uninstall_bt() {
  if [ -f "$BT_SOCKET_UNIT" ] || [ -f "$BT_SERVICE_UNIT" ]; then
    systemctl disable --now olares-note-bt.socket >/dev/null 2>&1
    rm -f "$BT_SOCKET_UNIT" "$BT_SERVICE_UNIT"; systemctl daemon-reload
    echo "removed the Bluetooth helper"
  fi
  rm -rf "$BT_DIR"
}

# The Bluetooth audio setup's script, as the host audio job copies it.
BT_AUDIO=${OLARES_NOTE_BT_AUDIO:-/var/lib/olares-bt-audio/olares-bt-audio.sh}

uninstall() {
  uninstall_bt
  uninstall_bridge
  # And what that setup did for Note alone (it keeps what Lares or the
  # desktop share). Last: it removes the directory this copy may run from.
  if [ -f "$BT_AUDIO" ]; then timeout -k 2 40 bash "$BT_AUDIO" remove </dev/null; fi
  [ -f "$SBIN" ] && rm -f "$SBIN" && echo "removed $SBIN"
  rm -rf "/var/lib/$NAME"
  # Nothing of Note is left: the old name need not be held down any more.
  if [ -L "$OLD_UNIT" ]; then systemctl unmask "$OLD.service" >/dev/null 2>&1; rm -f "$OLD_UNIT"; systemctl daemon-reload; fi
  rm -f "$OLD_SBIN"; rm -rf "/var/lib/$OLD" "/run/$OLD"
  return 0
}

# What Note 0.6.1 and 0.6.2 left under the bridge's old name: their unit is
# stopped and removed, and then masked, a link to /dev/null, because an older
# Note's job may run again on this host (a preview upgraded, a release
# reinstalled) and its install would bring a second bridge back. Masked, its
# unit file is written into /dev/null and nothing starts. Their list of
# Notes stays where they read it: their uninstall hooks still detach there,
# and detach here counts both lists.
legacy_cleanup() {
  if [ -f "$OLD_UNIT" ] && [ ! -L "$OLD_UNIT" ]; then
    systemctl disable --now "$OLD.service" >/dev/null 2>&1
    rm -f "$OLD_UNIT"
    echo "removed the old $OLD.service"
  fi
  [ -L "$OLD_UNIT" ] || { systemctl mask "$OLD.service" >/dev/null 2>&1 || ln -sf /dev/null "$OLD_UNIT"; }
  systemctl daemon-reload
  rm -f "$OLD_SBIN"
}

# A namespace name, nothing that could walk out of $USERS.
valid_id() { [[ "${1:-}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || { echo "not a namespace name: '${1:-}'"; exit 2; }; }
# Under one lock, so a Note installing while another is removed cannot see the
# bridge gone after it attached, or keep a bridge nobody is left to remove.
users_locked() { mkdir -p "${USERS_LOCK%/*}"; ( flock -w 10 9 || { echo "another attach or detach holds $USERS_LOCK"; exit 1; }; "$@" ) 9>"$USERS_LOCK"; }

# Whether a Note on the list wants the desktop bridge. Each one's entry says
# what its chart asked; one switching it off takes it from the host only
# when no other wants it (review, 2026-10-14: a preview with it off took the
# bridge from the release beside it). An entry with nothing in it, and the
# 0.6.x list, are from versions whose Notes with it off did not attach.
bridge_wanted() {
  local f
  for f in "$USERS"/* "$OLD_USERS"/*; do
    [ -f "$f" ] || continue
    [ "$(cat "$f")" = "bridge=off" ] || return 0
  done
  return 1
}

# Notes using these, in both lists: this one's and the one 0.6.2 kept.
users_left() { ls -A "$USERS" "$OLD_USERS" 2>/dev/null | grep -v -e '^$' -e ':$' | sort -u | tr '\n' ' '; }

attach() {
  # A bridge 0.6.1 left, with no list, is taken over as this Note's: users
  # have one Note (a shared app is one per cluster), so it is what an
  # uninstalled 0.6.1 left behind, and goes when this Note does. Only a
  # renamed preview beside a 0.6.1 Note is counted wrong, and that one gets
  # its bridge back at its next upgrade.
  # This Note's own entry in the old list is from its own older version.
  rm -f "$OLD_USERS/$1"
  mkdir -p "$USERS" && echo "bridge=${OLARES_NOTE_DESKTOP_BRIDGE:-on}" > "$USERS/$1" && echo "host services used by $1"
  legacy_cleanup
  install
}

detach() {
  local left
  rm -f "$USERS/$1" "$OLD_USERS/$1"
  left=$(users_left)
  if [ -n "$left" ]; then
    echo "host services kept, still used by: ${left% }"
    bridge_wanted || uninstall_bridge
    return 0
  fi
  echo "no Note on this host uses the host services any more"
  uninstall
}

# bt-serve is started by systemd as root for each request, and by tests as
# whoever runs them; it needs nothing that root alone has.
[ "${1:-}" = bt-serve ] && { bt_serve; exit 0; }
need_root
case "${1:-}" in
  check) host_uid || exit 2; check ;;
  up) host_uid || exit 2; up ;;
  watch) host_uid || exit 2; watch ;;
  install) install ;;
  uninstall) uninstall ;;
  attach) valid_id "${2:-}"; users_locked attach "$2" ;;
  detach) valid_id "${2:-}"; users_locked detach "$2" ;;
  *) sed -n '24,31p' "$0"; exit 2 ;;
esac
