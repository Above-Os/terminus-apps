# syntax=docker/dockerfile:1.7
# Colibri 2.1.0, Apache-2.0. Source and patch pinned to the tested image.
# Build from this directory: docker build -f Dockerfile .
FROM node:24.11.0-bookworm-slim AS source
ARG COLIBRI_COMMIT=0a5504a1dc64f86fcd0fe7db298b0448c730e7e6
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none --no-checkout https://github.com/JustVugg/colibri.git /src && git -C /src checkout "$COLIBRI_COMMIT"
WORKDIR /src
RUN <<'APPLY_OLARES_PATCH'
git apply - <<'COLIBRI_PATCH'
diff --git a/web/src/App.tsx b/web/src/App.tsx
index 0a3824e..0cf642e 100644
--- a/web/src/App.tsx
+++ b/web/src/App.tsx
@@ -32,7 +32,7 @@ import { Button } from "@/components/ui/button"
 import { Input } from "@/components/ui/input"
 import { Textarea } from "@/components/ui/textarea"
 import {
-  generateImage, generatesImages, getHealth, listModelInfo, streamChat,
+  configureRouterEndpoint, generateImage, generatesImages, getHealth, listModelInfo, streamChat,
   type ChatMessage, type GeneratedImage, type HealthResponse, type StreamChatResult,
 } from "@/lib/api"
 import {
@@ -61,15 +61,31 @@ const message = (role: ChatMessage["role"], content: string, images?: string[]):
 
 export default function App() {
   const { t, locale, setLocale, locales } = useLocale()
+  const olaresAuth = import.meta.env.VITE_OLARES_AUTH === "1"
 
   const servedByEngine = typeof window !== "undefined" && window.location.port !== "5173" && window.location.protocol.startsWith("http")
   const defaultBase = servedByEngine ? `${window.location.origin}/v1` : "http://127.0.0.1:8000/v1"
+  const [routerBase, setRouterBase] = useState("")
+  useEffect(() => {
+    if (!olaresAuth) return
+    const controller = new AbortController()
+    fetch('/olares-config.json', {signal: controller.signal})
+      .then(response => response.ok ? response.json() : Promise.reject())
+      .then((config: {routerBaseUrl?: string}) => {
+        if (!config.routerBaseUrl) return
+        configureRouterEndpoint(config.routerBaseUrl, `${window.location.origin}/router/v1`)
+        setRouterBase(config.routerBaseUrl)
+      }).catch(() => {})
+    return () => controller.abort()
+  }, [olaresAuth])
   const [baseUrl, setBaseUrl] = useState(() => {
+    if (olaresAuth) return defaultBase
     const saved = stored(localStorage, "colibri.baseUrl", defaultBase)
     if (servedByEngine && saved === "http://127.0.0.1:8000/v1" && defaultBase !== saved) return defaultBase
     return saved
   })
   const [apiKey, setApiKey] = useState("")
+  const usingRouter = !!routerBase && baseUrl === routerBase
   const [models, setModels] = useState<string[]>([])
   /* Models the server marks with the image_generation capability. With one of
      them selected the conversation generates pictures instead of text. */
@@ -230,7 +246,9 @@ export default function App() {
     setConnecting(true)
     setError("")
     try {
-      const info = await listModelInfo(baseUrl, apiKey, controller.signal)
+      const available = await listModelInfo(baseUrl, apiKey, controller.signal)
+      const info = usingRouter && !available.some(item => item.id === 'default-chat')
+        ? [{id: 'default-chat', capabilities: ['chat']}, ...available] : available
       const found = info.map((item) => item.id)
       setModels(found)
       setImageModels(info.filter(generatesImages).map((item) => item.id))
@@ -496,8 +514,14 @@ export default function App() {
   const empty = messages.length === 0
   const connectionControls = (<fieldset disabled={loading}><section className="side-section">
           <div className="section-title"><Link2 className="size-3.5" /> {t("sidebar.connection")}</div>
-          <label>{t("sidebar.endpoint")}<Input id="endpoint" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label>
-          <label>{t("sidebar.apiKey")}<div className="relative"><KeyRound className="field-icon" /><Input id="api-key" className="pl-9" type="password" value={apiKey} placeholder={t("sidebar.apiKeyPlaceholder")} onChange={(event) => setApiKey(event.target.value)} /></div><span className="field-help">{t("sidebar.apiKeyHelp")}</span></label>
+          {olaresAuth && <label>{locale.startsWith("zh") ? "连接服务" : "Connection service"}<select aria-label="Connection service" value={usingRouter ? "router" : "local"} onChange={event => {
+            setApiKey("")
+            setBaseUrl(event.target.value === "router" ? routerBase : defaultBase)
+            autoConnected.current = false
+          }}><option value="local">Colibri {locale.startsWith("zh") ? "本地推理（默认）" : "local engine (default)"}</option><option value="router" disabled={!routerBase}>Olares Router</option></select></label>}
+          <label>{t("sidebar.endpoint")}<Input id="endpoint" value={baseUrl} readOnly={olaresAuth} onChange={(event) => setBaseUrl(event.target.value)} /></label>
+          {olaresAuth ? <p className="field-help">{locale.startsWith("zh") ? "已使用 Olares 登录认证，无需填写 API key。" : "Authenticated by Olares. No API key required."}</p> : <label>{t("sidebar.apiKey")}<div className="relative"><KeyRound className="field-icon" /><Input id="api-key" className="pl-9" type="password" value={apiKey} placeholder={t("sidebar.apiKeyPlaceholder")} onChange={(event) => setApiKey(event.target.value)} /></div><span className="field-help">{t("sidebar.apiKeyHelp")}</span></label>}
+          {usingRouter && <p className="field-help">{locale.startsWith("zh") ? "Router 模式的回复不计入 Colibri 本地引擎统计。切换服务后建议新建对话。" : "Router replies do not appear in local Colibri engine statistics. Start a new chat after switching services."}</p>}
           <Button type="button" variant="secondary" onClick={connect} disabled={connecting}>
             {connecting ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
             {t("sidebar.probe")}
@@ -582,6 +606,7 @@ export default function App() {
       <button className="rail-button" aria-label={t("ui.search")} title={t("ui.search")} onClick={() => { setQuery(""); setHistoryOpen(true) }}><Search /></button>
       <button className="rail-button" aria-label={t("ui.history")} title={t("ui.history")} onClick={() => { setQuery(""); setHistoryOpen(true) }}><History /></button>
       <div className="rail-bottom">
+        <button className="rail-button" aria-label={locale.startsWith("zh") ? "本地 GGUF 模型" : "Local GGUF models"} title={locale.startsWith("zh") ? "在新标签页管理本地模型" : "Manage local models in a new tab"} onClick={() => window.open("/olares-models/", "_blank", "noopener,noreferrer")}><Database /></button>
         <button className={cn("rail-button", view === "settings" && "active")} aria-label={t("ui.settings")} title={t("ui.settings")} onClick={() => openSettings()}><Settings2 /></button>
         <button className="rail-button" aria-label={t("ui.theme")} title={t("ui.theme")} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun /> : <Moon />}</button>
       </div>
diff --git a/web/src/lib/api.ts b/web/src/lib/api.ts
index 047e64a..3859cea 100644
--- a/web/src/lib/api.ts
+++ b/web/src/lib/api.ts
@@ -119,8 +119,18 @@ export interface StreamChatResult {
   compaction: Compaction | null
 }
 
+let routerPublicRoot = ""
+let routerProxyRoot = ""
+export function configureRouterEndpoint(publicBase: string, proxyBase: string) {
+  routerPublicRoot = publicBase.replace(/\/v1\/?$/, "").replace(/\/+$/, "")
+  routerProxyRoot = proxyBase.replace(/\/v1\/?$/, "").replace(/\/+$/, "")
+}
+
 export function endpoint(baseUrl: string, path: string) {
-  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`
+  const base = baseUrl.replace(/\/+$/, "")
+  const mapped = routerPublicRoot && (base === routerPublicRoot || base.startsWith(routerPublicRoot + "/"))
+    ? routerProxyRoot + base.slice(routerPublicRoot.length) : base
+  return `${mapped}/${path.replace(/^\/+/, "")}`
 }
 
 export function serverEndpoint(baseUrl: string, path: string) {
COLIBRI_PATCH
APPLY_OLARES_PATCH

FROM source AS dashboard
WORKDIR /src/web
RUN npm ci
ENV VITE_OLARES_AUTH=1
RUN npm run build

FROM ubuntu:24.04 AS engine
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3 ca-certificates curl && \
    curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb -o /tmp/cuda-keyring.deb && \
    dpkg -i /tmp/cuda-keyring.deb && apt-get update && \
    apt-get install -y --no-install-recommends cuda-nvcc-13-0 cuda-cudart-dev-13-0 libcublas-dev-13-0 && \
    rm -rf /var/lib/apt/lists/* /tmp/cuda-keyring.deb
ENV CUDA_HOME=/usr/local/cuda-13.0
RUN apt-get update && apt-get install -y --no-install-recommends cuda-profiler-api-13-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY --from=source /src/c/ ./c/
# Explicit Blackwell architecture for the verified RTX 5090 target.
RUN make -C c -j2 install CUDA=1 CUDA_HOME=/usr/local/cuda-13.0 CUDA_ARCH=sm_120 ARCH=x86-64-v3 PREFIX=/usr/local DESTDIR=/stage

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 libgomp1 ca-certificates nginx-light && rm -rf /var/lib/apt/lists/* && if ! getent group 1000 >/dev/null; then groupadd -g 1000 colibri; fi && if ! getent passwd 1000 >/dev/null; then useradd -u 1000 -g 1000 -m colibri; fi
# Ship the CUDA libraries used by the engines, rather than unrelated runtime
# libraries such as cuFFT/cuSPARSE. The GPU driver is supplied by Olares.
COPY --from=engine /usr/local/cuda-13.0/lib64/libcudart.so.13.* /usr/local/lib/
COPY --from=engine /usr/local/cuda-13.0/lib64/libcublas.so.13.* /usr/local/lib/
COPY --from=engine /usr/local/cuda-13.0/lib64/libcublasLt.so.13.* /usr/local/lib/
RUN for library in libcudart libcublas libcublasLt; do set -- /usr/local/lib/${library}.so.13.*; test -f "$1"; ln -s "$(basename "$1")" "/usr/local/lib/${library}.so.13"; ln -s "${library}.so.13" "/usr/local/lib/${library}.so"; done
COPY --from=engine /stage/usr/local/ /usr/local/
COPY --from=dashboard /src/web/dist /usr/local/libexec/colibri/web/dist
RUN ln -s ../libexec/colibri/web /usr/local/bin/web
COPY --from=source /src/LICENSE /src/NOTICE /src/THIRD_PARTY_NOTICES.md /usr/share/doc/colibri/
ENV HOME=/data/home PYTHONUNBUFFERED=1 LD_LIBRARY_PATH=/usr/local/lib NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /data
USER 1000:1000
EXPOSE 8000
ENTRYPOINT ["python3", "/usr/local/bin/coli"]
CMD ["--help"]

# Olares model catalogue and persistent engine selection.
COPY <<'OLARES_MODEL_MANAGER' /usr/local/libexec/colibri/olares_models.py
#!/usr/bin/env python3
"""Olares GGUF catalogue and single-engine supervisor (stdlib only)."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tools'))
from gguf_import import ARCHES
SUPPORTED = set(ARCHES)
SPLIT = re.compile(r'^(.*)-(\d{5})-of-(\d{5})\.gguf$', re.I)

def metadata(path):
    """Read selected header fields without allocating tokenizer arrays or tensor data."""
    scalars = {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
    with open(path, 'rb') as f:
        size = os.fstat(f.fileno()).st_size
        def read(n):
            if n < 0 or n > 4096 or f.tell()+n > min(size,256*1024*1024):
                raise ValueError('Invalid or oversized GGUF header')
            b=f.read(n)
            if len(b)!=n: raise ValueError('Truncated GGUF header')
            return b
        def number(fmt): return struct.unpack('<'+fmt, read(struct.calcsize(fmt)))[0]
        def skip(n):
            if n < 0 or f.tell()+n > min(size,256*1024*1024):
                raise ValueError('Invalid or oversized GGUF metadata')
            f.seek(n,1)
        def string(want=False):
            n=number('Q')
            if want: return read(n).decode('utf-8')
            skip(n)
        def value(kind, want=False, depth=0):
            if depth>8: raise ValueError('GGUF metadata nesting too deep')
            if kind==8: return string(want)
            if kind==9:
                element=number('I'); count=number('Q')
                if count>2000000: raise ValueError('GGUF metadata array too large')
                if element in scalars: skip(count*scalars[element])
                else:
                    for _ in range(count): value(element,False,depth+1)
                return None
            if kind not in scalars: raise ValueError('Unknown GGUF metadata type')
            b=read(scalars[kind])
            return int.from_bytes(b,'little') if want else None
        if read(4)!=b'GGUF': raise ValueError('Not a GGUF file')
        if number('I') not in (2,3): raise ValueError('Only GGUF v2/v3 headers are supported')
        number('Q'); count=number('Q')
        if count>20000: raise ValueError('Too many GGUF metadata fields')
        result={}
        wanted={'general.architecture','general.name','general.file_type','split.count','split.no'}
        for _ in range(count):
            key=string(True); kind=number('I'); v=value(kind,key in wanted)
            if key in wanted: result[key]=v
        return result

def confined(path, root):
    path=Path(path); resolved=path.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    if not resolved.is_file(): raise ValueError('GGUF is not a regular file')
    return resolved

def catalogue(root):
    root=Path(root); files=[]; warnings=[]; start=time.monotonic()
    if not root.is_dir(): return [], ['Model directory does not exist']
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:]=sorted(d for d in dirs if not Path(base,d).is_symlink() and d not in {'xet','.git'})
        for name in sorted(names):
            if name.lower().endswith('.gguf'): files.append(Path(base,name))
        if len(files)>2000 or time.monotonic()-start>15:
            warnings.append('Scan limit reached; narrow the model directory or remove obsolete cache entries')
            files=files[:2000];break
    entries=[]; groups=set(); companions=[]
    for path in sorted(files):
        if path.name.lower().startswith(('mmproj','mtp-','dspark-')):
            try:
                actual=confined(path,root)
                meta=metadata(path)
                companions.append({'path':path.relative_to(root).as_posix(),'size':actual.stat().st_size,
                                   'name':meta.get('general.name'),
                                   'fingerprint':hashlib.sha256(json.dumps((str(actual),actual.stat().st_size,actual.stat().st_mtime_ns)).encode()).hexdigest(),
                                   'kind':'vision_projector' if path.name.lower().startswith('mmproj') else 'draft_head'})
            except (OSError,ValueError):pass
            continue
        split=SPLIT.match(path.name); parts=[path]
        if split:
            prefix,part,total=split.group(1),int(split.group(2)),int(split.group(3))
            group=(str(path.parent),prefix,total)
            if group in groups: continue
            groups.add(group)
            if not 1<=total<=1024:
                parts=[path]
            else:
                parts=[path.parent/f'{prefix}-{i:05d}-of-{total:05d}.gguf' for i in range(1,total+1)]
                path=parts[0]
        relative=path.relative_to(root).as_posix()
        entry={'id':hashlib.sha256(relative.encode()).hexdigest()[:32], 'path':relative,
               'name':path.name,'size':0,'architecture':None,'selectable':False,'reason':'','parts':len(parts)}
        try:
            if split and not 1<=int(split.group(3))<=1024: raise ValueError('Invalid split GGUF count')
            fingerprints=[]
            for part in parts:
                actual=confined(part,root);stat=actual.stat();entry['size']+=stat.st_size
                fingerprints.append((str(actual),stat.st_size,stat.st_mtime_ns))
            meta=metadata(path);arch=meta.get('general.architecture')
            entry.update(name=meta.get('general.name') or path.name,architecture=arch,
                         file_type=meta.get('general.file_type'))
            if arch not in SUPPORTED: raise ValueError(f'Unsupported architecture: {arch or "unknown"}')
            if len(parts)!=int(meta.get('split.count',len(parts))): raise ValueError('Incomplete split GGUF set')
            entry['fingerprint']=hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest()[:32]
            entry['selectable']=True
        except (OSError,ValueError,UnicodeError,struct.error) as exc:
            entry['reason']=str(exc)[:400]
        entries.append(entry)
    for entry in entries:
        parent=Path(entry['path']).parent
        names={e['name'] for e in entries if Path(e['path']).parent==parent}
        entry['companions']=[c for c in companions if Path(c['path']).parent==parent and
                             (c['name']==entry['name'] or len(names)==1)]
        if entry.get('fingerprint') and entry['companions']:
            entry['fingerprint']=hashlib.sha256(json.dumps((entry['fingerprint'],[c['fingerprint'] for c in entry['companions']])).encode()).hexdigest()[:32]
    matched={c['path'] for e in entries for c in e['companions']}
    warnings.extend('Auxiliary GGUF is not matched to a unique model: '+c['path'] for c in companions if c['path'] not in matched)
    # A projector on its own is an auxiliary file, not a selectable chat model.
    return entries,warnings

class Manager:
    def __init__(self, root, data, ram='16', context='4096'):
        self.root=Path(root);self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True)
        self.imports=self.data/'imports';self.imports.mkdir(exist_ok=True)
        self.saved=self.data/'selection.json';self.log=self.data/'engine.log'
        self.ram=ram;self.context=context;self.key=os.environ.get('COLI_API_KEY','')
        self.lock=threading.RLock();self.operation=threading.Lock();self.proc=None
        self.active=None;self.phase='empty';self.error='';self.pending=None;self.closing=False;self.modalities=['text']
    def status(self):
        with self.lock:
            if self.phase=='ready' and self.proc is not None and self.proc.poll() is not None:
                self.phase='error';self.error='Engine exited. Select a supported model to retry.';self.active=None
            return {'phase':self.phase,'active':self.active,'pending':self.pending,'error':self.error,
                    'root':'Common/huggingface','cuda':os.environ.get('COLI_CUDA','1'),'input_modalities':self.modalities}
    def persist(self,path):
        temp=self.saved.with_suffix('.tmp');temp.write_text(json.dumps({'path':path}),encoding='utf-8');os.replace(temp,self.saved)
    def engine_health(self):
        request=Request('http://127.0.0.1:8000/health',headers={'Authorization':'Bearer '+self.key})
        with urlopen(request,timeout=2) as r:return json.load(r)
    def drain(self):
        if not self.proc or self.proc.poll() is not None:return
        until=time.monotonic()+120
        while time.monotonic()<until:
            s=self.engine_health().get('scheduler',{})
            if not s.get('active',0) and not s.get('queued',0):return
            time.sleep(.5)
        raise ValueError('Current generation is still active. Wait for it to finish and retry.')
    def stop(self):
        proc=self.proc
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
        # Kill any engine child left in the same process group before replacing it.
        if proc:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        self.proc=None
    def prepare(self,entry):
        final=self.imports/entry['fingerprint']
        if (final/'complete').is_file():return final
        stage=Path(tempfile.mkdtemp(prefix='pending-',dir=self.imports))
        try:
            env=dict(os.environ,COLI_CUDA='0',CUDA_VISIBLE_DEVICES='',NVIDIA_VISIBLE_DEVICES='void')
            with self.log.open('ab') as log:
                result=subprocess.run([sys.executable,str(HERE/'tools/gguf_import.py'),
                       str(self.root/entry['path']),str(stage),'--mode','link'],env=env,
                       stdout=log,stderr=subprocess.STDOUT,timeout=180)
            if result.returncode:raise ValueError('GGUF import failed. Check the model architecture, tensors and quantization.')
            (stage/'complete').write_text('2.1.0')
            os.replace(stage,final);return final
        finally:
            if stage.exists():shutil.rmtree(stage)
    def launch(self,entry,directory):
        env=dict(os.environ,COLI_MODEL=str(directory))
        with self.log.open('ab') as log:
            self.proc=subprocess.Popen([sys.executable,'/usr/local/bin/coli','web','--host','127.0.0.1',
                    '--port','8000','--no-browser','--ctx',str(self.context),'--ram',str(self.ram)],
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        until=time.monotonic()+300
        while time.monotonic()<until:
            if self.closing:raise ValueError('Application is stopping')
            if self.proc.poll() is not None:raise ValueError('Engine failed to load this model. See the log below.')
            try:
                health=self.engine_health()
                if health.get('status')=='ok':
                    self.modalities=health.get('input_modalities',['text']);return
            except (OSError,ValueError):pass
            time.sleep(.5)
        raise ValueError('Engine startup exceeded 300 seconds')
    def change(self,entry):
        old=self.active;old_dir=self.imports/old['fingerprint'] if old else None;stopped=False
        try:
            directory=self.prepare(entry) if entry else None
            self.drain()
            self.stop();stopped=True
            if entry:self.launch(entry,directory)
            self.persist(entry['path'] if entry else None)
            with self.lock:self.active=entry;self.phase='ready' if entry else 'empty';self.error=''
        except Exception as exc:
            message=str(exc)
            if stopped:
                self.stop()
                if old and not self.closing:
                    try:self.launch(old,old_dir)
                    except Exception as restore:
                        self.stop();old=None;message+=' Previous model could not be restored: '+str(restore)
            with self.lock:
                self.active=old;self.phase='ready' if old and self.proc and self.proc.poll() is None else 'error';self.error=message
        finally:
            with self.lock:self.pending=None
            self.operation.release()
    def request(self,entry):
        if not self.operation.acquire(blocking=False):raise ValueError('A model operation is already in progress')
        with self.lock:self.phase='loading';self.pending=entry;self.error=''
        threading.Thread(target=self.change,args=(entry,),daemon=True).start()
    def bootstrap(self):
        try:
            if self.saved.exists():path=json.loads(self.saved.read_text())['path']
            else:path=os.environ.get('MODEL_GGUF','').strip();path=str(Path(path).relative_to(self.root)) if path else None
            if not path:return
            entries,_=catalogue(self.root);entry=next((e for e in entries if e['path']==path and e['selectable']),None)
            if not entry:raise ValueError('Saved or configured GGUF is missing or unsupported. Select another model.')
            self.request(entry)
        except (OSError,ValueError,KeyError) as exc:
            with self.lock:self.phase='error';self.error=str(exc)

def handler_for(manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,value,ctype='application/json; charset=utf-8'):
            b=json.dumps(value,ensure_ascii=False).encode() if isinstance(value,(dict,list)) else value.encode()
            self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            if b:self.wfile.write(b)
        def authorized(self):
            good=bool(manager.key) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+manager.key)
            if not good:self.send(401,{'error':'Authentication required'})
            return good
        def do_GET(self):
            if not self.authorized():return
            path=urlparse(self.path).path
            if path in ('/','/index.html'):self.send(200,PAGE,'text/html; charset=utf-8')
            elif path=='/health':self.send(200,{'status':'ok','manager':manager.status()['phase']})
            elif path=='/guard':self.send(204 if manager.status()['phase']=='ready' else 403,'')
            elif path=='/status':self.send(200,manager.status())
            elif path=='/catalog':
                items,warnings=catalogue(manager.root);self.send(200,{'models':items,'warnings':warnings})
            elif path=='/log':
                try:
                    with manager.log.open('rb') as f:f.seek(max(0,manager.log.stat().st_size-6000));text=f.read().decode('utf-8','replace')
                    self.send(200,{'text':text.replace(manager.key,'[redacted]') if manager.key else text})
                except OSError:self.send(200,{'text':''})
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.authorized():return
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                self.send(403,{'error':'Cross-origin changes are not allowed'});return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                self.send(415,{'error':'JSON body required'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(length));path=urlparse(self.path).path
                if path=='/load':
                    entries,_=catalogue(manager.root)
                    entry=next((e for e in entries if e['id']==body.get('id')),None)
                    if not entry or not entry['selectable']:raise ValueError('Selected GGUF is missing, incomplete or unsupported')
                elif path=='/unload':entry=None
                else:self.send(404,{'error':'Not found'});return
                manager.request(entry);self.send(202,manager.status())
            except (ValueError,TypeError,AttributeError) as exc:self.send(409,{'error':str(exc)})
    return Handler

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Colibri · Local GGUF</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#243146;font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1080px;margin:36px auto;padding:0 24px}header{display:flex;align-items:center;justify-content:space-between;gap:12px}h1{font-size:28px;margin:0}h2{font-size:18px;margin:0 0 10px}.card{background:white;border:1px solid #dce3ed;border-radius:12px;padding:22px;margin:20px 0}button,a.button,select{font:inherit;border:1px solid #c6d2e1;border-radius:7px;background:white;padding:9px 15px;color:#244d82;cursor:pointer;text-decoration:none}button.primary{background:#2a63ad;color:white;border-color:#2a63ad}button:disabled{opacity:.45;cursor:default}small,.muted{color:#617089}code{font:12px/1.5 monospace;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #e4eaf1;padding:13px 9px;vertical-align:top}th{font-size:13px;color:#617089}.actions{display:flex;gap:10px;flex-wrap:wrap}.warning{color:#925d0c}.error{color:#a02f35;white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#15243a;color:#e5eefb;border-radius:8px;padding:16px;font-size:12px}.tag{background:#eaf2fd;border-radius:5px;padding:3px 7px;display:inline-block}#table{overflow:auto}.selected{background:#edf4ff}input[type=radio]{width:18px;height:18px}#notice{min-height:24px}a{color:#255da7}@media(max-width:600px){main{padding:0 14px;margin:20px auto}.card{padding:15px}h1{font-size:23px}}</style>
<main><header><h1 id="title"></h1><select id="language" aria-label="Language"><option value="zh">中文</option><option value="en">English</option></select></header><p id="intro" class="muted"></p>
<section class="card"><h2 id="stateTitle"></h2><div id="status"></div><p id="error" class="error" role="alert"></p><div class="actions"><a class="button" id="chat" href="/"></a><button id="unload"></button></div></section>
<section class="card"><header><h2 id="modelsTitle"></h2><button id="refresh"></button></header><p id="hint" class="muted"></p><div id="table"></div><p id="notice" role="status"></p><div class="actions"><button class="primary" id="load"></button></div></section>
<section class="card" id="confirmation" hidden><p id="confirmText"></p><div class="actions"><button class="primary" id="confirmProceed"></button><button id="confirmCancel"></button></div></section>
<details class="card"><summary id="logTitle"></summary><pre id="log"></pre></details><p id="foot" class="muted"></p></main>
<script>
const dictionaries={zh:{title:'Colibri · 本地模型',intro:'选择 Common/huggingface 中已有的 GGUF。不会自动下载、复制或修改模型权重。',stateTitle:'运行状态',modelsTitle:'发现的 GGUF',hint:'递归扫描模型目录，包含 Hugging Face snapshots。分片模型只显示一项，必须包含全部分片。',refresh:'重新扫描',load:'加载所选模型',unload:'停止本地模型',chat:'进入聊天',logTitle:'加载日志',foot:'加载大型模型可能需要几分钟。停止模型会释放推理进程的显存，但应用的 GPU 分配仍由 Olares 管理。',empty:'未加载模型，请从下方选择。',loading:'正在准备或加载模型，请等待…',ready:'模型已就绪',error:'加载失败，可以重新选择模型。',noFiles:'没有找到 GGUF 文件。将受支持的模型放入 Common/huggingface 后重新扫描。普通 datasets、assets 或 bnb-4bit 目录不会作为 GGUF 模型列出。',choose:'请选择一个可加载的模型。',name:'模型 / 文件位置',architecture:'架构',size:'文件大小',availability:'兼容性',supported:'架构受支持，实际加载仍取决于权重格式和可用资源',unsupported:'无法选择',scan:'正在扫描…',confirm:'切换或停止模型前，请确认当前对话已导出。更换模型后需要重新打开聊天页面。继续吗？',vision:'视觉附件',draft:'辅助草稿权重',visionPending:'配有视觉文件，输入能力以加载后的引擎状态为准',textOnly:'当前引擎仅支持文本，视觉文件未启用',visionReady:'视觉输入已启用',proceed:'确认继续',cancel:'取消',saved:'选择已保存，重启应用后会恢复这个模型。'},en:{title:'Colibri · Local models',intro:'Choose an existing GGUF in Common/huggingface. Weights are not downloaded, copied or modified.',stateTitle:'Engine status',modelsTitle:'Discovered GGUF files',hint:'Scans recursively, including Hugging Face snapshots. Split models appear once and require every shard.',refresh:'Rescan',load:'Load selected model',unload:'Stop local model',chat:'Open chat',logTitle:'Loading log',foot:'Large models can take several minutes. Stopping releases engine VRAM; Olares still manages the application GPU allocation.',empty:'No model loaded. Choose one below.',loading:'Preparing or loading a model. Please wait…',ready:'Model ready',error:'Loading failed. You can select another model.',noFiles:'No GGUF files found. Add a supported model to Common/huggingface and rescan. Ordinary datasets, assets and bnb-4bit directories are not GGUF models.',choose:'Select a loadable model.',name:'Model / file location',architecture:'Architecture',size:'File size',availability:'Compatibility',supported:'Architecture supported; loading still depends on weights and available resources',unsupported:'Not selectable',scan:'Scanning…',confirm:'Export your current conversation before switching or stopping. Reopen chat after changing models. Continue?',vision:'Vision companion',draft:'Draft head',visionPending:'Vision file found; input support depends on the loaded engine',textOnly:'Current engine is text-only; vision file is not enabled',visionReady:'Image input enabled',proceed:'Confirm',cancel:'Cancel',saved:'Selection saved. The same model will be restored after an application restart.'}};
let language=(localStorage.getItem('colibri-locale')||navigator.language).startsWith('zh')?'zh':'en',models=[],selected='',state={phase:'empty'},pending=false,confirming=null,hasScanned=false;
const $=id=>document.getElementById(id),t=k=>dictionaries[language][k];
async function api(path,body){const response=await fetch('/olares-models/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw Error(data.error||response.status);return data;}
function text(id,value){$(id).textContent=value;}
function render(){document.documentElement.lang=language;for(const id of ['title','intro','stateTitle','modelsTitle','hint','refresh','load','unload','chat','logTitle','foot'])text(id,t(id));$('language').value=language;const busy=state.phase==='loading';$('confirmation').hidden=!confirming;text('confirmText',t('confirm')+(confirming?.path==='load'?' · '+(models.find(m=>m.id===confirming.id)?.name||''):''));text('confirmProceed',t('proceed'));text('confirmCancel',t('cancel'));text('status',t(state.phase)+(state.active?' · '+state.active.name:'')+(state.phase==='ready'?' · '+t('saved'):''));text('error',state.error||'');$('load').disabled=busy||pending||!selected;$('unload').disabled=busy||pending||(!state.active&&state.phase!=='error');$('chat').style.display=state.phase==='ready'?'inline-block':'none';const target=$('table');target.replaceChildren();if(!models.length){const p=document.createElement('p');p.textContent=t(hasScanned?'noFiles':'scan');target.append(p);return;}const table=document.createElement('table'),head=document.createElement('tr');for(const k of ['','name','architecture','size','availability']){const th=document.createElement('th');th.textContent=k?t(k):'';head.append(th);}table.append(head);for(const m of models){const tr=document.createElement('tr');if(selected===m.id)tr.className='selected';const td=document.createElement('td'),radio=document.createElement('input');radio.type='radio';radio.name='model';radio.value=m.id;radio.setAttribute('aria-label',m.name);radio.checked=selected===m.id;radio.disabled=!m.selectable||busy||!!confirming;radio.onchange=()=>{selected=m.id;render();};td.append(radio);tr.append(td);const name=document.createElement('td'),label=document.createElement('strong'),path=document.createElement('code');label.textContent=m.name;path.textContent=m.path;name.append(label,document.createElement('br'),path);for(const c of m.companions||[]){const note=document.createElement('small');note.textContent=t(c.kind==='vision_projector'?'vision':'draft')+': '+c.path.split('/').pop()+' · '+(c.size/2**30).toFixed(2)+' GiB';name.append(document.createElement('br'),note);}tr.append(name);for(const value of [m.architecture||'—',(m.size/2**30).toFixed(2)+' GiB',m.selectable?t('supported')+((m.companions||[]).some(c=>c.kind==='vision_projector')?' · '+t(state.active?.id===m.id?((state.input_modalities||[]).includes('image')?'visionReady':'textOnly'):'visionPending'):''):t('unsupported')+': '+m.reason]){const cell=document.createElement('td');cell.textContent=value;tr.append(cell);}table.append(tr);}target.append(table);}
async function scan(){text('notice',t('scan'));$('refresh').disabled=true;try{const data=await api('catalog');models=data.models;hasScanned=true;if(!models.some(m=>m.id===selected&&m.selectable))selected=state.active?.id||'';text('notice',data.warnings.join(' '));render();}catch(e){text('notice',e.message);}finally{$('refresh').disabled=false;}}
async function poll(){try{const fresh=await api('status');if(JSON.stringify(fresh)!==JSON.stringify(state)){state=fresh;render();}text('error',state.error||'');if($('log').parentElement.open)text('log',(await api('log')).text);}catch(e){text('error',e.message);}}
function change(path){if(path==='load'&&!selected){text('notice',t('choose'));return;}confirming={path,id:selected};render();$('confirmation').scrollIntoView({block:'center'});$('confirmProceed').focus();}async function performChange(){const action=confirming;confirming=null;pending=true;render();try{state=await api(action.path,action.path==='load'?{id:action.id}:{});render();}catch(e){text('notice',e.message);}finally{pending=false;await poll();render();}}
$('confirmProceed').onclick=performChange;$('confirmCancel').onclick=()=>{confirming=null;render();};$('refresh').onclick=scan;$('load').onclick=()=>change('load');$('unload').onclick=()=>change('unload');$('language').onchange=e=>{language=e.target.value;render();};$('log').parentElement.ontoggle=poll;render();poll().then(scan);setInterval(poll,1500);
</script></html>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ram',default='16');parser.add_argument('--ctx',default='4096');args=parser.parse_args()
    manager=Manager(os.environ.get('OLARES_MODEL_ROOT','/models'),os.environ.get('OLARES_MODEL_DATA','/data/olares-models'),args.ram,args.ctx)
    server=ThreadingHTTPServer(('127.0.0.1',8002),handler_for(manager));server.daemon_threads=True
    def shutdown(*_):
        manager.closing=True;manager.stop();threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    threading.Thread(target=manager.bootstrap,daemon=True).start()
    try:server.serve_forever()
    finally:manager.closing=True;manager.stop();server.server_close()

if __name__=='__main__':main()

OLARES_MODEL_MANAGER
