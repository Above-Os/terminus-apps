#!/usr/bin/env bash
# Prepare an Olares host so apps can record from a Bluetooth headset or
# speakerphone (e.g. Dolphin520), without anyone logged in at its screen.
# Run as root on the host (Control Hub -> Terminal -> Olares, or ssh + sudo).
#
#   olares-bt-audio.sh check                 read-only: what is there, what is missing
#   olares-bt-audio.sh setup [--replace-pulseaudio] [--shared-socket]
#                                            check, repair what drifted, apply only if something it
#                                            installs is missing, install the boot self-check, check again
#   olares-bt-audio.sh setup --quick         repair, boot self-check, check; no packages, no restarts,
#                                            at most 60 s; exits 4 after printing needs-apply if apply is due
#   olares-bt-audio.sh apply-async [setup options]
#                                            run setup in the background as the host's transient unit
#                                            olares-bt-audio-apply (journalctl -u olares-bt-audio-apply)
#   olares-bt-audio.sh apply [--persist-wbs] [--replace-pulseaudio] [--shared-socket]
#                                            packages, a headless audio session, wideband speech;
#                                            stops if a real PulseAudio serves pulse, unless told to replace it
#   olares-bt-audio.sh pair <name>           scan and pair in ONE bluetoothctl session (press the
#                                            device's pairing button first); trusts and connects it
#   olares-bt-audio.sh test <MAC>            cued 8 s recording in mSBC, then CVSD, with levels
#
# --shared-socket (not yet tried on a host): pipewire-pulse also listens in
# /run/olares-audio/pulse, so apps no longer depend on the 0700 runtime directory.
# Everything it changes is listed by `check` and undone by hand (see README).
set -uo pipefail
export LC_ALL=C

# Nothing here may wait forever. Run from a container that entered the host's
# mount namespace but not its PID namespace, systemctl cannot reach systemd
# (the bus checks the caller's pid) and a following command waited until the
# platform killed the init container after 10 min (yaotest005, 2026-10-12).
# So every command that talks to a daemon goes through a timeout; a timeout
# counts as a failure and says which step it was, on the real stderr (fd 3)
# even where the caller silenced stderr. --foreground keeps a terminal usable
# for commands started from an interactive shell.
# Their stdin is /dev/null unless the caller feeds them on purpose (STDIN=1):
# from a Job with no terminal, stdin is a pipe that never ends, and btmgmt and
# bluetoothctl read it and wait (yaotest005, 2026-10-12: setup stopped at the
# wideband check, though the same script ran fine from a terminal).
exec 3>&2
TMO=${OLARES_AUDIO_TMO:-20}
command -v timeout >/dev/null && HAVE_TIMEOUT=1 || HAVE_TIMEOUT=""
tmo() {
  local s=$1 rc; shift
  if [ -n "${STDIN:-}" ]; then
    if [ -n "$HAVE_TIMEOUT" ]; then timeout --foreground -k 3 "$s" "$@"; rc=$?; else command "$@"; rc=$?; fi
  else
    if [ -n "$HAVE_TIMEOUT" ]; then timeout --foreground -k 3 "$s" "$@" </dev/null; rc=$?; else command "$@" </dev/null; rc=$?; fi
  fi
  if [ "$rc" = 124 ] || [ "$rc" = 137 ]; then
    case "$1" in
      btmgmt|bluetoothctl) echo "$1 timed out (BlueZ $(bluez_version), $(tty_state)) after ${s}s: $*" >&3 ;;
      *) echo "timed out after ${s}s: $*" >&3 ;;
    esac
  fi
  return "$rc"
}
bluez_version() { timeout -k 1 3 bluetoothctl --version </dev/null 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 | grep . || echo '?'; }
tty_state() { if [ -t 0 ]; then echo "with a TTY"; else echo "no TTY"; fi; }
# BlueZ 5.72's btmgmt (bt_shell) does not exit after a command when there is
# no terminal, even with stdin at /dev/null; 5.64's does (yaotest005 against
# hzydemo01, 2026-10-12). bt_shell's own --timeout ends it; where a tool lacks
# that option the hard limit still does, and counts as a failure.
BT_OPT_BTMGMT="" BT_OPT_BLUETOOTHCTL=""
if [ -n "$HAVE_TIMEOUT" ]; then
  # Into a variable first: under pipefail, a --help that is killed or exits
  # non-zero fails the whole pipeline even when grep matched; that is how
  # yaotest005 ran btmgmt without --timeout (2026-10-12).
  case "$(timeout -k 1 3 btmgmt --help </dev/null 2>&1)" in *--timeout*) BT_OPT_BTMGMT=1 ;; esac
  case "$(timeout -k 1 3 bluetoothctl --help </dev/null 2>&1)" in *--timeout*) BT_OPT_BLUETOOTHCTL=1 ;; esac
fi
systemctl() { tmo "${SC_TMO:-$TMO}" systemctl "$@"; }
loginctl() { tmo "$TMO" loginctl "$@"; }
# Commands given as arguments get --timeout (BT_WAIT seconds, 3 unless a
# command needs longer); a session fed on stdin (pair) runs as it is.
bluetoothctl() {
  if [ -z "${STDIN:-}" ] && [ -n "$BT_OPT_BLUETOOTHCTL" ] && [ "${1:-}" != --version ]; then
    tmo "${BT_TMO:-$TMO}" bluetoothctl --timeout "${BT_WAIT:-3}" "$@"
  else
    tmo "${BT_TMO:-$TMO}" bluetoothctl "$@"
  fi
}
btmgmt() {
  if [ -n "$BT_OPT_BTMGMT" ]; then tmo 5 btmgmt --timeout 3 "$@"; else tmo 5 btmgmt "$@"; fi
}
sudo() { tmo "${SUDO_TMO:-$TMO}" sudo "$@"; }
systemd-tmpfiles() { tmo "$TMO" systemd-tmpfiles "$@"; }
systemd-run() { tmo "$TMO" systemd-run "$@"; }
apt-get() { tmo 900 apt-get "$@"; }

# Tests point this at a scratch tree; on a host it is empty.
R=${OLARES_AUDIO_TEST_ROOT:-}
USER_NAME=${OLARES_AUDIO_USER:-olares}
UID_N=$(id -u "$USER_NAME" 2>/dev/null) || { echo "no user $USER_NAME (set OLARES_AUDIO_USER)"; exit 2; }
HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
RUNDIR=$R/run/user/$UID_N
AS_USER=(sudo -u "$USER_NAME" XDG_RUNTIME_DIR="$RUNDIR")
USER_CTL=("${AS_USER[@]}" DBUS_SESSION_BUS_ADDRESS="unix:path=$RUNDIR/bus" systemctl --user)
# A libpulse client running as the directory's owner "secures" its runtime
# directory, $XDG_RUNTIME_DIR/pulse, back to 0700 (pa_make_secure_dir), which
# locks every other uid out. That was the 700 that kept coming back: the boot
# self-check set 711, then its own check ran pactl as olares and undid it,
# every minute (yaotest005, 2026-10-12, reproduced by hand: pactl as olares
# turns 711 into 700; the same with PULSE_RUNTIME_PATH elsewhere does not).
# So every pulse client here runs with its own runtime path and an explicit
# server, never touching that directory.
AS_PULSE=("${AS_USER[@]}" PULSE_RUNTIME_PATH="$RUNDIR/olares-bt-audio-client" PULSE_SERVER="unix:$RUNDIR/pulse/native")
# What an app sees: a different uid (Note runs as 1000) connecting through the
# fixed path. Such a client cannot change the owner's directory either.
APP_UID=${OLARES_AUDIO_APP_UID:-1000}
PKGS=(bluez pipewire wireplumber pipewire-pulse libspa-0.2-bluetooth pulseaudio-utils)

