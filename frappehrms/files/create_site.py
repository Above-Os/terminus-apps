"""Create a Frappe site on an already-provisioned Olares MariaDB database."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path


def _noop_setup_database(*_args, **_kwargs) -> None:
    print(
        "Skipping MariaDB user/database creation; using Olares middleware credentials",
        flush=True,
    )


def _rewrite_user_arg(func, args, kwargs, db_user: str):
    """Force the MySQL user to the middleware account, not the database name."""
    kwargs = dict(kwargs)
    if "user" in kwargs:
        kwargs["user"] = db_user
        return args, kwargs
    try:
        params = list(inspect.signature(func).parameters)
        args = list(args)
        if "user" in params:
            idx = params.index("user")
            if idx < len(args):
                args[idx] = db_user
            else:
                kwargs["user"] = db_user
        elif len(args) >= 4:
            args[3] = db_user
    except (TypeError, ValueError):
        args = list(args)
        if len(args) >= 4:
            args[3] = db_user
    return tuple(args), kwargs


def _patch_middleware_db_user(db_user: str, db_name: str) -> None:
    """Olares 1.12.7 names the MariaDB user with hyphens and the database with
    an underscore. Older Frappe ignores site_config db_user and authenticates as
    db_name, which then fails with Access denied.
    """
    import frappe

    orig_init = frappe.init

    def _init(*args, **kwargs):
        orig_init(*args, **kwargs)
        frappe.conf.db_user = db_user
        frappe.conf.db_name = db_name

    frappe.init = _init

    try:
        import frappe.installer as installer
    except ImportError:
        installer = None
    else:
        orig_make_conf = getattr(installer, "make_conf", None)
        if orig_make_conf is not None:

            def _make_conf(*args, **kwargs):
                orig_make_conf(*args, **kwargs)
                frappe.conf.db_user = db_user
                frappe.conf.db_name = db_name
                site = kwargs.get("site") or (
                    args[0] if args else os.environ.get("SITE_NAME", "frontend")
                )
                cfg_path = (
                    Path("/home/frappe/frappe-bench/sites") / site / "site_config.json"
                )
                if cfg_path.exists():
                    try:
                        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        cfg = {}
                    cfg["db_user"] = db_user
                    cfg["db_name"] = db_name
                    cfg_path.write_text(
                        json.dumps(cfg, indent=1) + "\n", encoding="utf-8"
                    )

            installer.make_conf = _make_conf

    try:
        from frappe.database.db_manager import DbManager
    except ImportError:
        DbManager = None
    if DbManager is not None:
        orig_restore = getattr(DbManager, "restore_database", None)
        if orig_restore is not None:
            raw = (
                orig_restore.__func__
                if isinstance(orig_restore, staticmethod)
                else orig_restore
            )

            def _restore(*args, **kwargs):
                print(
                    f"Restoring {db_name!r} as middleware user {db_user!r}",
                    flush=True,
                )
                args, kwargs = _rewrite_user_arg(raw, args, kwargs, db_user)
                return raw(*args, **kwargs)

            DbManager.restore_database = staticmethod(_restore)

    try:
        from frappe.database.mariadb.database import MariaDBDatabase
    except ImportError:
        return

    orig_gcs = MariaDBDatabase.get_connection_settings

    def _gcs(self):
        settings = orig_gcs(self)
        settings["user"] = db_user
        for key in ("database", "db"):
            if key in settings:
                settings[key] = db_name
        self.user = db_user
        return settings

    MariaDBDatabase.get_connection_settings = _gcs

    orig_db_init = MariaDBDatabase.__init__

    def _db_init(self, *args, **kwargs):
        orig_db_init(self, *args, **kwargs)
        self.user = db_user
        if getattr(self, "cur_db_name", None) in (None, "", db_user):
            self.cur_db_name = db_name

    MariaDBDatabase.__init__ = _db_init


def main() -> None:
    bench = Path("/home/frappe/frappe-bench")
    sites = bench / "sites"
    os.chdir(sites)

    site = os.environ.get("SITE_NAME", "frontend")
    db_name = os.environ["DB_NAME"]
    db_user = os.environ.get("DB_USER") or db_name
    db_password = os.environ["DB_PASSWORD"]
    db_host = os.environ["DB_HOST"]
    db_port = int(os.environ.get("DB_PORT") or 3306)
    admin_password = os.environ["ADMIN_PASSWORD"]

    print(
        f"Olares MariaDB db_name={db_name!r} db_user={db_user!r}",
        flush=True,
    )

    site_dir = sites / site
    site_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = site_dir / "site_config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cfg = {}
    cfg.update(
        {
            "db_host": db_host,
            "db_port": db_port,
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_password,
            "db_type": "mariadb",
        }
    )
    cfg_path.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")

    import frappe.database as frappe_database
    import frappe.database.mariadb.setup_db as mariadb_setup

    frappe_database.setup_database = _noop_setup_database
    mariadb_setup.setup_database = _noop_setup_database
    _patch_middleware_db_user(db_user, db_name)

    from frappe.installer import _new_site

    kwargs = {
        "db_name": db_name,
        "site": site,
        "admin_password": admin_password,
        "verbose": True,
        "force": True,
        "db_password": db_password,
        "db_type": "mariadb",
        "db_host": db_host,
        "db_port": db_port,
        "install_apps": ["erpnext", "hrms"],
    }
    params = inspect.signature(_new_site).parameters
    if "db_user" in params:
        kwargs["db_user"] = db_user
    if "setup_db" in params:
        kwargs["setup_db"] = False
    if "install_apps" not in params:
        kwargs.pop("install_apps")

    _new_site(**kwargs)
    (bench / "sites" / "currentsite.txt").write_text(site + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
