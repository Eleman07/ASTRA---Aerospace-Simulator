/** Request/response shim for ASTRA Browser Edition.
    Exactly one worker per tab => isolated mission state per user/browser tab.
    External astra.client HTTP access is NOT available in this static edition. */
const worker = new Worker(new URL('./browser-engine-worker.js', import.meta.url), {type:'classic'});
const pending = new Map();
let nextId = 0;
let readyResolve, readyReject;
const ready = new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject});
let bootReady=false;
const indicator = document.createElement('div');
indicator.id='browserEngineStatus';
indicator.setAttribute('role','status');
indicator.setAttribute('aria-live','polite');
indicator.textContent='STARTING PYTHON · LOCAL DEVICE';
indicator.style.cssText='position:fixed;z-index:9999;bottom:12px;right:12px;max-width:min(390px,90vw);background:rgba(4,15,28,.96);border:1px solid #2b6071;border-radius:9px;color:#b5e5f5;padding:9px 13px;font:11px ui-monospace,monospace;pointer-events:none;box-shadow:0 8px 32px #0008';
function mount(){if(!document.querySelector('#browserEngineStatus'))document.body.append(indicator)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
worker.onmessage = event => {
  const msg=event.data||{};
  if(msg.kind==='ready'){
    bootReady=true;indicator.textContent=`BROWSER ENGINE · PYTHON ${msg.python} · OFFLINE CAPABLE`;
    readyResolve(true); return;
  }
  if(msg.kind==='boot_error'){
    indicator.textContent='BROWSER ENGINE FAILED: '+String(msg.error).slice(0,170);
    indicator.style.borderColor='#db6f7d';readyReject(new Error(msg.error));return;
  }
  const slot=pending.get(msg.id);
  if(!slot)return;
  pending.delete(msg.id);
  if(msg.ok)slot.resolve(msg.data);else slot.reject(new Error(msg.error||'ASTRA worker error'));
};
worker.onerror = error => {
  const message=error.message||'Worker initialization failure';
  indicator.textContent='BROWSER ENGINE FAILED: '+message;
  if(!bootReady)readyReject(new Error(message));
  for(const {reject} of pending.values())reject(new Error(message));pending.clear();
};
export async function browserApi(path,payload){
  await ready;
  return new Promise((resolve,reject)=>{
    const id=++nextId;
    pending.set(id,{resolve,reject});
    worker.postMessage({id,path,payload,method:payload===undefined?'GET':'POST'});
  });
}
export function browserReady(){return ready;}

// Explicit opt-in offline bundle download. Works only with a self-hosted
// Pyodide core; never claim offline just because the PWA shell was cached.
function offlineInstallUI(){
  const wrap=document.createElement('div');
  wrap.style.cssText='position:fixed;right:12px;bottom:58px;z-index:9998;max-width:min(350px,90vw);font:11px ui-monospace,monospace;color:#a4c8d1';
  const btn=document.createElement('button');
  btn.textContent='SALVA PER OFFLINE';
  btn.style.cssText='border:1px solid #456a83;border-radius:8px;background:#0e1c2c;color:#d8f1fc;padding:10px 14px;cursor:pointer';
  btn.title='Scarica core Python/WebAssembly e asset essenziali su questo dispositivo';
  const detail=document.createElement('small');
  detail.style.cssText='display:block;margin-top:5px;text-align:right;max-width:350px';
  btn.onclick=async()=>{
    btn.disabled=true;detail.textContent='Verifica dei file offline…';
    if(!('serviceWorker' in navigator)){detail.textContent='Service Worker non disponibile';btn.disabled=false;return}
    try{const reg=await navigator.serviceWorker.ready;
      (navigator.serviceWorker.controller||reg.active)?.postMessage({type:'CACHE_OFFLINE'});
    }catch(err){detail.textContent=String(err.message||err);btn.disabled=false}
  };
  navigator.serviceWorker?.addEventListener('message',e=>{
    const m=e.data||{};
    if(m.kind==='offline_progress'){detail.textContent='Salvataggio offline: '+m.file}
    if(m.kind==='offline_ready'){detail.textContent='Core e asset principali disponibili offline ✓';btn.textContent='OFFLINE PRONTO';}
    if(m.kind==='offline_error'){detail.textContent='Offline incompleto: '+m.error;btn.disabled=false}
  });
  wrap.append(btn,detail);document.body.append(wrap);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',offlineInstallUI,{once:true});else offlineInstallUI();