# check counts what it reports in three kinds, because they are fixed in three
# ways. MISSING: something apply installs (packages, linger, configs); only
# apply fixes it, and it may restart part of the audio session. DRIFT: state that comes
# and goes on a set-up host (directory mode, link, wideband, the shared socket
# listening); repair puts it back in place without restarting anything. OTHER:
# neither can (no adapter, a PulseAudio to decide on, the boot self-check).
MISSING=0 DRIFT=0 OTHER=0
ok() { printf '  ✅ %s\n' "$*"; }
no() { printf '  ❌ %s\n' "$*"; MISSING=$((MISSING + 1)); }
drift() { printf '  ❌ %s\n' "$*"; DRIFT=$((DRIFT + 1)); }
bad() { printf '  ❌ %s\n' "$*"; OTHER=$((OTHER + 1)); }
failing() { echo $((MISSING + DRIFT + OTHER)); }

# "Failed to connect to bus" is not "service inactive": tell them apart once.
SD=""
sd_reachable() {
  if [ -z "$SD" ]; then if systemctl show -p Version >/dev/null 2>&1; then SD=yes; else SD=no; fi; fi
  [ "$SD" = yes ]
}
NO_SD="cannot reach systemd (run in the host's PID namespace)"

wp_major() { wireplumber --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f2; }

# WirePlumber only manages Bluetooth for a user sitting at a seat unless told
# otherwise, and HFP should use BlueZ's native backend. Same file name and
# lines as Lares writes, so the two installers agree on one file instead of
# stacking two. 0.4 reads Lua, 0.5 reads SPA-JSON; write the one that applies.
wp_conf_path() {
  if [ "$(wp_major)" -ge 5 ] 2>/dev/null; then
    echo "$HOME_DIR/.config/wireplumber/wireplumber.conf.d/80-bluetooth-without-seat.conf"
  else
    echo "$HOME_DIR/.config/wireplumber/bluetooth.lua.d/80-bluetooth-without-seat.lua"
  fi
}
wp_conf_body() {
  if [ "$(wp_major)" -ge 5 ] 2>/dev/null; then
    printf 'wireplumber.profiles = {\n  main = { monitor.bluez.seat-monitoring = disabled }\n}\n'
    printf 'monitor.bluez.properties = {\n  bluez5.hfphsp-backend = "native"\n  bluez5.hfphsp-backend-native-modem = "any"\n}\n'
  else
    printf '%s\n' 'bluez_monitor.properties["with-logind"] = false' \
      'if bluez_midi_monitor then bluez_midi_monitor.properties["with-logind"] = false end' \
      'bluez_monitor.properties["bluez5.hfphsp-backend"] = "native"' \
      'bluez_monitor.properties["bluez5.hfphsp-backend-native-modem"] = "any"'
  fi
}
# Lares's own test for "already right" (bluetooth-ready.py), so neither side
# rewrites a file the other just wrote; plus one of ours. WirePlumber 0.4.8
# has no MIDI monitor, so Lares's unguarded bluez_midi_monitor line is a nil
# index there and WirePlumber exits 70: no Bluetooth endpoints, headsets fail
# with br-connection-profile-unavailable (hzydemo01, 2026-10-12). That file
# counts as wrong wherever WirePlumber does not define the MIDI monitor.
wp_midi() { grep -rqsE 'bluez_midi_monitor[[:space:]]*=' "$R/usr/share/wireplumber"; }
wp_current() {
  local f; f=$(wp_conf_path)
  [ -f "$f" ] || return 1
  if [ "$(wp_major)" -ge 5 ] 2>/dev/null; then wp_conf_body | cmp -s - "$f"; return; fi
  grep -q hfphsp-backend-native-modem "$f" && grep -q with-logind "$f" && ! grep -q enable-msbc "$f" || return 1
  wp_midi || ! grep -qE '^[[:space:]]*bluez_midi_monitor[.[]' "$f"
}
wp_active() { [ "$("${USER_CTL[@]}" is-active wireplumber 2>/dev/null)" = active ]; }
# A WirePlumber that dies on its config is restarted by systemd and dies again;
# only "active" twice, 2 s apart, counts.
wp_stays_active() {
  local _
  for _ in 1 2 3 4 5; do sleep 2; wp_active || continue; sleep 2; wp_active && return 0; done
  return 1
}
# Names this script used before it took Lares's.
wp_old_paths() {
  echo "$HOME_DIR/.config/wireplumber/bluetooth.lua.d/80-no-logind.lua"
  echo "$HOME_DIR/.config/wireplumber/wireplumber.conf.d/80-no-seat-monitoring.conf"
}

# Write stdin to a file only when it differs; returns 0 when it wrote.
put() {
  local f=$1 tmp; tmp=$(mktemp); cat > "$tmp"
  if cmp -s "$tmp" "$f"; then rm -f "$tmp"; return 1; fi
  mkdir -p "$(dirname "$f")"; cat "$tmp" > "$f"; rm -f "$tmp"
}
put_user() {
  local f=$1 tmp; tmp=$(mktemp); cat > "$tmp"
  if cmp -s "$tmp" "$f"; then rm -f "$tmp"; return 1; fi
  sudo -u "$USER_NAME" mkdir -p "$(dirname "$f")"
  # root reads the temp file, the user writes the target: that split is the point
  # shellcheck disable=SC2024
  STDIN=1 sudo -u "$USER_NAME" tee "$f" < "$tmp" >/dev/null
  rm -f "$tmp"
}

# Apps run as another uid (Note is 1000) and mount the pulse directory, which
# PipeWire creates 0700. The socket inside is 0666; only the directory has to
# be enterable, and pipewire-pulse recreates it whenever it restarts.
share_conf() { echo "$HOME_DIR/.config/systemd/user/pipewire-pulse.service.d/olares-share.conf"; }
# "-": a chmod that runs before the directory exists must not fail, and so
# stop, pipewire-pulse.
share_conf_body() { printf '[Service]\nExecStartPost=-/bin/chmod 711 %%t/pulse\n'; }
# Apps mount the pulse directory from a fixed path, so one package fits every
# box whatever uid runs the sound server here (1000 on some installs, 1001 on
# others). tmpfiles recreates the link at every boot; L+ replaces the empty
# directory a container started before this setup would have left there.
LINK=$R/run/olares-audio/pulse
LINK_CONF=$R/etc/tmpfiles.d/olares-audio.conf
link_ok() { [ "$(readlink "$LINK" 2>/dev/null)" = "$RUNDIR/pulse" ] && [ -f "$LINK_CONF" ]; }

