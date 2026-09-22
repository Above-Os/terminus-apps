// Run with Node 24+: node tests/clawdbot-schema-migration.test.mjs
// For the real pinned image, set MIGRATION_V19_FIXTURE to a schema-v19 backup.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
const chart = fs.readFileSync(new URL('../clawdbot/templates/configmap-sqlite-migration.yaml', import.meta.url), 'utf8');
const source = chart.split('  migrate-agent-schema.mjs: |\n')[1].split('\n').map(line => line.startsWith('    ') ? line.slice(4) : line).join('\n');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'clawdbot-schema-test-'));
const script = path.join(root, 'migration.mjs');
fs.writeFileSync(script, source);
function run(state) {
  return spawnSync(process.execPath, [script], { env: { ...process.env, HOME: state, OPENCLAW_HOME: state, OPENCLAW_STATE_DIR: state }, encoding: 'utf8', timeout: 60000 });
}
function dbPath(state) {
  const dir = path.join(state, 'agents/main/agent');
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, 'openclaw-agent.sqlite');
}
function pass(result) { assert.equal(result.status, 0, result.stdout + result.stderr); }
try {
  const state = path.join(root, 'guards');
  pass(run(state));
  console.log('PASS fresh install');
  const file = dbPath(state);
  let db = new DatabaseSync(file); db.exec('PRAGMA user_version=99'); db.close();
  const before = fs.readFileSync(file);
  let result = run(state); assert.notEqual(result.status, 0); assert.match(result.stderr, /Unsupported schema 99/); assert.deepEqual(fs.readFileSync(file), before);
  console.log('PASS unknown schema refused without changes');
  fs.unlinkSync(file); fs.symlinkSync(path.join(root, 'target.sqlite'), file);
  db = new DatabaseSync(path.join(root, 'target.sqlite')); db.close();
  result = run(state); assert.notEqual(result.status, 0); assert.match(result.stderr, /Unsafe database file/);
  console.log('PASS symlink refused');
  fs.unlinkSync(file); fs.writeFileSync(file, 'not a database');
  result = run(state); assert.notEqual(result.status, 0); assert.equal(fs.readFileSync(file, 'utf8'), 'not a database');
  console.log('PASS corrupt database refused without changes');
  fs.unlinkSync(file); db = new DatabaseSync(file); db.exec('PRAGMA user_version=21'); db.close();
  pass(run(state)); console.log('PASS current schema is a no-op');
  if (process.env.MIGRATION_V19_FIXTURE) {
    const state = path.join(root, 'integration'); const file = dbPath(state);
    fs.copyFileSync(process.env.MIGRATION_V19_FIXTURE, file);
    const marker = 'Olares migration regression: preserve conversation';
    db = new DatabaseSync(file);
    assert.equal(db.prepare('PRAGMA user_version').get().user_version, 19);
    const key = 'agent:main:olares-schema-regression';
    const id = '00000000-0000-4000-8000-000000000021';
    const now = Date.now();
    db.prepare('INSERT INTO session_nodes(session_key,current_session_id,entry_json,updated_at,label) VALUES (?,?,?,?,?)').run(key, id, JSON.stringify({sessionId:id,updatedAt:now,label:marker}), now, marker);
    const count = db.prepare('SELECT count(*) AS n FROM session_nodes').get().n; db.close();
    fs.writeFileSync(path.join(state, 'openclaw.json'), '{"update":{"checkOnStart":false}}\n');
    const config = fs.readFileSync(path.join(state, 'openclaw.json'));
    fs.mkdirSync(path.join(state, 'workspace')); fs.writeFileSync(path.join(state, 'workspace/marker'), marker);
    pass(run(state));
    db = new DatabaseSync(file, {readOnly:true});
    assert.equal(db.prepare('PRAGMA user_version').get().user_version, 21);
    assert.equal(db.prepare('PRAGMA integrity_check').get().integrity_check, 'ok');
    assert.equal(db.prepare('PRAGMA foreign_key_check').all().length, 0);
    assert.equal(db.prepare('SELECT count(*) AS n FROM session_nodes').get().n, count);
    const row = db.prepare('SELECT entry_json,label FROM session_nodes WHERE session_key=?').get(key);
    assert.equal(row.label, marker); assert.equal(JSON.parse(row.entry_json).label, marker); db.close();
    assert.deepEqual(fs.readFileSync(path.join(state, 'openclaw.json')), config);
    assert.equal(fs.readFileSync(path.join(state, 'workspace/marker'), 'utf8'), marker);
    const backups = path.join(state, 'migration-backups/2026.9.5-schema-21/main');
    const files = fs.readdirSync(backups).filter(f => f.endsWith(".sqlite")); assert.equal(files.length, 1);
    const backup = path.join(backups, files[0]);
    assert.equal(fs.statSync(backup).mode & 0o777, 0o600);
    db = new DatabaseSync(backup, {readOnly:true}); assert.equal(db.prepare('PRAGMA user_version').get().user_version,19); assert.equal(db.prepare('SELECT count(*) AS n FROM session_nodes').get().n,count); assert.equal(db.prepare('PRAGMA integrity_check').get().integrity_check,'ok'); db.close();
    pass(run(state)); assert.deepEqual(fs.readdirSync(backups).filter(f => f.endsWith(".sqlite")),files);
    console.log('PASS real v19 -> v21, conversation/config/workspace preservation, verified v19 backup and idempotence');
  } else console.log('SKIP pinned-image integration (MIGRATION_V19_FIXTURE not supplied)');
} finally { fs.rmSync(root, {recursive:true,force:true}); }
