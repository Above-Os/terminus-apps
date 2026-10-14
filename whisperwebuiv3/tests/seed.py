import fcntl,hashlib,json,pathlib,requests,time,traceback,yaml
outputs=pathlib.Path('/Whisper-WebUI/outputs')
lock=open(outputs/'release-seed.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
out=outputs/'release-baseline.json'
if out.exists():print(out.read_text());raise SystemExit(0)
result={}
try:
    for _ in range(120):
        try:
            if requests.get('http://localhost:8000/healthz',timeout=5).status_code==200:break
        except requests.RequestException:pass
        time.sleep(3)
    with open('/cache/hf/hub/assets/whisper108-test-jfk.flac','rb') as audio:
        r=requests.post('http://localhost:8000/v1/audio/transcriptions',files={'file':('old-version.flac',audio,'audio/flac')},data={'language':'en'},timeout=300)
    r.raise_for_status();assert 'ask not what your country' in r.text.lower()
    subtitle=outputs/'retention-history.srt';subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nHistorical subtitle - keep\n')
    audio=outputs/'retention-history.wav';audio.write_bytes(pathlib.Path('/cache/hf/hub/assets/whisper108-test-jfk.flac').read_bytes())
    config=pathlib.Path('/Whisper-WebUI/configs/default_parameters.yaml');values=yaml.safe_load(config.read_text());values['retention_test_marker']='webui-release-upgrade-preserve';config.write_text(yaml.safe_dump(values,allow_unicode=True,sort_keys=False))
    result={'passed':True,'marker':values['retention_test_marker'],'historical_outputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [subtitle,audio]},'seed_transcription_match':True}
except Exception:result={'passed':False,'error':traceback.format_exc()}
out.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