# The shared socket: instead of a link into the runtime directory, the fixed
# path is a real directory, open to all, in which pipewire-pulse listens as
# well. Apps mount the same path and connect to the same name (native), so
# Note's chart stays as it is. The runtime directory's mode stops mattering.
# PipeWire takes an absolute unix: address as is (relative ones go under
# $XDG_RUNTIME_DIR/pulse); listing server.address replaces the default, hence
# unix:native again.
shared_conf() { echo "$HOME_DIR/.config/pipewire/pipewire-pulse.conf.d/80-olares-shared.conf"; }
shared_conf_body() {
  printf '# olares-bt-audio.sh --shared-socket: a second socket outside the 0700 runtime directory\n'
  printf 'pulse.properties = {\n  server.address = [ "unix:native" "unix:%s/native" ]\n}\n' "$LINK"
}
shared_mode() { [ -f "$(shared_conf)" ]; }
shared_dir_ok() { [ -d "$LINK" ] && [ ! -L "$LINK" ] && [ -f "$LINK_CONF" ]; }
shared_answers() { [ -S "$LINK/native" ] && "${AS_PULSE[@]}" pactl -s "unix:$LINK/native" info >/dev/null 2>&1; }

pulse_shared() { [ "$(stat -c %a "$RUNDIR/pulse" 2>/dev/null)" = 711 ]; }

# Wideband is read and set over the kernel's Bluetooth management socket
# directly, the way btmgmt does underneath, so no bt_shell is involved: BlueZ
# 5.72's btmgmt does not exit without a terminal (yaotest005, 2026-10-12), and
# no file in sysfs or bluetoothctl shows the setting. Read Controller
# Information (0x0004) gives supported and current settings, bit 17 is
# wideband speech; wbs-on is Set Powered off, Set Wideband Speech on, Set
# Powered on, Set Connectable on. btmgmt is the fallback where python3 or the
# socket is not available. "mgmt info" prints "<supported> <current>".
MGMT_PY='import ctypes, socket, struct, sys
IDX = 0
def op(s, code, param=b""):
    s.send(struct.pack("<HHH", code, IDX, len(param)) + param)
    while True:
        d = s.recv(512)
        ev, i, n = struct.unpack_from("<HHH", d)
        if ev in (1, 2) and i == IDX and len(d) >= 9 and struct.unpack_from("<H", d, 6)[0] == code:
            if d[8]:
                sys.exit(3)
            return d[9:]
class A(ctypes.Structure):
    _fields_ = [("f", ctypes.c_ushort), ("d", ctypes.c_ushort), ("c", ctypes.c_ushort)]
s = socket.socket(31, socket.SOCK_RAW, 1)
s.settimeout(3)
a = A(31, 0xFFFF, 3)
if ctypes.CDLL(None, use_errno=True).bind(s.fileno(), ctypes.byref(a), ctypes.sizeof(a)):
    sys.exit(2)
if sys.argv[1] == "wbs-on":
    op(s, 5, b"\x00"); op(s, 0x47, b"\x01"); op(s, 5, b"\x01"); op(s, 7, b"\x01")
r = op(s, 4)
print(*struct.unpack_from("<II", r, 9))
'
mgmt() { tmo 10 python3 -c "$MGMT_PY" "$@" 2>/dev/null; }
wbs_bit() {
  local o sup cur
  if o=$(mgmt info) && [ -n "$o" ]; then
    read -r sup cur <<<"$o"
    if [ "$1" = supported ]; then [ $(( (sup >> 17) & 1 )) = 1 ]; else [ $(( (cur >> 17) & 1 )) = 1 ]; fi
    return
  fi
  btmgmt --index 0 info 2>/dev/null | grep "$1 settings" | grep -q wide-band-speech
}
wbs_on() { wbs_bit current; }
wbs_supported() { wbs_bit supported; }
wbs_enable() {
  mgmt wbs-on >/dev/null && return 0
  btmgmt --index 0 power off >/dev/null; btmgmt --index 0 wbs on >/dev/null; btmgmt --index 0 power on >/dev/null
}

# Wideband at boot: the same unit Lares installs, so one unit power-cycles the
# radio, not two. Lares's points at its voice agent (bluetooth-voice-ready
# wideband); where Lares is absent this script writes the unit and a small
# command of the same name and arguments, which Lares's agent also accepts as
# a fallback. An existing unit or command is never overwritten.
WB=bluetooth-wideband-speech.service
WB_UNIT=$R/etc/systemd/system/$WB
WB_BIN=$R/usr/local/sbin/bluetooth-wideband-speech
OLD_WBS_UNIT=$R/etc/systemd/system/olares-bt-wideband.service
# Lares's voice agent: never written or replaced here, only reported.
LARES_BIN=$R/usr/local/sbin/bluetooth-voice-ready
LARES_UNIT=$R/etc/systemd/system/bluetooth-voice-ready.service
wb_unit_body() {
  cat <<UNIT
[Unit]
Description=Enable Bluetooth wideband speech for HFP
After=bluetooth.service
PartOf=bluetooth.service

[Service]
Type=oneshot
ExecStart=$WB_BIN wideband
RemainAfterExit=yes

[Install]
WantedBy=bluetooth.service
UNIT
}
wb_bin_body() {
  cat <<'BIN'
#!/bin/sh
# Turn on Bluetooth wideband speech (mSBC); BlueZ forgets it at every boot.
# Written by olares-bt-audio.sh where Lares had not installed its own. The
# kernel takes the switch only while the radio is off, so this powers it off
# once when wideband is off, and leaves the radio alone when it is already on.
# Talks to the kernel's management socket itself: BlueZ 5.72's btmgmt never
# exits without a terminal. btmgmt (with --timeout where it has one, under a
# hard limit) only where python3 cannot.
case "${1:-wideband}" in wideband) ;; *) echo "unknown command $1" >&2; exit 2 ;; esac
BIN
  printf "MGMT_PY='%s'\n" "$MGMT_PY"
  cat <<'BIN'
