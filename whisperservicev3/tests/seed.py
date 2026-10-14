import fcntl,json,pathlib,sqlite3,time,hashlib,requests,traceback,subprocess
backup=pathlib.Path('/tmp/.upgrade-backups');backup.mkdir(exist_ok=True)
lock=open(backup/'release-seed.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
out=backup/'seed-result.json'
if out.exists() and json.loads(out.read_text()).get('passed'):print(out.read_text());raise SystemExit(0)
try:
    for _ in range(90):
        try:
            if requests.get('http://localhost:8000/health',timeout=5).status_code==200:break
        except requests.RequestException:pass
        time.sleep(2)
    sample='/cache/hf/hub/assets/whisper108-test-jfk.flac'
    subprocess.run(['ffmpeg','-y','-i',sample,str(backup/'seed.wav')],check=True,capture_output=True)
    with open(backup/'seed.wav','rb') as audio:
        r=requests.post('http://localhost:8000/service/transcribe',params={'model':'large-v3','device':'cuda','language':'en'},files={'file':('seed.wav',audio,'audio/wav')},timeout=60)
    r.raise_for_status();identifier=r.json()['identifier']
    for _ in range(150):
        task=requests.get('http://localhost:8000/task/'+identifier,timeout=10).json()
        if task['status'] in ['completed','failed']:break
        time.sleep(2)
    assert task['status']=='completed',task
    original=sqlite3.connect('/app/records.db');saved=sqlite3.connect(backup/'records.db');original.backup(saved)
    assert saved.execute('PRAGMA integrity_check').fetchone()[0]=='ok';saved.close();original.close()
    # Sentinel represents historical user audio, which must survive the new cleaner.
    sentinel=pathlib.Path('/tmp/retention-history-sentinel.wav');sentinel.write_bytes(pathlib.Path(sample).read_bytes())
    before={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in pathlib.Path('/tmp').iterdir() if p.is_file()}
    (backup/'legacy-inventory.json').write_text(json.dumps(before))
    result={'passed':True,'identifier':identifier,'task':task,'legacy_files':len(before),'database_integrity':'ok'}
except Exception:result={'passed':False,'error':traceback.format_exc()}
out.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
