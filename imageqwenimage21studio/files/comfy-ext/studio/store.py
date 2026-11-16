"""studio.db: jobs and assets, kept apart from ComfyUI's own database."""
import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,            -- image | video | audio
  source TEXT NOT NULL,          -- upload | output | frame | trim | mask | edit
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  mime TEXT NOT NULL,
  bytes INTEGER NOT NULL DEFAULT 0,
  width INTEGER, height INTEGER,
  duration REAL,
  has_audio INTEGER NOT NULL DEFAULT 0,
  poster TEXT,
  job_id TEXT,
  starred INTEGER NOT NULL DEFAULT 0,
  deleted INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  md5 TEXT                       -- of the file as uploaded, before any conversion
);
CREATE INDEX IF NOT EXISTS assets_created ON assets(created);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,           -- also the ComfyUI prompt_id
  mode TEXT NOT NULL,
  variant TEXT NOT NULL,
  spec TEXT NOT NULL,            -- {prompt, mode, assets: [{id, role}], params, batch?, action?}
  used TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL,          -- queued | running | done | failed | cancelled | interrupted
  stage TEXT,
  step INTEGER, steps INTEGER,
  error TEXT,
  outputs TEXT NOT NULL DEFAULT '[]',
  parent_id TEXT, relation TEXT,
  starred INTEGER NOT NULL DEFAULT 0,
  deleted INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL, started REAL, finished REAL
);
CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
"""

JSON_FIELDS = {"spec", "used", "error", "outputs"}
ACTIVE = ("queued", "running")


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in JSON_FIELDS & d.keys():
        d[k] = json.loads(d[k]) if d[k] else None
    for k in ("starred", "deleted", "has_audio"):
        if k in d:
            d[k] = bool(d[k])
    return d


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.executescript(SCHEMA)
            if "md5" not in {r[1] for r in self.db.execute("PRAGMA table_info(assets)")}:
                self.db.execute("ALTER TABLE assets ADD COLUMN md5 TEXT")
            self.db.execute("CREATE INDEX IF NOT EXISTS assets_md5 ON assets(md5)")

    def _q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def _x(self, sql, args=()):
        with self.lock:
            self.db.execute(sql, args)

    # assets

    def add_asset(self, a):
        a = {"created": time.time(), "starred": 0, "deleted": 0, "has_audio": 0, **a}
        cols = ",".join(a)
        self._x("INSERT INTO assets (%s) VALUES (%s)" % (cols, ",".join("?" * len(a))), [int(v) if isinstance(v, bool) else v for v in a.values()])
        return self.asset(a["id"])

    def asset(self, aid):
        r = self._q("SELECT * FROM assets WHERE id=?", (aid,))
        return _row(r[0]) if r else None

    def asset_by_md5(self, md5):
        for r in self._q("SELECT * FROM assets WHERE md5=? AND deleted=0 ORDER BY created DESC", (md5,)):
            if os.path.exists(r["path"]):
                return _row(r)
        return None

    def assets_without_md5(self):
        return [_row(r) for r in self._q("SELECT id, path FROM assets WHERE md5 IS NULL AND deleted=0")]

    def assets(self, kind=None, source=None, q=None, starred=None, before=None, limit=60):
        sql, args = "SELECT * FROM assets WHERE deleted=0", []
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if source:
            sql += " AND source=?"
            args.append(source)
        else:
            sql += " AND source<>'mask'"
        if q:
            sql += " AND name LIKE ? ESCAPE '\\'"
            args.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if starred:
            sql += " AND starred=1"
        if before:
            sql += " AND created<?"
            args.append(float(before))
        sql += " ORDER BY created DESC LIMIT ?"
        args.append(int(limit))
        return [_row(r) for r in self._q(sql, args)]

    def update_asset(self, aid, **fields):
        if not fields:
            return self.asset(aid)
        sets = ",".join("%s=?" % k for k in fields)
        self._x("UPDATE assets SET %s WHERE id=?" % sets, [int(v) if isinstance(v, bool) else v for v in fields.values()] + [aid])
        return self.asset(aid)

    def asset_in_use(self, aid):
        for j in self.jobs_by_status(ACTIVE):
            if any(x.get("id") == aid for x in j["spec"].get("assets", [])):
                return True
        return False

    # jobs

    def add_job(self, j):
        j = {"created": time.time(), **j}
        for k in JSON_FIELDS & j.keys():
            j[k] = json.dumps(j[k])
        cols = ",".join(j)
        self._x("INSERT INTO jobs (%s) VALUES (%s)" % (cols, ",".join("?" * len(j))), list(j.values()))
        return self.job(j["id"])

    def job(self, jid):
        r = self._q("SELECT * FROM jobs WHERE id=?", (jid,))
        return _row(r[0]) if r else None

    def jobs(self, before=None, starred=None, limit=30):
        sql, args = "SELECT * FROM jobs WHERE deleted=0", []
        if starred:
            sql += " AND starred=1"
        if before:
            sql += " AND created<?"
            args.append(float(before))
        sql += " ORDER BY created DESC LIMIT ?"
        args.append(int(limit))
        return [_row(r) for r in self._q(sql, args)]

    def jobs_by_status(self, statuses):
        return [_row(r) for r in self._q("SELECT * FROM jobs WHERE status IN (%s) ORDER BY created" % ",".join("?" * len(statuses)), list(statuses))]

    def update_job(self, jid, **fields):
        if fields:
            for k in JSON_FIELDS & fields.keys():
                fields[k] = json.dumps(fields[k])
            sets = ",".join("%s=?" % k for k in fields)
            self._x("UPDATE jobs SET %s WHERE id=?" % sets, [int(v) if isinstance(v, bool) else v for v in fields.values()] + [jid])
        return self.job(jid)