mgmt() { timeout -k 1 10 python3 -c "$MGMT_PY" "$@" </dev/null 2>/dev/null; }
T=""
case "$(timeout -k 1 3 btmgmt --help </dev/null 2>&1)" in *--timeout*) T="--timeout 3" ;; esac
bt() { timeout -k 1 5 btmgmt $T --index 0 "$@" </dev/null; }
on() {
  o=$(mgmt info) || o=""
  if [ -n "$o" ]; then set -- $o; [ $(( ($2 >> 17) & 1 )) = 1 ] && [ $(( $2 & 1 )) = 1 ]; return; fi
  bt info 2>/dev/null | grep 'current settings' | grep 'powered' | grep -q wide-band-speech
}
on && exit 0
mgmt wbs-on >/dev/null || { bt power off >/dev/null; bt wbs on >/dev/null; bt power on >/dev/null; bt connectable on >/dev/null; }
on || { echo "bluetooth wideband speech is off" >&2; exit 1; }
BIN
}
# Through the unit when there is one, so Lares's implementation is the one used.
wbs_fix() { if [ -f "$WB_UNIT" ]; then SC_TMO=60 systemctl restart "$WB" >/dev/null 2>&1; else wbs_enable; fi; }
wb_install() {
  local reload=""
  if [ -f "$OLD_WBS_UNIT" ]; then
    systemctl disable --now olares-bt-wideband.service >/dev/null 2>&1; rm -f "$OLD_WBS_UNIT"; reload=1
    echo "removed olares-bt-wideband.service ($WB replaces it)"
  fi
  if [ ! -f "$WB_UNIT" ]; then mkdir -p "$(dirname "$WB_UNIT")"; wb_unit_body > "$WB_UNIT"; reload=1; fi
  # Ours (by its comment) may be replaced by a newer one; anyone else's never.
  if grep -q "^ExecStart=$WB_BIN" "$WB_UNIT" && { [ ! -e "$WB_BIN" ] || grep -q "Written by olares-bt-audio.sh" "$WB_BIN"; } \
     && ! wb_bin_body | cmp -s - "$WB_BIN"; then
    mkdir -p "$(dirname "$WB_BIN")"; wb_bin_body > "$WB_BIN"; chmod 755 "$WB_BIN"
  fi
  if [ -n "$reload" ]; then systemctl daemon-reload; fi
  systemctl enable "$WB" >/dev/null 2>&1
}

pulse_server() { "${AS_PULSE[@]}" pactl info 2>/dev/null | sed -n 's/^Server Name: //p'; }

# For the journal when the directory is found at 0700: if its change time
# matches when pipewire-pulse.service last started, the drop-in's chmod lost
# a race with the server creating it; if not, something else changed it.
pulse_units_state() {
  "${USER_CTL[@]}" show pipewire-pulse.socket pipewire-pulse.service -p Id -p ActiveState -p ActiveEnterTimestamp 2>/dev/null \
    | awk -F= '/^Id=/{id=$2} /^ActiveState=/{st=$2} /^ActiveEnterTimestamp=/{printf "%s%s %s since %s", sep, id, st, ($2 == "" ? "-" : $2); sep="; "}'
}

# The boot self-check runs a copy of this script, so it does not depend on
# wherever setup was started from (/root, a home directory, a USB stick).
SBIN=$R/usr/local/sbin/olares-bt-audio.sh
READY=olares-audio-ready.service
READY_UNIT=$R/etc/systemd/system/$READY
READY_STATUS=$R/run/olares-audio-ready.status

# "devices Paired|Connected" is BlueZ 5.65+; older ones only know
# paired-devices, newer ones answer that with "Invalid command". An empty list
# is an answer too, so the BlueZ version picks the command, not the output.
bt_devices() {
  local v major minor mac rest
  v=$(bluetoothctl --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
  major=${v%%.*} minor=${v#*.}
  if [ -n "$v" ] && [ "$major" -eq 5 ] && [ "$minor" -lt 65 ]; then
    bluetoothctl paired-devices 2>/dev/null | grep '^Device' | while read -r _ mac rest; do
      if [ "$1" = Paired ] || bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes'; then echo "Device $mac $rest"; fi
    done
  else
    bluetoothctl devices "$1" 2>/dev/null | grep '^Device'
  fi
}

check() {
  MISSING=0 DRIFT=0 OTHER=0
  echo "Host Bluetooth audio for user $USER_NAME (uid $UID_N):"
  if [ -e "$R/sys/class/bluetooth/hci0" ]; then ok "adapter hci0"; else bad "no Bluetooth adapter (nothing else here can help)"; fi
  if rfkill list bluetooth 2>/dev/null | grep -q 'blocked: yes'; then bad "adapter is rfkill-blocked"; else ok "not blocked"; fi
  if ! sd_reachable; then bad "$NO_SD: services, units and the boot self-check not checked"
  elif [ "$(systemctl is-active bluetooth 2>/dev/null)" = active ]; then ok "bluetooth service active"; else bad "bluetooth service not active"; fi
  for p in "${PKGS[@]}"; do if dpkg -s "$p" >/dev/null 2>&1; then ok "package $p"; else no "package $p missing"; fi; done
  if [ -e "$R/var/lib/systemd/linger/$USER_NAME" ]; then ok "linger on (audio session without a login)"; else no "linger off: no audio session unless $USER_NAME logs in at the screen"; fi
  if wp_current; then ok "WirePlumber manages Bluetooth without a seat, native HFP ($(wp_conf_path))"; else no "WirePlumber still waits for a seated login ($(wp_conf_path) missing or out of date)"; fi
  local old; for old in $(wp_old_paths); do [ -f "$old" ] && no "old WirePlumber fragment $old (apply replaces it)"; done
  if [ -S "$RUNDIR/pulse/native" ]; then ok "pulse socket $RUNDIR/pulse/native"; else no "no pulse socket in $RUNDIR"; fi
  # The socket alone says nothing about who serves it: a real PulseAudio
  # names its Bluetooth profiles and sources differently, and Note only
  # knows PipeWire's names (hzydemo01, 2026-10-10: PulseAudio 15.99).
  local server; server=$(pulse_server)
  case "$server" in
    *PipeWire*) ok "pulse served by PipeWire ($server)" ;;
    "") no "nothing answers on the pulse socket" ;;
    *) bad "pulse served by $server, not PipeWire: apply would replace it; decide first" ;;
  esac
  command -v wireplumber >/dev/null || no "wireplumber not installed (the config written assumes 0.4 until it is)"
  if shared_mode; then
    echo "  ·  shared socket mode ($(shared_conf)): the runtime directory's mode does not matter"
    if shared_dir_ok; then ok "apps find pulse in $LINK, a directory kept at boot by $LINK_CONF"; else no "$LINK is not the shared directory (apply --shared-socket)"; fi
    if shared_answers; then ok "pipewire-pulse answers on $LINK/native"; else drift "nothing answers on $LINK/native: apps installed with capture.bluetooth find no sound server"; fi
  else
    # Note runs as uid 1000. When the host user is that uid too (hzydemo01),
    # the directory's mode does not matter; 711 is only needed otherwise.
    if [ "$UID_N" = 1000 ]; then
      ok "host user is uid 1000, as Note is: the pulse directory needs no sharing"
    elif pulse_shared; then
      ok "pulse directory enterable by apps (711)"
    else
      drift "pulse directory is $(stat -c %a "$RUNDIR/pulse" 2>/dev/null): apps running as another uid get 'Connection refused'"
    fi
    if share_conf_body | cmp -s - "$(share_conf)"; then ok "kept enterable across restarts ($(share_conf))"
    elif [ -f "$(share_conf)" ]; then no "$(share_conf) is an older version (apply rewrites it)"
    else no "not kept enterable across pipewire-pulse restarts"; fi
    if link_ok; then ok "apps find pulse at $LINK -> $RUNDIR/pulse (kept at boot by $LINK_CONF)"
    elif [ -f "$LINK_CONF" ]; then drift "no link at $LINK: apps installed with capture.bluetooth find no sound server"
    else no "no link at $LINK: apps installed with capture.bluetooth find no sound server"; fi
  fi
  app_can_connect
  if wbs_on; then ok "wideband speech on"; else drift "wideband speech off: mSBC recordings will be digital silence (-90 dBFS)"; fi
  if ! sd_reachable; then :
  elif [ -f "$WB_UNIT" ] && [ "$(systemctl is-enabled "$WB" 2>/dev/null)" = enabled ]; then
    ok "wideband restored at boot ($WB: $(sed -n 's/^ExecStart=//p' "$WB_UNIT"))"
  else
    no "wideband not restored at boot (apply --persist-wbs installs $WB)"
  fi
  [ -f "$OLD_WBS_UNIT" ] && no "old olares-bt-wideband.service still installed: a second unit power-cycling the radio at boot (apply removes it)"
  if [ -e "$LARES_BIN" ] || [ -e "$LARES_UNIT" ]; then echo "  ·  Lares voice agent is here (bluetooth-voice-ready): coexisting, left alone"; fi
  # The Olares desktop depends on pipewire(-pulse), wireplumber and
  # pulseaudio-utils, not on libspa-0.2-bluetooth: removing those removes it.
  if dpkg -s olares-desktop >/dev/null 2>&1; then echo "  ·  olares-desktop present: the sound server comes with it (never apt-get remove pipewire-pulse or pulseaudio-utils here)"; fi
  if ! sd_reachable; then :
  elif [ ! -f "$READY_UNIT" ]; then
    bad "no boot self-check ($READY; setup installs it)"
  else
    local en act; en=$(systemctl is-enabled "$READY" 2>/dev/null) act=$(systemctl is-active "$READY" 2>/dev/null)
    if [ "$en" = enabled ] && [ "$act" = active ]; then ok "boot self-check enabled and running ($READY)"; else bad "boot self-check $READY is ${en:-?}/${act:-?}, not enabled/active"; fi
    if [ -s "$READY_STATUS" ]; then echo "  ·  its last result: $(head -1 "$READY_STATUS")"; else echo "  ·  it has not reported since boot (journalctl -u ${READY%.service})"; fi
  fi
  echo "Paired devices:"; bt_devices Paired | sed 's/^/  /' | grep . || echo "  (none)"
  [ -S "$RUNDIR/pulse/native" ] && { echo "Bluetooth cards PipeWire sees:"; "${AS_PULSE[@]}" pactl list cards short 2>/dev/null | grep bluez | sed 's/^/  /'; }
  return 0
}

