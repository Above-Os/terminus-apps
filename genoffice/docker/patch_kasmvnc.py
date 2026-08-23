#!/usr/bin/env python3
"""Harden linuxserver KasmVNC for a long-lived office stream.

1. Guard the idle timer so a dropped websocket cannot throw lastActiveAt.
2. Stretch idle disconnect; do not auto-reconnect or inject fake keys
   (both made clicks miss and sessions flap through the Olares entrance).
3. Raise Xvnc frame rate / JPEG quality — linuxserver starts Xvnc without
   -FrameRate, so the stream defaults to a conservative encode path.
4. Turn on IME Input Mode so the client's OS IME (Windows Pinyin, etc.)
   can type CJK into the remote session. Default is off and localStorage
   would keep it off, so force it on.
"""
from pathlib import Path

WWW = Path("/usr/share/kasmvnc/www")
BUNDLE = WWW / "dist/main.bundle.js"
ERR = WWW / "dist/error_handler.bundle.js"
XVNC_RUN = Path("/etc/s6-overlay/s6-rc.d/svc-kasmvnc/run")

IDLE_OLD = """      UI._sessionTimeoutInterval = setInterval(function () {
        var timeSinceLastActivityInS = (Date.now() - UI.rfb.lastActiveAt) / 1000;
        var idleDisconnectInS = 1200; //20 minute default 

        if (Number.isFinite(parseFloat(UI.rfb.idleDisconnect))) {
          idleDisconnectInS = parseFloat(UI.rfb.idleDisconnect) * 60;
        }

        if (timeSinceLastActivityInS > idleDisconnectInS) {
          parent.postMessage({
            action: 'idle_session_timeout',
            value: 'Idle session timeout exceeded'
          }, '*');
        } else {
          //send keep-alive
          UI.rfb.sendKey(1, null, false);
        }
      }, 5000);"""

IDLE_NEW = """      UI._sessionTimeoutInterval = setInterval(function () {
        if (!UI.rfb) { return; }
        var timeSinceLastActivityInS = (Date.now() - UI.rfb.lastActiveAt) / 1000;
        var idleDisconnectInS = 604800;

        if (Number.isFinite(parseFloat(UI.rfb.idleDisconnect))) {
          idleDisconnectInS = parseFloat(UI.rfb.idleDisconnect) * 60;
        }

        if (timeSinceLastActivityInS > idleDisconnectInS) {
          parent.postMessage({
            action: 'idle_session_timeout',
            value: 'Idle session timeout exceeded'
          }, '*');
        }
      }, 5000);"""

XVNC_OLD = """    -websocketPort 6901 \\
    -interface 0.0.0.0 \\
    -Log *:stdout:10"""

XVNC_NEW = """    -websocketPort 6901 \\
    -interface 0.0.0.0 \\
    -FrameRate=60 \\
    -DynamicQualityMin=7 \\
    -DynamicQualityMax=9 \\
    -Log *:stdout:10"""


def must_replace(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    old = old.replace("\r\n", "\n")
    new = new.replace("\r\n", "\n")
    if old not in text:
        raise SystemExit(f"{label}: expected snippet not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"patched {label} in {path}")


def main() -> None:
    must_replace(BUNDLE, IDLE_OLD, IDLE_NEW, "idle interval")
    must_replace(
        BUNDLE,
        "UI.initSetting('idle_disconnect', 20);",
        "UI.initSetting('idle_disconnect', 10080);",
        "idle_disconnect default",
    )
    # Leave UI.initSetting('reconnect', false) as shipped.
    must_replace(
        BUNDLE,
        "UI.initSetting('enable_ime', false);",
        "UI.initSetting('enable_ime', true); UI.forceSetting('enable_ime', true, false);",
        "enable_ime default",
    )

    err = ERR.read_text(encoding="utf-8").replace("\r\n", "\n")
    needle = 'var allowedErrors = ["The user has exited the lock before this request was completed."];'
    if needle not in err:
        raise SystemExit(f"allowedErrors snippet not found in {ERR}")
    err = err.replace(
        needle,
        needle
        + """

      if (event.message && event.message.indexOf("lastActiveAt") !== -1) {
        window.location.reload();
        return false;
      }""",
        1,
    )
    ERR.write_text(err, encoding="utf-8")
    print(f"patched lastActiveAt reload in {ERR}")

    must_replace(XVNC_RUN, XVNC_OLD, XVNC_NEW, "xvnc encode flags")


if __name__ == "__main__":
    main()
