import fcntl,hashlib,io,json,os,pathlib,requests,subprocess,time,traceback
from concurrent.futures import ThreadPoolExecutor
from gradio_client import Client,handle_file
outputs=pathlib.Path('/Whisper-WebUI/outputs')
lock=open(outputs/'release-webui-test.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
result={'chart':'1.1.22','app_version':'1.0.8','tests':[]}
def record(label):result['tests'].append(label);save()
def save():(outputs/'release-webui-result.json').write_text(json.dumps(result,indent=2))
def source_files():
    files=[]
    for d in pathlib.Path('/request-data').glob('req-*'):
        try:files.extend(p for p in d.iterdir() if p.is_file() and not p.name.startswith('.'))
        except FileNotFoundError:pass  # Request cleanup can remove the folder during observation.
    return files
def assert_clean():
    for _ in range(30):
        if not source_files():return
        time.sleep(0.1)
    assert not source_files()
def request(path,fmt='json'):
    with open(path,'rb') as audio:
        r=requests.post('http://localhost:8000/v1/audio/transcriptions',files={'file':(pathlib.Path(path).name,audio,'application/octet-stream')},data={'language':'en','response_format':fmt},timeout=300)
    r.raise_for_status();assert 'ask not what your country' in r.text.lower(),r.text
    return r
try:
    for _ in range(120):
        try:
            if requests.get('http://localhost:8000/healthz',timeout=5).status_code==200:break
        except requests.RequestException:pass
        time.sleep(3)
    assert pathlib.Path('/Whisper-WebUI/VERSION').read_text().strip()=='1.0.8'
    assert os.environ['AUTO_DELETE_SOURCE_AUDIO']=='true' and os.environ['AUTO_CLEANUP_SOURCE_AUDIO']=='true'
    for endpoint in ['http://localhost:7860/','http://localhost:7860/gradio_api/info','http://localhost:8000/v1/models']:
        requests.get(endpoint,timeout=30).raise_for_status()
    record('WebUI, Gradio schema, model API and actual source version')
    sample='/cache/hf/hub/assets/whisper108-test-jfk.flac'
    for fmt in ['json','text','srt','vtt','verbose_json']:
        request(sample,fmt);assert_clean();record('OpenAI '+fmt+' transcription and request cleanup')
    r=requests.post('http://localhost:8000/v1/audio/transcriptions',files={'file':('broken.wav',io.BytesIO(b'not audio'),'audio/wav')},timeout=30)
    assert r.status_code>=400 and r.status_code<600,r.text
    assert_clean();record('corrupt upload rejected and cleaned')
    subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=black:s=16x16:r=1','-i',sample,'-shortest','-c:v','libx264','-c:a','aac','/tmp/webui-test.mp4'],check=True,capture_output=True)
    request('/tmp/webui-test.mp4');assert_clean();record('video transcription and cleanup')
    with ThreadPoolExecutor(max_workers=2) as executor:list(executor.map(lambda _:request(sample),range(2)))
    assert_clean();record('two concurrent OpenAI requests without residual source files')
    # Run the actual Gradio UI callback with its advertised default parameters.
    client=Client('http://localhost:7860/',verbose=False)
    info=client.view_api(return_format='dict')
    endpoint=next((name for name in info['named_endpoints'] if name=='/transcribe_file'),None)
    assert endpoint, list(info['named_endpoints'])
    config=requests.get('http://localhost:7860/config',timeout=20).json()
    components={c['id']:c for c in config['components']}
    dependency=next(d for d in config['dependencies'] if d.get('api_name')=='transcribe_file')
    values=[components[i].get('props',{}).get('value') for i in dependency['inputs']]
    values[0]=[handle_file(sample)];values[1]=''
    value=client.predict(*values,api_name=endpoint)
    assert 'ask not what your country' in json.dumps(value).lower(),value
    assert_clean();record('actual Gradio upload callback and subtitle generation')
    subtitle_paths=value[1] if isinstance(value[1],list) else [value[1]]
    for p in subtitle_paths:
        if isinstance(p,dict):p=p.get('path') or p.get('name')
        assert p and pathlib.Path(p).exists(),p
    result['subtitles_preserved']=True
    folder=pathlib.Path('/tmp/retention-original-folder');folder.mkdir(exist_ok=True)
    original=folder/'original.flac';original.write_bytes(pathlib.Path(sample).read_bytes())
    original_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    values[0]=None;values[1]=str(folder)
    folder_result=client.predict(*values,api_name=endpoint)
    assert 'ask not what your country' in json.dumps(folder_result).lower()
    assert hashlib.sha256(original.read_bytes()).hexdigest()==original_hash
    assert_clean();record('actual selected-folder callback preserves the user original')
    assert requests.get('http://localhost:8000/storage/audio',timeout=10).status_code==403
    assert requests.post('http://localhost:8000/storage/audio/cleanup',json={'dry_run':False},timeout=10).status_code==403
    record('storage administration disabled without token')
    baseline=outputs/'release-baseline.json'
    if baseline.exists():
        before=json.loads(baseline.read_text())
        for p,digest in before['historical_outputs'].items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==digest
        import yaml
        config=yaml.safe_load(pathlib.Path('/Whisper-WebUI/configs/default_parameters.yaml').read_text())
        assert config['retention_test_marker']==before['marker']
        result['historical_outputs_unchanged']=len(before['historical_outputs']);result['configuration_marker_preserved']=True
    result['remaining_source_files']=len(source_files());result['passed']=True
except Exception:result['passed']=False;result['error']=traceback.format_exc()
save();print(json.dumps(result),flush=True)