# Connect as APP_UID the way the app's pod does. The pod's hostPath mount
# resolves /run/olares-audio/pulse once and binds the pulse directory itself,
# so the app never walks through /run/user/<uid> (0700). A connect from the
# host through the link does walk through it and is refused even when the app
# is fine (luolong01, 2026-10-12: 30 of 30 refused on the host, 5 of 5 fine
# in Note). So the probe binds the directory into a private mount namespace,
# as the pod does, and connects there; it never widens /run/user/<uid>.
# Without unshare/setpriv it only reads the permission bits. Counted as drift:
# what blocks it (mode, link, socket) is what repair puts back.
app_can_connect() {
  local src out rc mode nmode
  [ -S "$LINK/native" ] || return 0   # reported above as no link / no socket
  src=$(readlink -f "$LINK")
  if command -v unshare >/dev/null && command -v setpriv >/dev/null && tmo 5 unshare -m true >/dev/null 2>&1; then
    # shellcheck disable=SC2016  # expanded by the inner sh
    if out=$(tmo "$TMO" unshare -m sh -c '
          m=$(mktemp -d) && mount --bind "$1" "$m" || exit 97
          p=$(mktemp -d); chown "$2" "$p" 2>/dev/null
          setpriv --reuid="$2" --regid="$2" --clear-groups \
            env HOME="$p" PULSE_RUNTIME_PATH="$p/rt" PULSE_SERVER="unix:$m/native" pactl info
          rc=$?; umount "$m"; rmdir "$m"; rm -rf "$p"; exit $rc' sh "$src" "$APP_UID" 2>&1); then
      ok "apps (uid $APP_UID) connect to $src/native mounted as a pod mounts it"; return
    else
      rc=$?
    fi
    if [ "$rc" != 97 ]; then drift "apps (uid $APP_UID) cannot connect to $src/native mounted as a pod mounts it: $(echo "$out" | grep -v '^$' | head -1)"; return; fi
  fi
  mode=$(stat -c %a "$src" 2>/dev/null) nmode=$(stat -c %a "$src/native" 2>/dev/null); mode=${mode:-0} nmode=${nmode:-0}
  if [ $(( ${mode: -1} & 1 )) = 1 ] && [ $(( ${nmode: -1} & 6 )) = 6 ]; then
    ok "apps (uid $APP_UID) may enter $src and use native (permission bits only, not probed)"
  else
    drift "apps (uid $APP_UID) cannot enter $src ($mode) or use native ($nmode) (permission bits only, not probed)"
  fi
}

# Put back what drifts after setup, cheapest first, one line per fix; returns
# 0 when it fixed something. Restarts nothing. The pulse directory has been
# seen back at 0700 after apply although the drop-in had run, and again later
# with nothing touched (yaotest005, 2026-10-12; cause unknown), so this does
# not trust the drop-in alone. Wideband is tried once per process: an adapter
# that will not take it would otherwise be power-cycled, dropping its
# connection, every round.
WBS_TRIED="" SHARED_WARNED="" SHARED_RESTARTED=""
repair() {
  local fixed=1 mode
  if shared_mode; then
    if shared_dir_ok && ! shared_answers && [ -S "$RUNDIR/pulse/native" ]; then
      # pipewire-pulse is socket-activated on the runtime socket only; it
      # opens the shared one when something wakes it. Running without it
      # (started before the config was there) takes a restart, tried once per
      # process since it cuts off every pulse client on the host.
      "${AS_PULSE[@]}" pactl info >/dev/null 2>&1
      if shared_answers; then echo "woke pipewire-pulse; it answers on $LINK/native again"; fixed=0
      else
        if [ -z "$SHARED_RESTARTED" ]; then
          SHARED_RESTARTED=1; SUDO_TMO=60 "${USER_CTL[@]}" restart pipewire-pulse.service >/dev/null 2>&1; wait_pulse_service
        fi
        if shared_answers; then echo "restarted pipewire-pulse; it answers on $LINK/native again"; fixed=0
        elif [ -z "$SHARED_WARNED" ]; then echo "pipewire-pulse does not answer on $LINK/native even restarted (see $(shared_conf))"; SHARED_WARNED=1; fi
      fi
    fi
  else
    if [ "$UID_N" != 1000 ] && [ -d "$RUNDIR/pulse" ] && ! pulse_shared; then
      mode=$(stat -c %a "$RUNDIR/pulse" 2>/dev/null)
      echo "pulse directory was $mode (changed $(stat -c %z "$RUNDIR/pulse" 2>/dev/null); $(pulse_units_state)), set to 711"
      chmod 711 "$RUNDIR/pulse"; fixed=0
    fi
    if [ -f "$LINK_CONF" ] && ! link_ok; then
      systemd-tmpfiles --create "$LINK_CONF" && echo "recreated $LINK"; fixed=0
    fi
  fi
  if [ -z "$WBS_TRIED" ] && wbs_supported && ! wbs_on; then
    WBS_TRIED=1; wbs_fix
    if wbs_on; then echo "turned wideband speech on"; else echo "wideband speech still off after turning it on; not retrying until restart"; fi
    fixed=0
  fi
  return $fixed
}

# One line for the journal; the full check goes to $READY_STATUS for `check`.
report() {
  local out n_ok n_no line
  out=$(check 2>&1)
  n_ok=$(grep -c '✅' <<<"$out") n_no=$(grep -c '❌' <<<"$out")
  if [ "$n_no" = 0 ]; then
    line="ready: all $n_ok checks pass"
  else
    line="not ready: $n_no of $((n_ok + n_no)) checks fail: $(grep '❌' <<<"$out" | sed 's/^ *❌ //' | paste -sd';' -)"
  fi
  printf '%s %s\n%s\n' "$(date '+%F %T')" "$line" "$out" > "$READY_STATUS"
  echo "$line"
}

# What olares-audio-ready.service runs. The audio session comes up when
# user@<uid> starts, which can be late after a cold boot, so it polls for the
# socket, repairs, and reports once; after that it stays, re-checking every
# minute and writing only when it had to fix something. A timer would do the
# same work but log a start and a finish every round whether or not anything
# was wrong; a loop that sleeps logs nothing while all is well.
watch() {
  local rounds=${OLARES_AUDIO_WATCH_ROUNDS:-0} n=0 reported="" waited=0 warned=""
  while :; do
    if [ -S "$RUNDIR/pulse/native" ]; then
      if repair || [ -z "$reported" ]; then report; reported=1; fi
    elif [ -z "$warned" ] && [ "$waited" -ge 600 ]; then
      echo "no audio session for $USER_NAME after 10 min ($RUNDIR/pulse/native missing); still waiting"; warned=1
    fi
    n=$((n + 1)); [ "$rounds" -gt 0 ] && [ "$n" -ge "$rounds" ] && return 0
    if [ -n "$reported" ]; then sleep 60; else sleep 10; waited=$((waited + 10)); fi
  done
}

ready_unit_body() {
  cat <<UNIT
[Unit]
Description=Keep Bluetooth audio ready for Olares apps (pulse directory, $LINK, wideband speech)
After=bluetooth.service user@$UID_N.service systemd-tmpfiles-setup.service

[Service]
Type=simple
Environment=OLARES_AUDIO_USER=$USER_NAME
ExecStart=$SBIN watch
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
}

# Idempotent: copies and reloads only what differs. Sets READY_RESULT.
READY_RESULT=""
install_ready() {
  local self changed="" tmp
  self=$(readlink -f "${BASH_SOURCE[0]}")
  [ -f "$self" ] || { echo "cannot find this script on disk to install the boot self-check; run it from a file"; return 1; }
  mkdir -p "$(dirname "$SBIN")" "$(dirname "$READY_UNIT")"
  if [ "$self" != "$SBIN" ] && ! cmp -s "$self" "$SBIN"; then
    # A new file, not an overwrite: bash reads a running script as it goes.
    tmp=$SBIN.new; cp "$self" "$tmp" && chmod 755 "$tmp" && mv -f "$tmp" "$SBIN"; changed=1
  fi
  if ! ready_unit_body | cmp -s - "$READY_UNIT"; then ready_unit_body > "$READY_UNIT"; changed=1; fi
  if [ -n "$changed" ]; then
    systemctl daemon-reload
    systemctl enable "$READY" >/dev/null 2>&1
    SC_TMO=60 systemctl restart "$READY"
    READY_RESULT="installed or updated ($SBIN, $READY_UNIT)"
  else
    systemctl enable "$READY" >/dev/null 2>&1
    systemctl start "$READY"
    READY_RESULT="already in place"
  fi
}

# After user@<uid> restarts, the pulse directory comes from
# pipewire-pulse.socket and the server itself only starts when a client
# connects; the drop-in's chmod runs after that. Wake it and wait until the
# service is active, so what follows sees the session as apps will.
wait_pulse_service() {
  local _
  for _ in $(seq 1 30); do
    [ "$("${USER_CTL[@]}" is-active pipewire-pulse.service 2>/dev/null)" = active ] && return 0
    [ -S "$RUNDIR/pulse/native" ] && "${AS_PULSE[@]}" pactl info >/dev/null 2>&1
    sleep 1
  done
  return 1
}

# Restarting the audio session drops every Bluetooth audio connection
# (yaotest005, 2026-10-12: Dolphin520 gone after apply). Reconnect what was
# connected before; WirePlumber registers the Bluetooth profiles a little
# after the session starts, so a connect can fail at first. Sets RECONNECT_RESULT.
RECONNECT_RESULT="no device was connected"
reconnect() {
  local mac done_ok="" kept="" left="" _
  [ $# -gt 0 ] || return 0
  for mac in "$@"; do
    if bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes'; then kept="$kept $mac"; continue; fi
    for _ in 1 2 3; do
      BT_WAIT=10 BT_TMO=15 bluetoothctl connect "$mac" >/dev/null 2>&1
      bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes' && break
      sleep 3
    done
    if bluetoothctl info "$mac" 2>/dev/null | grep -q 'Connected: yes'; then done_ok="$done_ok $mac"; else left="$left $mac"; fi
  done
  RECONNECT_RESULT=""
  [ -n "$kept" ] && RECONNECT_RESULT="still connected$kept"
  [ -n "$done_ok" ] && RECONNECT_RESULT="${RECONNECT_RESULT:+$RECONNECT_RESULT; }reconnected$done_ok"
  [ -n "$left" ] && RECONNECT_RESULT="${RECONNECT_RESULT:+$RECONNECT_RESULT; }disconnected, reconnect by hand:$(for m in $left; do printf ' bluetoothctl connect %s;' "$m"; done)"
  return 0
}

# Installing pipewire-pulse takes the pulse socket from a running PulseAudio
# (Ubuntu 22.04's default), which changes sound for everything on the host.
# Note records through either since it stopped matching PipeWire's names, so
# this is a choice, not a requirement.
is_pulseaudio_host() { local s; s=$(pulse_server); [ -n "$s" ] && [[ "$s" != *PipeWire* ]]; }

# Changes only what differs and restarts only what a change needs: the whole
# audio session only when the PipeWire stack was just installed; WirePlumber
# when its fragment changed or the Bluetooth plugin is new (as Lares does);
# pipewire-pulse when the shared socket was switched on. Each of these drops
# Bluetooth audio, so devices connected before are reconnected after.
apply_changes() {
  local persist=$1 replace=$2 shared=$3 connected p missing=() session="" wp="" pp=""
  sd_reachable || { echo "$NO_SD: nothing changed"; exit 5; }
  if is_pulseaudio_host && [ -z "$replace" ]; then
    echo "pulse is served by $(pulse_server). apply would replace it with PipeWire."
    echo "Rerun with --replace-pulseaudio to do that; this script does not prepare a PulseAudio host."
    exit 3
  fi
  # Once chosen, the shared socket stays: an apply without the flag keeps it.
  shared_mode && shared=1
  connected=$(bt_devices Connected | awk '{print $2}')
  for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "installing ${missing[*]}"
    DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}" || { echo "apt failed"; exit 1; }
    case " ${missing[*]} " in *" pipewire "*|*" pipewire-pulse "*|*" wireplumber "*) session=1 ;; esac
    case " ${missing[*]} " in *" libspa-0.2-bluetooth "*) wp=1 ;; esac
  fi
  [ -e "$R/var/lib/systemd/linger/$USER_NAME" ] || loginctl enable-linger "$USER_NAME"
  local wp_backup wp_before="" f; wp_backup=$(mktemp -d)
  for f in "$(wp_conf_path)" $(wp_old_paths); do [ -f "$f" ] && cp -p "$f" "$wp_backup/"; done
  [ -d "$RUNDIR" ] && wp_active && wp_before=1
  if ! wp_current; then wp_conf_body | put_user "$(wp_conf_path)"; wp=1; echo "wrote $(wp_conf_path)"; fi
  local old; for old in $(wp_old_paths); do [ -f "$old" ] && { rm -f "$old"; wp=1; echo "removed old $old"; }; done
  share_conf_body | put_user "$(share_conf)" && "${USER_CTL[@]}" daemon-reload >/dev/null 2>&1
  if [ -n "$shared" ]; then
    shared_conf_body | put_user "$(shared_conf)" && pp=1
    [ -L "$LINK" ] && rm -f "$LINK"
    printf 'd %s 0755 root root -\nd %s 0755 %s - -\n' "$(dirname "$LINK")" "$LINK" "$USER_NAME" | put "$LINK_CONF"
  else
    printf 'd %s 0755 root root -\nL+ %s - - - - %s\n' "$(dirname "$LINK")" "$LINK" "$RUNDIR/pulse" | put "$LINK_CONF"
  fi
  systemd-tmpfiles --create "$LINK_CONF"
  [ "$persist" = --persist-wbs ] && wb_install
  if [ -n "$session" ]; then
    echo "restarting the audio session (user@$UID_N): the PipeWire stack is new"
    SC_TMO=90 systemctl restart "user@$UID_N"; sleep 5
  elif [ -d "$RUNDIR" ]; then
    if [ -n "$wp" ]; then echo "restarting WirePlumber: its fragment changed or the Bluetooth plugin is new"; SUDO_TMO=60 "${USER_CTL[@]}" restart wireplumber >/dev/null 2>&1; sleep 2; fi
    if [ -n "$pp" ]; then echo "restarting pipewire-pulse: it now listens on $LINK/native too"; SUDO_TMO=60 "${USER_CTL[@]}" restart pipewire-pulse.service >/dev/null 2>&1; fi
  fi
  if [ -n "$wp" ] && [ -n "$wp_before" ] && ! wp_stays_active; then
    for f in "$(wp_conf_path)" $(wp_old_paths); do
      rm -f "$f"; [ -f "$wp_backup/$(basename "$f")" ] && cp -p "$wp_backup/$(basename "$f")" "$f"
    done
    SUDO_TMO=60 "${USER_CTL[@]}" restart wireplumber >/dev/null 2>&1
    echo "WirePlumber did not stay active with $(wp_conf_path); put back what was there before and restarted it"
    echo "see: journalctl --user -M $USER_NAME@ -u wireplumber -b"
    rm -rf "$wp_backup"
    exit 6
  fi
  rm -rf "$wp_backup"
  if ! wbs_on; then WBS_TRIED=1; wbs_fix; fi
  install_ready
  wait_pulse_service || echo "pipewire-pulse.service did not become active within 30 s"
  repair
  # shellcheck disable=SC2086  # one MAC per word
  reconnect $connected
  echo "Bluetooth devices: $RECONNECT_RESULT"
}

