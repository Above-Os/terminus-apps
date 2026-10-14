import asyncio, contextlib, importlib.util, io, json, os, pathlib, secrets
import tempfile, threading, time, unittest
import sys
sys.path.insert(0, '/app')
import fcntl
run_lock=open('/state/retention-safety-single.lock','w')
try:fcntl.flock(run_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('retention','/opt/olares-runtime/retention.py')
retention=importlib.util.module_from_spec(spec);spec.loader.exec_module(retention)
workspace=tempfile.TemporaryDirectory(prefix='retention-safety-')
os.environ['AUDIO_REQUEST_DIR']=workspace.name+'/api'
os.environ['AUDIO_CLEANUP_TOKEN']=secrets.token_hex(32)
retention.install()
from app.main import app
from app.services.file_service import FileService
from app.services import file_service
from fastapi import FastAPI, UploadFile

async def call_asgi(application,path,method='GET',body=None,token=None):
    payload=json.dumps(body).encode() if body is not None else b''
    headers=[(b'content-type',b'application/json'),(b'content-length',str(len(payload)).encode())]
    if token is not None:headers.append((b'authorization',('Bearer '+token).encode()))
    scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','root_path':'','headers':headers,'client':('127.0.0.1',1234),'server':('localhost',8000)}
    messages=[];sent=False
    async def receive():
        nonlocal sent
        if not sent:
            sent=True;return {'type':'http.request','body':payload,'more_body':False}
        await asyncio.sleep(60)
        return {'type':'http.disconnect'}
    async def send(message):messages.append(message)
    try:await application(scope,receive,send)
    except Exception:pass
    status=next(m['status'] for m in messages if m['type']=='http.response.start')
    data=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
    try:parsed=json.loads(data or b'{}')
    except ValueError:parsed={'text':data.decode(errors='replace')}
    return status,parsed

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=workspace.name)
        self.manager=retention.ManagedFiles(self.tmp.name+'/requests')
        self.outside=pathlib.Path(self.tmp.name)/'user-original.wav';self.outside.write_bytes(b'KEEP USER FILE')
    def tearDown(self):self.tmp.cleanup()
    def old(self,directory):
        p=directory/'.managed.json';j=json.loads(p.read_text());j['created']=j['finished']=time.time()-72*3600;p.write_text(json.dumps(j))
    def test_no_delete_of_user_original(self):
        directory,lock=self.manager.begin();token=retention.current_directory.set(directory)
        try:
            (directory/'upload.wav').write_bytes(b'audio')
            self.assertFalse(self.manager.is_owned(self.outside))
            self.manager.release_loaded_files()
            self.assertEqual(self.manager.inventory()['files'],0)
        finally:self.manager.finish(directory,lock);retention.current_directory.reset(token)
        self.assertEqual(self.outside.read_bytes(),b'KEEP USER FILE')
    def test_retention_dry_run_active_and_orphan(self):
        self.manager.retain=True
        directory,lock=self.manager.begin();(directory/'upload.wav').write_bytes(b'kept')
        self.manager.finish(directory,lock);self.old(directory)
        active,active_lock=self.manager.begin();(active/'active.wav').write_bytes(b'active');self.old(active)
        orphan,orphan_lock=self.manager.begin();(orphan/'orphan.wav').write_bytes(b'orphan');self.old(orphan);orphan_lock.close()
        self.assertEqual(self.manager.cleanup(True)['directories'],2)
        self.assertTrue(directory.exists())
        self.assertEqual(self.manager.cleanup(False)['directories'],2)
        self.assertTrue(active.exists());self.assertFalse(orphan.exists())
        self.manager.finish(active,active_lock)
    def test_retained_upload_is_readable_by_olares_owner(self):
        self.manager.retain=True
        directory,lock=self.manager.begin();token=retention.current_directory.set(directory)
        try:
            path=pathlib.Path(FileService.save_upload(UploadFile(filename='debug.wav',file=io.BytesIO(b'debug audio'))))
            self.assertEqual(directory.stat().st_uid,1000 if os.geteuid()==0 else os.geteuid())
            self.assertEqual(path.stat().st_uid,1000 if os.geteuid()==0 else os.geteuid())
            self.assertEqual(path.read_bytes(),b'debug audio')
        finally:self.manager.finish(directory,lock);retention.current_directory.reset(token)
    def test_retention_metadata_write_failure_keeps_ownership_marker(self):
        self.manager.retain=True
        directory,lock=self.manager.begin();(directory/'audio.wav').write_bytes(b'keep temporarily')
        original=pathlib.Path.write_text
        def fail_pending(path,*args,**kwargs):
            if path.name=='.managed.pending':raise OSError('simulated full disk')
            return original(path,*args,**kwargs)
        with patch.object(pathlib.Path,'write_text',fail_pending):self.manager.finish(directory,lock)
        self.assertEqual(json.loads((directory/'.managed.json').read_text())['kind'],retention.MARKER)
        self.old(directory);self.assertEqual(self.manager.cleanup(False)['directories'],1)
    def test_symlinks_and_unmarked_directories(self):
        outside=self.outside.parent/'external';outside.mkdir();(outside/'valuable.wav').write_bytes(b'keep')
        (self.manager.root/('req-'+'a'*32)).symlink_to(outside,target_is_directory=True)
        unknown=self.manager.root/('req-'+'b'*32);unknown.mkdir();(unknown/'valuable.wav').write_bytes(b'keep')
        self.manager.cleanup(False)
        self.assertTrue((outside/'valuable.wav').exists());self.assertTrue((unknown/'valuable.wav').exists())
    def test_delete_failure_is_reported_without_claiming_success(self):
        self.manager.retain=True
        directory,lock=self.manager.begin();(directory/'old.wav').write_bytes(b'keep on failure');self.manager.finish(directory,lock);self.old(directory)
        with patch.object(retention.shutil,'rmtree',side_effect=OSError('simulated permission denial')):
            result=self.manager.cleanup(False)
        self.assertEqual(result['files'],0);self.assertEqual(result['errors'],1)
        self.assertTrue((directory/'old.wav').exists())
    def test_concurrent_requests_have_isolated_ownership(self):
        barrier=threading.Barrier(8)
        def request(i):
            directory,lock=self.manager.begin();token=retention.current_directory.set(directory)
            try:
                path=directory/'audio.wav';path.write_bytes(bytes([i])*10);barrier.wait()
                self.assertTrue(self.manager.is_owned(path));self.manager.release_loaded_files()
            finally:self.manager.finish(directory,lock);retention.current_directory.reset(token)
        with ThreadPoolExecutor(max_workers=8) as executor:list(executor.map(request,range(8)))
        self.assertEqual(list(self.manager.root.iterdir()),[])
    def test_partial_upload_is_removed(self):
        manager=self.manager
        fixture=FastAPI();fixture.add_middleware(retention.RequestFilesMiddleware,manager=manager)
        class BrokenFile:
            def read(self):raise OSError('upload interrupted')
        @fixture.post('/service/transcribe')
        def upload():FileService.save_upload(UploadFile(filename='broken.wav',file=BrokenFile()))
        status,_=asyncio.run(call_asgi(fixture,'/service/transcribe','POST',{}))
        self.assertEqual(status,500);self.assertEqual(list(manager.root.iterdir()),[])
    def test_interrupted_url_download_is_removed(self):
        fixture=FastAPI();fixture.add_middleware(retention.RequestFilesMiddleware,manager=self.manager)
        class Response:
            headers={};url='https://example.org/sample.wav';is_redirect=False
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def raise_for_status(self):pass
            def iter_content(self,**kwargs):
                yield b'partial audio'
                raise file_service.requests.ConnectionError('download interrupted')
        class Session:
            hooks={'response':[]}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def get(self,*args,**kwargs):return Response()
        @fixture.post('/speech-to-text-url')
        def download():FileService.download_from_url('https://example.org/sample.wav')
        with patch.object(file_service,'validate_url',return_value=('https://example.org/sample.wav',None)),patch.object(file_service.requests,'Session',Session):
            status,_=asyncio.run(call_asgi(fixture,'/speech-to-text-url','POST',{}))
        self.assertEqual(status,500);self.assertEqual(list(self.manager.root.iterdir()),[])
    def test_administration_auth_preview_and_execution(self):
        token=os.environ['AUDIO_CLEANUP_TOKEN'];manager=app.state.audio_storage
        directory,lock=manager.begin();(directory/'old.wav').write_bytes(b'old');manager.retain=True;manager.finish(directory,lock);self.old(directory)
        self.assertEqual(asyncio.run(call_asgi(app,'/storage/audio'))[0],403)
        self.assertEqual(asyncio.run(call_asgi(app,'/storage/audio',token='wrong'))[0],403)
        self.assertEqual(asyncio.run(call_asgi(app,'/storage/audio',token='错误令牌'))[0],403)
        status,body=asyncio.run(call_asgi(app,'/storage/audio',token=token));self.assertEqual(status,200);self.assertGreaterEqual(body['managed']['files'],1)
        status,body=asyncio.run(call_asgi(app,'/storage/audio/cleanup','POST',{},token));self.assertEqual(status,200);self.assertTrue(body['dry_run']);self.assertTrue(directory.exists())
        self.assertEqual(asyncio.run(call_asgi(app,'/storage/audio/cleanup','POST',{'older_than_hours':0},token))[0],422)
        status,body=asyncio.run(call_asgi(app,'/storage/audio/cleanup','POST',{'dry_run':False},token));self.assertEqual(status,200);self.assertFalse(directory.exists())

suite=unittest.defaultTestLoader.loadTestsFromTestCase(SafetyTests)
run=unittest.TextTestRunner(verbosity=2).run(suite)
result={'tests':run.testsRun,'passed':run.wasSuccessful(),'failures':len(run.failures),'errors':len(run.errors)}
pathlib.Path('/state/retention-safety-result.json').write_text(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
