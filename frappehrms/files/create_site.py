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