apply() {
  local persist="" replace="" shared=""
  for arg in "$@"; do
    case "$arg" in
      --persist-wbs) persist=--persist-wbs ;;
      --replace-pulseaudio) replace=1 ;;
      --shared-socket) shared=1 ;;
      *) echo "unknown option $arg"; exit 2 ;;
    esac
  done
  apply_changes "$persist" "$replace" "$shared"
  check
}

# check -> repair what drifted -> apply only if something apply installs is
# missing -> boot self-check -> check. Drift alone never runs apply: apply
# restarts the audio session, which interrupts a recording and drops the
# Bluetooth device. Rerunning on a ready host changes nothing.
setup() {
  local replace="" shared="" quick="" applied server before mode
  for arg in "$@"; do
    case "$arg" in
      --replace-pulseaudio) replace=1 ;;
      --shared-socket) shared=1 ;;
      --quick) quick=1 ;;
      *) echo "unknown option $arg"; exit 2 ;;
    esac
  done
  # --quick is what an init container can afford to wait for: a hard 60 s cap
  # on top of the per-command timeouts.
  if [ -n "$quick" ] && [ -z "${OLARES_AUDIO_QUICK_INNER:-}" ] && [ -n "$HAVE_TIMEOUT" ]; then
    local self rc limit=${OLARES_AUDIO_QUICK_LIMIT:-60}
    self=$(readlink -f "${BASH_SOURCE[0]}")
    OLARES_AUDIO_QUICK_INNER=1 timeout -k 5 "$limit" bash "$self" setup "$@"; rc=$?
    if [ "$rc" = 124 ] || [ "$rc" = 137 ]; then echo "setup --quick did not finish within $limit s" >&3; fi
    return "$rc"
  fi
  echo "== Before"; check
  before=$(failing)
  if ! sd_reachable; then
    echo
    echo "$NO_SD: nothing changed"
    return 5
  fi
  server=$(pulse_server)
  if is_pulseaudio_host && [ -z "$replace" ]; then
    echo
    echo "== Result"
    printf '  %-16s %s\n' "sound server" "$server, not PipeWire: left as it is" \
      "apply" "skipped" "boot self-check" "not installed (it keeps a PipeWire setup ready)" \
      "next" "to replace PulseAudio with PipeWire: bash ${BASH_SOURCE[0]} setup --replace-pulseaudio"
    return 3
  fi
  # Quick: no pipewire-pulse restart either, that is a restart of the session.
  [ -n "$quick" ] && SHARED_RESTARTED=1
  echo "== Repair"; repair || echo "  nothing had drifted"
  check >/dev/null
  if [ -n "$quick" ]; then
    install_ready
    applied="not run (--quick)"
    RECONNECT_RESULT="untouched (apply did not run)"
  elif [ "$MISSING" -gt 0 ] || { [ -n "$shared" ] && ! shared_mode; }; then
    echo "== Apply ($MISSING missing${shared:+, switching to the shared socket})"
    applied="ran: $MISSING items it installs were missing${shared:+, shared socket asked for}"
    apply_changes --persist-wbs "$replace" "$shared"
  else
    install_ready
    applied="skipped: nothing it installs was missing"
    RECONNECT_RESULT="untouched (apply did not run)"
  fi
  repair >/dev/null
  echo "== After"; check
  if shared_mode; then mode="shared socket in $LINK"; else mode="link $LINK -> $RUNDIR/pulse"; fi
  echo
  echo "== Result"
  printf '  %-16s %s\n' "sound server" "$(pulse_server)" "apps connect via" "$mode" "apply" "$applied" \
    "Bluetooth" "$RECONNECT_RESULT" "boot self-check" "$READY_RESULT" \
    "checks" "before: $before failing; now: $(failing) failing" \
    "after a reboot" "journalctl -u ${READY%.service} -b   (one line: ready / not ready)"
  if [ -n "$quick" ] && { [ "$MISSING" -gt 0 ] || { [ -n "$shared" ] && ! shared_mode; }; }; then
    echo "needs-apply"
    return 4
  fi
  [ "$(failing)" -eq 0 ]
}

