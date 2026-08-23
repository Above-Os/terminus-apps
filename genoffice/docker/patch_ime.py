#!/usr/bin/env python3
"""Enable KasmVNC IME Input Mode (client OS IME → remote session)."""
from pathlib import Path

BUNDLE = Path("/usr/share/kasmvnc/www/dist/main.bundle.js")
OLD = "UI.initSetting('enable_ime', false);"
NEW = "UI.initSetting('enable_ime', true); UI.forceSetting('enable_ime', true, false);"
text = BUNDLE.read_text(encoding="utf-8").replace("\r\n", "\n")
if OLD not in text:
    if "UI.initSetting('enable_ime', true)" in text:
        print(f"already patched {BUNDLE}")
        raise SystemExit(0)
    raise SystemExit(f"enable_ime snippet not found in {BUNDLE}")
BUNDLE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8", newline="\n")
print(f"patched enable_ime default in {BUNDLE}")
