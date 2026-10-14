import fcntl,json,pathlib,requests,time,traceback
from gradio_client import Client,handle_file
root=pathlib.Path('/Whisper-WebUI/outputs')
lock=open(root/'release-mic-test.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
result={}
try:
    for _ in range(90):
        try:
            if requests.get('http://localhost:7860/gradio_api/info',timeout=5).status_code==200:break
        except requests.RequestException:pass
        time.sleep(2)
    config=requests.get('http://localhost:7860/config',timeout=20).json();components={c['id']:c for c in config['components']}
    dependency=next(d for d in config['dependencies'] if d.get('api_name')=='transcribe_mic')
    values=[components[i].get('props',{}).get('value') for i in dependency['inputs']]
    values[0]=handle_file('/cache/hf/hub/assets/whisper108-test-jfk.flac')
    value=Client('http://localhost:7860/',verbose=False).predict(*values,api_name='/transcribe_mic')
    assert 'ask not what your country' in json.dumps(value).lower(),value
    time.sleep(1)
    remaining=[str(p) for p in pathlib.Path('/tmp/gradio').rglob('*') if p.is_file() and p.suffix.lower() in ['.wav','.flac','.mp3','.webm']]
    result={'passed':True,'microphone_callback_transcribed':True,'gradio_source_cache_files_remaining':remaining}
except Exception:result={'passed':False,'error':traceback.format_exc()}
(root/'release-mic-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