# The full setup, run by the host's systemd so it outlives whoever started it
# (an init container that must not wait for apt). One at a time.
ASYNC=olares-bt-audio-apply
apply_async() {
  local self st
  self=$(readlink -f "${BASH_SOURCE[0]}")
  [ -f "$self" ] || { echo "cannot find this script on disk; copy it to the host first"; return 1; }
  sd_reachable || { echo "$NO_SD"; return 5; }
  st=$(systemctl is-active "$ASYNC.service" 2>/dev/null)
  case "$st" in
    active|activating|deactivating|reloading) echo "$ASYNC is already $st; not starting another (journalctl -u $ASYNC)"; return 0 ;;
  esac
  systemd-run --unit="$ASYNC" --collect --no-block --description="olares-bt-audio.sh setup" \
    --setenv=OLARES_AUDIO_USER="$USER_NAME" --setenv=LC_ALL=C /bin/bash "$self" setup "$@" \
    || { echo "systemd-run failed"; return 1; }
  echo "started $ASYNC in the background: journalctl -u $ASYNC -f"
}

# Separate bluetoothctl calls forget what a scan found the moment it stops,
# and pair then says "Device ... not available". One session keeps it.
pair() {
  local want=$1 mac
  bluetoothctl -- power on >/dev/null
  echo "Scanning 15 s for \"$want\" (it must be in pairing mode)..."
  mac=$( { echo "scan on"; sleep 15; echo "devices"; echo "scan off"; echo quit; } | STDIN=1 BT_TMO=40 bluetoothctl 2>/dev/null \
        | grep -E '^Device ' | grep -i -- "$want" | awk '{print $2}' | head -1 )
  [ -n "$mac" ] || { echo "not found; put it in pairing mode and retry"; exit 1; }
  echo "Found $mac; pairing"
  { echo "agent NoInputNoOutput"; echo "default-agent"; echo "scan on"; sleep 8; echo "pair $mac"; sleep 10;
    echo "trust $mac"; sleep 1; echo "connect $mac"; sleep 8; echo "scan off"; echo quit; } | STDIN=1 BT_TMO=60 bluetoothctl >/dev/null 2>&1
  bluetoothctl info "$mac" | grep -E 'Name|Paired|Trusted|Connected'
}

