/* Runs the original ASTRA Python simulation algorithms on-device.
   Dedicated Worker: no blocking of WebGL/main-thread UI.
   Pyodide runtime is pinned; no remote ASTRA simulation server is used. */
'use strict';
const BASE = new URL('./', self.location.href);
const PYODIDE_VERSION = '314.0.7';
const CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
let pyodide;
let bootError;
let loaded;
async function initialize(){
  try {
    const local = new URL('vendor/pyodide/pyodide.js', BASE);
    let indexURL = new URL('vendor/pyodide/', BASE).href;
    try {
      const probe = await fetch(local.href, {method:'HEAD'});
      if (!probe.ok) throw new Error('not self hosted');
      importScripts(local.href);
    } catch (err) {
      indexURL = CDN;
      importScripts(CDN+'pyodide.js');
    }
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
    self.postMessage({kind:'ready', version:'1.3.1', python:pyodide.runPython('import sys; sys.version.split()[0]')});
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
