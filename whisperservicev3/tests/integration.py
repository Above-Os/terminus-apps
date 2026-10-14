import fcntl, hashlib, io, json, os, pathlib, subprocess, time, traceback
from concurrent.futures import ThreadPoolExecutor
import requests

lock=open('/state/retention-integration.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
out=pathlib.Path('/state/retention-integration-result.json')
result={'chart':'1.1.24','tests':[],'task_ids':[]}
def save():out.write_text(json.dumps(result,indent=2))
def audio_files():
    return [p for d in pathlib.Path('/request-data').glob('req-*') for p in d.iterdir() if p.is_file() and not p.name.startswith('.')]
def check_empty(label):
    assert not audio_files(), [(p.name,p.stat().st_size) for p in audio_files()]
    result['tests'].append({'test':label,'remaining_source_files':0});save()
def submit(path,filename,endpoint='/service/transcribe'):
    with open(path,'rb') as f:
        r=requests.post('http://localhost:8000'+endpoint,params={'model':'large-v3','device':'cuda','language':'en','min_speakers':1,'max_speakers':1},files={'file':(filename,f,'application/octet-stream')},timeout=120)
    r.raise_for_status();identifier=r.json()['identifier']
    result['task_ids'].append(identifier);save()
    return identifier
def wait(identifier):
    for _ in range(200):
        r=requests.get('http://localhost:8000/task/'+identifier,timeout=10);r.raise_for_status();task=r.json()
        if task['status'] in ['completed','failed']:break
        time.sleep(3)
    assert task['status']=='completed',task
    assert 'ask not what your country' in json.dumps(task['result']).lower(),task
    return task
try:
    subprocess.run(['ffmpeg','-y','-i','/cache/hf/hub/assets/whisper108-test-jfk.flac','/tmp/retention-test.wav'],check=True,capture_output=True)
    task=wait(submit('/tmp/retention-test.wav','normal.wav'));check_empty('normal transcription')
    r=requests.post('http://localhost:8000/service/transcribe',files={'file':('broken.wav',io.BytesIO(b'not an audio file'),'audio/wav')},timeout=30)
    assert 400<=r.status_code<500,r.text
    check_empty('corrupt audio rejected without residue')
    subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=black:s=16x16:r=1','-i','/tmp/retention-test.wav','-shortest','-c:v','libx264','-c:a','aac','/tmp/retention-test.mp4'],check=True,capture_output=True)
    wait(submit('/tmp/retention-test.mp4','video.mp4'));check_empty('video and converted WAV cleaned')
    with ThreadPoolExecutor(max_workers=3) as executor:
        ids=list(executor.map(lambda i:submit('/tmp/retention-test.wav','concurrent-'+str(i)+'.wav'),range(3)))
    # All inputs have already been decoded even if their GPU tasks are queued.
    check_empty('queued concurrent inputs removed after decoding')
    for identifier in ids:wait(identifier)
    check_empty('three concurrent tasks completed without residue')
    segments=wait(submit('/tmp/retention-test.wav','complete.wav','/speech-to-text'))['result']['segments']
    words=[w for s in segments for w in s['words']]
    assert words and all('start' in w and 'end' in w and 'speaker' in w for w in words)
    check_empty('full transcription alignment diarization')
    result['aligned_words']=len(words)
    # This public synchronous endpoint has a separate upstream handler.
    with open('/tmp/retention-test.wav','rb') as f:
        r=requests.post('http://localhost:8000/v1/audio/transcriptions',files={'file':('openai.wav',f,'audio/wav')},data={'model':'large-v3','language':'en'},timeout=180)
    r.raise_for_status();assert 'ask not what your country' in r.text.lower(),r.text
    check_empty('OpenAI synchronous endpoint')
    seed=json.loads(pathlib.Path('/legacy-data/.upgrade-backups/seed-result.json').read_text())
    restored=requests.get('http://localhost:8000/task/'+seed['identifier'],timeout=10).json()
    assert restored['result']==seed['task']['result']
    result['seed_task_restored']=True
    legacy=pathlib.Path('/legacy-data');before=json.loads((legacy/'.upgrade-backups/legacy-inventory.json').read_text())
    assert all(hashlib.sha256((legacy/name).read_bytes()).hexdigest()==v['sha256'] for name,v in before.items())
    result['legacy_files_unchanged']=len(before)
    assert requests.get('http://localhost:8000/storage/audio',timeout=10).status_code==403
    assert requests.post('http://localhost:8000/storage/audio/cleanup',json={'dry_run':False},timeout=10).status_code==403
    result['tests'].append({'test':'storage administration disabled without token','passed':True})
    result['passed']=True
except Exception:
    result['passed']=False;result['error']=traceback.format_exc()
save();print(json.dumps(result,indent=2),flush=True)
