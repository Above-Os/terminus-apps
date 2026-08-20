#!/usr/bin/env python3
"""Harden the linuxserver KasmVNC web client against idle disconnect crashes.

The bundled UI starts a 5s interval that reads UI.rfb.lastActiveAt with no
null check. After ~20 minutes idle (or any websocket drop) rfb is gone and
the page throws Uncaught TypeError ... lastActiveAt. Reconnect is also
hard-disabled outside Kasm Workspaces.
"""
from pathlib import Path

WWW = Path("/usr/share/kasmvnc/www")
BUNDLE = WWW / "dist/main.bundle.js"
ERR = WWW / "dist/error_handler.bundle.js"
KCLIENT = Path("/kclient/public/index.html")

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
        } else {
          //send keep-alive
          UI.rfb.sendKey(1, null, false);
        }
      }, 5000);"""


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
        "UI.initSetting('reconnect', false);",
        "UI.initSetting('reconnect', true);",
        "reconnect default",
    )
    must_replace(
        BUNDLE,
        "UI.initSetting('idle_disconnect', 20);",
        "UI.initSetting('idle_disconnect', 10080);",
        "idle_disconnect default",
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

    kclient = KCLIENT.read_text(encoding="utf-8").replace("\r\n", "\n")
    old_src = "vnc/index.html?autoconnect=1&resize=remote&clipboard_up=true&clipboard_down=true&clipboard_seamless=true&show_control_bar=true"
    new_src = old_src + "&reconnect=true&idle_disconnect=10080"
    if old_src not in kclient:
        raise SystemExit(f"kclient iframe src not found in {KCLIENT}")
    KCLIENT.write_text(kclient.replace(old_src, new_src, 1), encoding="utf-8")
    print(f"patched kclient iframe in {KCLIENT}")


if __name__ == "__main__":
    main()
