// OpenClaw 2026.9.1 -> 2026.9.4: schema v19 gained this canonical index.
// Run offline, as an initContainer, before any Gateway/CLI writer starts.
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync, backup } = require('node:sqlite');
const state = process.env.OPENCLAW_STATE_DIR || '/home/node/.openclaw';
const index = 'idx_agent_session_nodes_active';
const sql = `CREATE INDEX ${index} ON session_nodes(session_key) WHERE archived_at IS NULL`;
const normalize = value => value.replace(/\s+/g, ' ').trim().replace(/;$/, '');
const check = db => {
  const rows = db.prepare('PRAGMA integrity_check').all();
  if (rows.length !== 1 || rows[0].integrity_check !== 'ok') throw new Error('SQLite integrity check failed');
  if (db.prepare('PRAGMA foreign_key_check').all().length) throw new Error('SQLite foreign key check failed');
};
async function main() {
  const agents = path.join(state, 'agents');
  if (!fs.existsSync(agents)) return console.log('[sqlite-migrate] fresh install; skip');
  for (const entry of fs.readdirSync(agents, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = path.join(agents, entry.name, 'agent', 'openclaw-agent.sqlite');
    if (!fs.existsSync(file)) continue;
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || stat.nlink !== 1) throw new Error('Unsafe database file');
    const db = new DatabaseSync(file);
    try {
      const existing = db.prepare('SELECT sql FROM sqlite_master WHERE name=?').get(index);
      if (existing) {
        if (normalize(existing.sql) !== normalize(sql)) throw new Error('Unexpected index definition; refusing replacement');
        console.log(`[sqlite-migrate] ${entry.name}: already current`);
        continue;
      }
      if (db.prepare('PRAGMA user_version').get().user_version !== 19) throw new Error('Unsupported schema version; refusing migration');
      const columns = db.prepare('PRAGMA table_info(session_nodes)').all().map(row => row.name);
      if (!['session_key', 'archived_at'].every(name => columns.includes(name))) throw new Error('Missing session_nodes columns');
      check(db);
      const dir = path.join(state, 'migration-backups', '2026.9.4-session-index', entry.name);
      fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
      const copy = path.join(dir, `${Date.now()}-${process.pid}.sqlite`);
      await backup(db, copy);
      fs.chmodSync(copy, 0o600);
      const saved = new DatabaseSync(copy, { readOnly: true });
      try { check(saved); } finally { saved.close(); }
      db.exec('BEGIN IMMEDIATE');
      try {
        db.exec(sql);
        check(db);
        db.exec('COMMIT');
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
      console.log(`[sqlite-migrate] ${entry.name}: index created; verified backup retained`);
    } finally { db.close(); }
  }
}
main().catch(error => { console.error('[sqlite-migrate]', error.message); process.exitCode = 1; });
