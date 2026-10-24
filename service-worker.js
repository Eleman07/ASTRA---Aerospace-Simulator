/* ASTRA Browser PWA 1.3.1. Static only; all physics stays on this device. */
const VERSION='astra-browser-v262';
const SHELL=['./','./index.html','./styles.css','./app.js','./browser-api.js',
  './browser-engine-worker.js','./browser-python-files.json','./browser_bridge.py',
  './i18n.js','./vehicle-glb.js','./disciplines.js','./mission-recorder.js',
  './engineering-studio.js','./flight-frames.js','./pilot-controls.js',
  './manifest.json','./icon.svg','./assets/vehicle-models.json'];
const PYODIDE=['pyodide.js','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json'];
const CORE_VISUALS=['./assets/space-nebula-2k.webp','./assets/space-nebula-4k.webp',
  './assets/earth-natural-1k.webp','./assets/earth-natural-2k.webp',
  './assets/earth-cape-wide-1k.webp','./assets/earth-cape-near-1k.webp',
  './assets/vehicles/sls-block1.glb','./assets/vehicles/x57-maxwell.glb',
  './assets/vehicles/quadrotor-innerscene.glb'];
async function sources(){
  const r=await fetch('./browser-python-files.json',{cache:'no-cache'});
  if(!r.ok)throw new Error('Python manifest HTTP '+r.status);
  return (await r.json()).map(p=>'./'+p);
}
async function putBatch(urls,source){
  const cache=await caches.open(VERSION);
  for(const u of urls){
    const req=new Request(new URL(u, self.registration.scope));
    const prev=await cache.match(req);
    if(prev){source?.postMessage({kind:'offline_progress',file:u,cached:true});continue}
    const response=await fetch(req);
    if(!response.ok)throw Error('Cannot cache '+u+' ('+response.status+')');
    await cache.put(req,response.clone());
    source?.postMessage({kind:'offline_progress',file:u,cached:false});
  }
}
self.addEventListener('install',event=>{
  event.waitUntil(awaitSources().then(py=>putBatch([...SHELL,...py])).then(()=>self.skipWaiting()));
});
// Resolved at event time rather than trying to await in an array literal.
async function awaitSources(){try{return await sources()}catch{return []}}
self.addEventListener('activate',event=>event.waitUntil(
  caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('astra-browser-')&&k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())
));
self.addEventListener('message',event=>{
  if(event.data?.type!=='CACHE_OFFLINE')return;
  const source=event.source;
  event.waitUntil((async()=>{
    try{
      // Offline requires a self-hosted Pyodide core. The public CDN is not enough.
      const probe=await fetch(new URL('./vendor/pyodide/pyodide.js',self.registration.scope),{method:'HEAD'});
      if(!probe.ok)throw Error('Pyodide files not bundled: deploy with GitHub Actions or run tools/prepare_pyodide.py');
      const fileList=[...SHELL,...await sources(),...PYODIDE.map(f=>'./vendor/pyodide/'+f),...CORE_VISUALS];
      await putBatch(fileList,source);
      source?.postMessage({kind:'offline_ready'});
    }catch(error){source?.postMessage({kind:'offline_error',error:String(error.message||error)})}
  })());
});
self.addEventListener('fetch',event=>{
  const r=event.request,url=new URL(r.url);
  if(r.method!=='GET'||url.origin!==self.location.origin)return;
  event.respondWith((async()=>{
    const cache=await caches.open(VERSION);
    const old=await cache.match(r);
    if(old)return old;
    try{
      const response=await fetch(r);
      if(response.ok)await cache.put(r,response.clone());
      return response;
    }catch{return Response.error()}
  })());
});
