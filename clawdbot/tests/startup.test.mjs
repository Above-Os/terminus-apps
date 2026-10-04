import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const chart = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
function block(file, key) {
  const text = fs.readFileSync(path.join(chart, 'templates', file), 'utf8');
  const match = text.match(new RegExp(`^  ${key}: \\|\\n([\\s\\S]*?)(?=^  [a-zA-Z].*:|$(?![\\s\\S]))`, 'm'));
  assert.ok(match, key);
  return match[1].split('\n').filter(l => !l || l.startsWith('    ')).map(l => l.slice(4)).join('\n');
}
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'clawdbot-startup-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}
function shim(t) {
  const dir = fixture(t);
  fs.mkdirSync(path.join(dir, 'bundled'));
  const node = path.join(dir, 'fake-node');
  fs.writeFileSync(node, '#!/bin/sh\nprintf "%s\\n" "$@"\n', {mode:0o755});
  const script = block('configmap-openclaw-bin.yaml','openclaw').replaceAll('/usr/local/bin/node',node).replaceAll('/app',path.join(dir,'bundled'));
  const bin = path.join(dir,'openclaw');fs.writeFileSync(bin,script,{mode:0o755});
  return { dir, bin };
}
test('ordinary CLI dispatches to the bundled entry, preserving argument boundaries', t => {
  const {bin}=shim(t);const r=spawnSync(bin,['doctor','--fix','--non-interactive','a b'],{encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/bundled\/openclaw\.mjs\ndoctor\n--fix\n--non-interactive\na b/);
});
test('mutating updater commands refuse before touching the core; status and help work',t=>{
  const {bin}=shim(t);
  for(const args of [['update'],['update','--yes'],['update','repair'],['update','--tag','latest']]) {
    const r=spawnSync(bin,args,{encoding:'utf8'});assert.equal(r.status,1);assert.match(r.stderr,/Olares Marketplace/);assert.equal(r.stdout,'');
  }
  for(const arg of ['status','--help','-h'])assert.equal(spawnSync(bin,['update',arg]).status,0);
});
test('a persisted npm-global OpenClaw cannot shadow the chart shim in normal PATH',t=>{
  const {dir,bin}=shim(t);const npm=path.join(dir,'npm-global','bin');fs.mkdirSync(npm,{recursive:true});
  fs.writeFileSync(path.join(npm,'openclaw'),'#!/bin/sh\necho WRONG_PERSISTED_CORE\n',{mode:0o755});
  const r=spawnSync('/bin/sh',['-c','openclaw --version'],{env:{...process.env,PATH:`${path.dirname(bin)}:${npm}:/usr/bin:/bin`},encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);assert.doesNotMatch(r.stdout,/WRONG/);assert.match(r.stdout,/bundled\/openclaw.mjs/);
});
test('Gateway wrapper withdraws its PID during failed-start backoff',async t=>{
  const dir=fixture(t); const stub=path.join(dir,'node');
  fs.writeFileSync(stub,'#!/bin/sh\nsleep 0.3\nexit 78\n',{mode:0o755});
  let script=block('configmap-gateway-ipc.yaml','gateway-entrypoint.sh').replaceAll('/usr/local/bin/node',stub).replaceAll('/tmp/',dir+'/').replace('cd /app',`cd '${dir}'`);
  const file=path.join(dir,'entry.sh');fs.writeFileSync(file,script);
  const child=spawn('/bin/bash',[file],{detached:true,env:{...process.env,OPENCLAW_GATEWAY_RESTART_SENTINEL:path.join(dir,'sentinel'),OPENCLAW_GATEWAY_RESTART_DELAY_SECONDS:'30'},stdio:['ignore','pipe','pipe']});
  t.after(()=>{try{process.kill(-child.pid,'SIGTERM')}catch{}});
  let out='';child.stdout.on('data',d=>out+=d);
  for(let n=0;n<100&&!out.includes('code=78');n++)await new Promise(r=>setTimeout(r,30));
  assert.match(out,/code=78/);assert.equal(fs.existsSync(path.join(dir,'openclaw-gateway.pid')),false);
});
test('readiness refuses a healthy sibling bridge when the owned Gateway is missing',t=>{
  const dir=fixture(t);const deployment=fs.readFileSync(path.join(chart,'templates/deployment.yaml'),'utf8');
  const probe=deployment.split('\n').find(l=>l.includes('const fs=require("fs")')).trim().slice(2).replaceAll('/tmp/openclaw-gateway.pid',path.join(dir,'pid'));
  // Stub HTTP with 200: this recreates the misleading sibling /readyz response.
  const run=()=>spawnSync(process.execPath,['-e','global.fetch=async()=>({ok:true});'+probe],{encoding:'utf8'});
  assert.equal(run().status,1);
  fs.writeFileSync(path.join(dir,'pid'),String(process.pid));assert.equal(run().status,0);
  fs.writeFileSync(path.join(dir,'pid'),'0');assert.equal(run().status,1);
});
