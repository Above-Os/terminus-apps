"""Disposable official-runtime migration regression; never use a live state directory."""
import os,json,pathlib,subprocess,threading,http.server,uuid,sqlite3,shutil,time,argparse,sys,tempfile
ROOT = None
requests=[]
class Mock(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))));requests.append(body)
  text='MIGRATION_ASSISTANT_RETAINED';base={'id':'fixture-completion','object':'chat.completion','created':1,'model':'test'}
  if body.get('stream'):
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
   for delta,finish in [({'role':'assistant','content':text},None),({},'stop')]:
    self.wfile.write(('data: '+json.dumps({**base,'object':'chat.completion.chunk','choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n').encode())
   self.wfile.write(b'data: [DONE]\n\n')
  else:
   data=json.dumps({**base,'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':5,'total_tokens':25}}).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
def run(version,home,args,label):
 entry=ROOT/f'runtime-{version}/node_modules/openclaw/openclaw.mjs'
 if not entry.exists():raise RuntimeError(f'Runtime missing: {version}')
 state=home/'.openclaw';env={k:v for k,v in os.environ.items() if not k.startswith(('OPENCLAW_','CLAWDBOT_','MOLTBOT_'))}
 env.update(HOME=str(home),OPENCLAW_HOME=str(home),OPENCLAW_STATE_DIR=str(state),OPENCLAW_CONFIG_PATH=str(state/'openclaw.json'),OPENCLAW_WORKSPACE_DIR=str(state/'workspace'),OPENCLAW_NO_RESPAWN='1',CI='1')
 r=subprocess.run(['node',str(entry),*args],env=env,capture_output=True,text=True,timeout=240)
 (home/(label+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(f'{label}: exit {r.returncode}; see {home/(label+".log")}')
 return r.stdout

def schemas(state):
 result={}
 for p in state.rglob('*.sqlite'):
  if 'backup' in str(p.relative_to(state)):continue
  # Processes have exited. Copy the DB and sidecars together, then let SQLite
  # recover/checkpoint the disposable copy; immutable mode would ignore WAL.
  with tempfile.TemporaryDirectory() as scratch:
   snapshot=pathlib.Path(scratch)/p.name
   shutil.copy2(p,snapshot)
   for suffix in ('-wal','-shm'):
    sidecar=pathlib.Path(str(p)+suffix)
    if sidecar.exists():shutil.copy2(sidecar,pathlib.Path(str(snapshot)+suffix))
   db=sqlite3.connect(snapshot)
   try:
    assert db.execute('pragma integrity_check').fetchall()==[('ok',)],str(p)
    assert not db.execute('pragma foreign_key_check').fetchall(),str(p)
    result[str(p.relative_to(state))]=db.execute('pragma user_version').fetchone()[0]
   finally:db.close()
 return result

def case(v,port):
 home=ROOT/'native-results'/(v+'-'+str(int(time.time())));state=home/'.openclaw';ws=state/'workspace';ws.mkdir(parents=True)
 marker=ws/'MIGRATION_KEEP.md';marker.write_text('migration workspace must survive\n')
 cfg={'gateway':{'mode':'local','bind':'loopback','auth':{'mode':'token','token':'migration-fixture-not-a-real-secret'}},'agents':{'defaults':{'workspace':str(ws),'model':{'primary':'fixture/test'},'memorySearch':{'enabled':False}}},'models':{'providers':{'fixture':{'baseUrl':f'http://127.0.0.1:{port}/v1','apiKey':'fixture','api':'openai-completions','models':[{'id':'test','name':'Fixture model','contextWindow':32768,'maxTokens':1024}]}}},'update':{'checkOnStart':False,'auto':{'enabled':False}}}
 (state/'openclaw.json').write_text(json.dumps(cfg));session=str(uuid.uuid4())
 run(v,home,['doctor','--fix','--non-interactive'],'source-doctor')
 run(v,home,['agent','--local','--agent','main','--session-id',session,'--message','MIGRATION_USER_RETAINED','--json'],'source-chat')
 old=schemas(state);assert old,'no source databases'
 shutil.copytree(state,home/'pre-upgrade-backup')
 run('2026.9.9',home,['doctor','--fix','--non-interactive'],'target-doctor')
 new=schemas(state)
 assert new.get('state/openclaw.sqlite')==19,new
 assert new.get('agents/main/agent/openclaw-agent.sqlite')==24,new
 assert marker.read_text()=='migration workspace must survive\n'
 repaired=json.loads((state/'openclaw.json').read_text());assert repaired['gateway']['auth']['token']==cfg['gateway']['auth']['token'];assert repaired['models']['providers']['fixture']['baseUrl']==cfg['models']['providers']['fixture']['baseUrl']
 requests.clear()
 run('2026.9.9',home,['agent','--local','--agent','main','--session-id',session,'--message','MIGRATION_POST_UPGRADE','--json'],'target-chat')
 transcript=json.dumps(requests)
 assert 'MIGRATION_USER_RETAINED' in transcript,'old user transcript lost'
 assert 'MIGRATION_ASSISTANT_RETAINED' in transcript,'old assistant transcript lost'
 run('2026.9.9',home,['doctor','--fix','--non-interactive'],'target-doctor-repeat')
 assert schemas(state)==new,'schema changed on second repair'
 return {'source':v,'target':'2026.9.9','status':'passed','sourceSchemas':old,'targetSchemas':new,'evidence':str(home),'checks':['SQLite integrity and FK','real old user and assistant transcript in post-upgrade model context','workspace file','Gateway token','provider configuration','Doctor repeat']}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,required=True,help='Disposable directory containing runtime-VERSION/node_modules/openclaw');ap.add_argument('versions',nargs='+');args=ap.parse_args();ROOT=args.root.resolve()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=server.serve_forever,daemon=True).start();results=[]
 for v in args.versions:
  try:r=case(v,server.server_port)
  except Exception as e:r={'source':v,'target':'2026.9.9','status':'failed','reason':str(e)}
  results.append(r);print(json.dumps(r),flush=True)
 (ROOT/'native-results.json').write_text(json.dumps(results,indent=2));server.shutdown()
 sys.exit(0 if all(r['status']=='passed' for r in results) else 1)
