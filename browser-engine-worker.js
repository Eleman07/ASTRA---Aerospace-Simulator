/* Runs the original ASTRA Python simulation algorithms on-device.
   Dedicated Worker: no blocking of WebGL/main-thread UI.
   Pyodide runtime is pinned; no remote ASTRA simulation server is used. */
'use strict';
const BASE = new URL('./', self.location.href);
// Ship the Pyodide runtime with the Pages artifact. Remote CDN fallback
// caused network failures despite offline files already being deployed.
let pyodide;
let bootError;
let loaded;
async function initialize(){
  try {
    const local = new URL('vendor/pyodide/pyodide.js', BASE);
    const indexURL = new URL('vendor/pyodide/', BASE).href;
    const probe = await fetch(local.href, {method:'GET', cache:'no-store'});
    if (!probe.ok) throw new Error(`Pyodide locale assente (HTTP ${probe.status}): ${local.href}. Rifai il deploy da GitHub Actions.`);
    const contentType = probe.headers.get('content-type') || '';
    if (contentType.includes('text/html')) throw new Error(`GitHub Pages restituisce HTML invece di Pyodide: ${local.href}. Controlla i file vendor nel deploy.`);
    try {
      importScripts(local.href);
    } catch (scriptError) {
      throw new Error(`Caricamento Pyodide locale fallito: ${scriptError.message || String(scriptError)}. URL: ${local.href}`);
    }
    if (typeof loadPyodide !== 'function') throw new Error(`pyodide.js non ha definito loadPyodide(): ${local.href}`);
    pyodide = await loadPyodide({indexURL, stdout:()=>{}, stderr:(line)=>console.warn('[PY]',line)});
    const listResponse = await fetch(new URL('browser-python-files.json', BASE));
    if (!listResponse.ok) throw new Error('Cannot load Python source manifest');
    const paths = await listResponse.json();
    pyodide.FS.mkdirTree('/home/pyodide/astra');
    // Fetch in parallel, write into the Pyodide virtual filesystem.
    const items = await Promise.all(paths.map(async p=>{
      const response=await fetch(new URL(p,BASE));
      if (!response.ok) throw new Error('Unable to fetch '+p+' (HTTP '+response.status+')');
      return [p,await response.text()];
    }));
    for (const [p,source] of items) pyodide.FS.writeFile('/home/pyodide/'+p,source);
    pyodide.runPython('import sys; sys.path.insert(0,"/home/pyodide"); from browser_bridge import route_raw');
    self.postMessage({kind:'ready', version:'1.3.2', python:pyodide.runPython('import sys; sys.version.split()[0]')});
  }catch(error){
    bootError=error;
    self.postMessage({kind:'boot_error',error:String(error?.stack||error)});
    throw error;
  }
}
loaded=initialize();
self.onmessage=async event=>{
  const {id,path,payload,method}=event.data||{};
  if (!id) return;
  try {
    await loaded;
    const requestJSON=JSON.stringify({path,payload,method:method||(payload?'POST':'GET')});
    pyodide.globals.set('request_json',requestJSON);
    const raw=pyodide.runPython('route_raw(request_json)');
    const answer=JSON.parse(raw);
    self.postMessage({id,...answer});
  } catch (error) {
    self.postMessage({id,ok:false,error:String(error?.message||error||bootError)});
  }
};
