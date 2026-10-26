/* Runs the original ASTRA Python simulation algorithms on-device.
   Dedicated Worker: no blocking of WebGL/main-thread UI.
   Pyodide runtime is pinned; no remote ASTRA simulation server is used. */
import { loadPyodide } from './vendor/pyodide/pyodide.mjs';
import createPyodideModule from './vendor/pyodide/pyodide.asm.mjs';

const BASE = new URL('./', self.location.href);
// Ship the Pyodide runtime with the Pages artifact. Remote CDN fallback
// caused network failures despite offline files already being deployed.
let pyodide;
let bootError;
let loaded;
async function initialize(){
  try {
    const indexURL = new URL('vendor/pyodide/', BASE).href;
    // Pyodide 314 requires an ES-module worker (classic importScripts is unsupported).
    // Importing the two modules above fixes startup without any external CDN.
    const requiredFiles = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
    const availability = await Promise.all(requiredFiles.map(async file => {
      const url = new URL('vendor/pyodide/' + file, BASE);
      const response = await fetch(url, {method:'HEAD',cache:'no-store'});
      if (!response.ok) throw new Error(`Pyodide file missing: ${file} (HTTP ${response.status}). Re-run GitHub Pages workflow.`);
      return file;
    }));
    pyodide = await loadPyodide({
      indexURL,
      createPyodideModule,
      stdout:()=>{},
      stderr:(line)=>console.warn('[PY]',line)
    });
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
    self.postMessage({kind:'ready', version:'1.4.1', python:pyodide.runPython('import sys; sys.version.split()[0]')});
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
