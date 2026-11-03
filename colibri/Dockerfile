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
index 0a3824e..0900c4b 100644
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
