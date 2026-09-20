"""Force Frappe to log in as the Olares MariaDB username.

This image's frappe.connect() always uses conf.db_name as the MySQL user.
On Olares 1.12.7 the username has hyphens and the database name uses an
underscore, so that login fails with Access denied.
"""

from __future__ import annotations

import builtins
import os

_DB_USER = os.environ.get("DB_USER")
_DB_NAME = os.environ.get("DB_NAME")
_patched = False

if _DB_USER:
    _orig_import = builtins.__import__

    def _patch_get_db() -> None:
        global _patched
        if _patched:
            return
        try:
            import frappe.database as dbmod
        except Exception:
            return
        orig = getattr(dbmod, "get_db", None)
        if orig is None:
            return

        def get_db(
            host=None,
            user=None,
            password=None,
            port=None,
            cur_db_name=None,
            socket=None,
        ):
            return orig(
                host=host,
                user=_DB_USER,
                password=password,
                port=port,
                cur_db_name=_DB_NAME or cur_db_name,
                socket=socket,
            )

        dbmod.get_db = get_db
        _patched = True

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        mod = _orig_import(name, globals, locals, fromlist, level)
        if name == "frappe.database" or name.startswith("frappe.database."):
            _patch_get_db()
        return mod

    builtins.__import__ = _import
