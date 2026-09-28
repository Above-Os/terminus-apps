// Run with Node.js 24+: node --test clawdbot/tests/migration-current-schema.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { DatabaseSync } = require('node:sqlite');
const chart = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(chart, 'templates/configmap-sqlite-migration.yaml'), 'utf8')
  .split('  migrate-agent-schema.mjs: |\n')[1].split('\n').map(line => line.replace(/^    /, '')).join('\n');
function fixture(t, version) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'openclaw-schema-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const script = path.join(dir, 'migration.mjs');
  fs.writeFileSync(script, source);
  const file = path.join(dir, 'agents/main/agent/openclaw-agent.sqlite');
  if (version !== undefined) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const db = new DatabaseSync(file);
    db.exec(`CREATE TABLE proof(value TEXT); INSERT INTO proof VALUES ('preserve me'); PRAGMA user_version=${version};`);
    db.close();
  }
  return { dir, file, run: () => spawnSync(process.execPath, [script], {
    env: { ...process.env, OPENCLAW_STATE_DIR: dir }, encoding: 'utf8', timeout: 10000,
  }) };
}
test('fresh install does not create a database', t => {
  const f = fixture(t); const r = f.run();
  assert.equal(r.status, 0, r.stderr); assert.match(r.stdout, /fresh install; skip/);
  assert.equal(fs.existsSync(f.file), false);
});
test('schema 23 survives repeated init runs without modifying the database', t => {
  const f = fixture(t, 23), before = fs.readFileSync(f.file);
  for (let i = 0; i < 2; i++) {
    const r = f.run(); assert.equal(r.status, 0, r.stderr); assert.match(r.stdout, /already current/);
    assert.deepEqual(fs.readFileSync(f.file), before);
  }
  assert.equal(fs.existsSync(path.join(f.dir, 'migration-backups')), false);
});
for (const version of [18, 24]) {
  test(`unsupported schema ${version} is rejected without changing data`, t => {
    const f = fixture(t, version), before = fs.readFileSync(f.file), r = f.run();
    assert.equal(r.status, 1); assert.match(r.stderr, new RegExp(`Unsupported schema ${version}`));
    assert.deepEqual(fs.readFileSync(f.file), before);
  });
}
test('current schema with broken foreign keys is still rejected', t => {
  const f = fixture(t, 23), db = new DatabaseSync(f.file);
  db.exec('PRAGMA foreign_keys=OFF; CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER REFERENCES parent(id)); INSERT INTO child VALUES(1);');
  db.close(); const before = fs.readFileSync(f.file), r = f.run();
  assert.equal(r.status, 1); assert.match(r.stderr, /foreign key check failed/);
  assert.deepEqual(fs.readFileSync(f.file), before);
});