level() { python3 - "$1" "$2" <<'PY'
import wave, struct, math, sys
w = wave.open(sys.argv[1]); n = w.getnframes(); d = struct.unpack('<%dh' % n, w.readframes(n))
r = math.sqrt(sum(x*x for x in d) / max(n, 1)); p = max((abs(x) for x in d), default=0)
db = lambda v: 20 * math.log10(max(v, 1) / 32768)
print('%s: %.1f s, RMS %.1f dBFS, peak %.1f dBFS%s' % (sys.argv[2], n / 16000, db(r), db(p),
      '   <- digital silence' if p <= 2 else ''))
PY
}

# The device beeps before and after each take, so whoever is speaking knows
# when, without watching this terminal.
test_rec() {
  local mac=$1 card src snk tone=/tmp/olares-bt-tone.wav
  card=bluez_card.${mac//:/_}
  python3 -c "import math,struct,wave;w=wave.open('$tone','w');w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*660*i/16000))) for i in range(16000)));w.close()"
  chmod 644 "$tone"
  for prof in headset-head-unit-msbc headset-head-unit-cvsd; do
    "${AS_PULSE[@]}" pactl set-card-profile "$card" "$prof" || { echo "cannot switch to $prof"; continue; }
    sleep 2
    src=$("${AS_PULSE[@]}" pactl list sources short | awk '/bluez_input/{print $2; exit}')
    snk=$("${AS_PULSE[@]}" pactl list sinks short | awk '/bluez_output/{print $2; exit}')
    echo "$prof: speak from the first beep to the second (8 s)"; sleep 2
    "${AS_PULSE[@]}" paplay -d "$snk" "$tone"
    rm -f /tmp/olares-bt-test.wav
    "${AS_PULSE[@]}" timeout 8 parecord -d "$src" --rate=16000 --channels=1 --file-format=wav /tmp/olares-bt-test.wav
    "${AS_PULSE[@]}" paplay -d "$snk" "$tone"
    level /tmp/olares-bt-test.wav "$prof"
  done
  echo "CVSD with sound but mSBC silent = wideband speech is off (apply turns it on)."
}

case "${1:-check}" in
  check) check; [ "$(failing)" -eq 0 ] ;;
  setup) shift; setup "$@" ;;
  apply-async) shift; apply_async "$@" ;;
  apply) shift; apply "$@" ;;
  watch) watch ;;
  pair)  [ -n "${2:-}" ] || { echo "usage: $0 pair <name>"; exit 2; }; pair "$2" ;;
  test)  [ -n "${2:-}" ] || { echo "usage: $0 test <MAC>"; exit 2; }; test_rec "$2" ;;
  *) sed -n '2,24p' "$0"; exit 2 ;;
esac
