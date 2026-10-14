import asyncio,fcntl,hashlib,importlib.util,json,os,pathlib,secrets,sys,tempfile,threading,time,unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,'/Whisper-WebUI');sys.path.insert(0,'/opt/olares-runtime')
import webui_retention as retention
from fastapi import FastAPI
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline as Pipeline

test_root=tempfile.TemporaryDirectory(prefix='webui-retention-tests-')
os.environ.update(AUDIO_REQUEST_DIR=test_root.name+'/managed',GRADIO_TEMP_DIR=test_root.name+'/gradio',AUTO_DELETE_SOURCE_AUDIO='true',AUTO_CLEANUP_SOURCE_AUDIO='false',AUDIO_CLEANUP_TOKEN=secrets.token_hex(32))
cache=pathlib.Path(os.environ['GRADIO_TEMP_DIR']);cache.mkdir()
decoded=[]
def fake_run(self,audio,*args,**kwargs):
    decoded.append(str(audio))
    if kwargs.get('fail'):raise ValueError('simulated decode failure')
    if kwargs.get('barrier'):kwargs['barrier'].wait()
    return pathlib.Path(audio).read_bytes()
Pipeline.run=fake_run
app=FastAPI();manager=retention.install(app)

async def call(path,method='GET',payload=None,token=None):
    body=json.dumps(payload or {}).encode();messages=[];sent=False
    headers=[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())]
    if token:headers.append((b'authorization',('Bearer '+token).encode()))
    scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','root_path':'','headers':headers,'client':('127.0.0.1',1),'server':('localhost',8000)}
    async def receive():
        nonlocal sent
        if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
        await asyncio.sleep(30)
    async def send(message):messages.append(message)
    await app(scope,receive,send)
    status=next(x['status'] for x in messages if x['type']=='http.response.start')
    data=b''.join(x.get('body',b'') for x in messages if x['type']=='http.response.body')
    return status,json.loads(data or b'{}')

class Tests(unittest.TestCase):
    def setUp(self):
        manager.retain=False
        self.original=pathlib.Path(test_root.name)/'original.wav';self.original.write_bytes(b'original audio')
        self.subtitle=pathlib.Path(test_root.name)/'output.srt';self.subtitle.write_text('preserve subtitles')
    def tearDown(self):
        # All paths belong to this isolated TemporaryDirectory fixture.
        for d in manager.root.iterdir():
            if d.is_symlink():d.unlink()
            else:retention.shutil.rmtree(d)
    def aged(self,directory):
        marker=directory/'.managed.json';r=json.loads(marker.read_text());r.update(created=time.time()-72*3600,finished=time.time()-72*3600);marker.write_text(json.dumps(r))
    def test_folder_original_and_subtitle_preserved(self):
        self.assertEqual(Pipeline.run(object(),str(self.original)),b'original audio')
        self.assertNotEqual(decoded[-1],str(self.original));self.assertTrue(self.original.exists());self.assertTrue(self.subtitle.exists());self.assertEqual(manager.inventory()['files'],0)
    def test_gradio_cache_copy_removed_after_success(self):
        source=cache/'upload.wav';source.write_bytes(b'cached audio')
        self.assertEqual(Pipeline.run(object(),str(source)),b'cached audio');self.assertFalse(source.exists());self.assertEqual(manager.inventory()['files'],0)
    def test_failed_decode_cleans_request_and_cache(self):
        source=cache/'broken.wav';source.write_bytes(b'broken')
        with self.assertRaises(ValueError):Pipeline.run(object(),str(source),fail=True)
        self.assertFalse(source.exists());self.assertEqual(manager.inventory()['files'],0)
    def test_retention_keeps_gradio_and_owned_copies(self):
        manager.retain=True;source=cache/'retain.wav';source.write_bytes(b'retain')
        Pipeline.run(object(),str(source));self.assertTrue(source.exists());self.assertTrue(pathlib.Path(decoded[-1]).exists())
        d=pathlib.Path(decoded[-1]).parent;self.aged(d);manager.cleanup(False);self.assertFalse(d.exists());self.assertFalse(source.exists())
    def test_same_input_concurrent_callbacks_protected(self):
        source=cache/'shared.wav';source.write_bytes(b'concurrent');barrier=threading.Barrier(3)
        with ThreadPoolExecutor(max_workers=3) as executor:
            values=list(executor.map(lambda _:Pipeline.run(object(),str(source),barrier=barrier),range(3)))
        self.assertEqual(values,[b'concurrent']*3);self.assertFalse(source.exists());self.assertEqual(manager.inventory()['files'],0)
    def test_active_orphan_unknown_and_symlink(self):
        manager.retain=True;active,lock=manager.begin();(active/'active.wav').write_bytes(b'active');self.aged(active)
        orphan,other=manager.begin();(orphan/'orphan.wav').write_bytes(b'orphan');self.aged(orphan);other.close()
        unknown=manager.root/('req-'+'b'*32);unknown.mkdir(exist_ok=True);(unknown/'keep.wav').write_bytes(b'unknown')
        link=manager.root/('req-'+'a'*32);link.symlink_to(self.original.parent,target_is_directory=True)
        result=manager.cleanup(False);self.assertEqual(result['files'],1);self.assertTrue(active.exists());self.assertTrue(unknown.exists());self.assertTrue(self.original.exists());manager.finish(active,lock)
    def test_cleanup_failure_reports_error(self):
        manager.retain=True;d,lock=manager.begin();(d/'audio.wav').write_bytes(b'keep');manager.finish(d,lock);self.aged(d)
        with patch.object(retention.shutil,'rmtree',side_effect=OSError('simulated permission failure')):
            result=manager.cleanup(False)
        self.assertEqual(result['files'],0);self.assertGreaterEqual(result['errors'],1);self.assertTrue(d.exists())
        manager.cleanup(False)
    def test_token_preview_actual_and_invalid_age(self):
        manager.retain=True;d,lock=manager.begin();(d/'audio.wav').write_bytes(b'audio');manager.finish(d,lock);self.aged(d)
        token=os.environ['AUDIO_CLEANUP_TOKEN']
        self.assertEqual(asyncio.run(call('/storage/audio'))[0],403)
        self.assertEqual(asyncio.run(call('/storage/audio',token='错误'))[0],403)
        status,data=asyncio.run(call('/storage/audio/cleanup','POST',{},token));self.assertEqual(status,200);self.assertTrue(data['dry_run']);self.assertTrue(d.exists())
        self.assertEqual(asyncio.run(call('/storage/audio/cleanup','POST',{'older_than_hours':0},token))[0],422)
        status,data=asyncio.run(call('/storage/audio/cleanup','POST',{'dry_run':False},token));self.assertEqual(status,200);self.assertFalse(d.exists())

suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);run=unittest.TextTestRunner(verbosity=2).run(suite)
result={'tests':run.testsRun,'passed':run.wasSuccessful(),'errors':len(run.errors),'failures':len(run.failures)}
pathlib.Path('/Whisper-WebUI/outputs/webui-retention-safety-result.json').write_text(json.dumps(result));print(json.dumps(result),flush=True)
