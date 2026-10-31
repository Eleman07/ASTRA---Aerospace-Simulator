import { defaultProfile, validateProfile } from './controller-profiles.js';
const clamp=(x,lo=-1,hi=1)=>Math.max(lo,Math.min(hi,x));
export function calibratedAxis(raw,b) {
  if(!Number.isFinite(raw))return null;
  const x=clamp((raw-b.center)/(raw>=b.center?b.max-b.center:b.center-b.min));
  const magnitude=Math.abs(x)<=b.deadzone?0:(Math.abs(x)-b.deadzone)/(1-b.deadzone);
  return Math.sign(x)*((1-b.expo)*magnitude+b.expo*magnitude**3)*(b.invert?-1:1);
}
export class InputDeviceManager {
  constructor({getGamepads=()=>globalThis.navigator?.getGamepads?.()||[],storage=globalThis.localStorage}={}) {
    this.getGamepads=getGamepads;this.storage=storage;this.vehicle='aircraft';this.profile=defaultProfile();this.pads=[];this.armed=false;this.filtered={};this.previous={};this.message='Seleziona e abilita un controller in modalità manuale';this.pickup=false;this.last=null;
    this.load('aircraft');
  }
  disarm(message='Controller disabilitato'){this.armed=false;this.filtered={};this.previous={};this.pickup=false;this.message=message;}
  setProfile(p){this.profile=validateProfile(p);this.disarm('Profilo caricato · riabilita esplicitamente');}
  load(vehicle){this.vehicle=vehicle;let profile=defaultProfile(vehicle);try{const p=JSON.parse(this.storage?.getItem('astra-controller-v1-'+vehicle));if(p&&p.vehicle===vehicle)profile=validateProfile(p);}catch{}this.setProfile(profile);}
  save(){this.storage?.setItem('astra-controller-v1-'+this.vehicle,JSON.stringify(validateProfile(this.profile)));}
  select(slot,pad){this.disarm('Dispositivo cambiato · riabilita esplicitamente');this.profile.devices[slot]=pad?{id:pad.id,index:pad.index}:null;}
  resolve(slot){const d=this.profile.devices[slot];return d?this.pads.find(p=>p.index===d.index&&p.id===d.id):null;}
  arm(mode){if(mode!=='manual')return this.disarm('Attiva prima MANUAL OVERRIDE');if(!this.resolve('primary'))return this.disarm('Seleziona il dispositivo principale');this.armed=true;this.filtered={};this.previous={};this.pickup=false;this.waitNeutral=true;this.message='Centra gli assi di assetto per acquisire il controllo';}
  poll(dt,{mode='auto',throttle=0,enabled=true}={}) {
    try{this.pads=Array.from(this.getGamepads()||[]).filter(p=>p?.connected);}catch{this.pads=[];}
    const sample={axes:{roll:0,pitch:0,yaw:0,throttle:0,brakes:0},camera:{x:0,y:0,zoom:0},actions:{},raw:{},calibrated:{},source:null,lost:false,saturated:false,throttleReady:false};
    const used=new Set(['primary',...Object.values(this.profile.bindings).map(b=>b.device)]);
    if(this.armed&&(!enabled||mode!=='manual'||[...used].some(slot=>!this.resolve(slot)))){sample.lost=true;this.disarm(!enabled?'Controllo sospeso · riabilita al ritorno':mode!=='manual'?'Autorità al controllo '+mode:'Dispositivo scollegato · richiesta GNC');}
    let invalid=false;
    for(const [name,b] of Object.entries(this.profile.bindings)) {
      const pad=this.resolve(b.device);if(!pad)continue;
      let value=0;
      if(b.source==='axis') {const raw=pad.axes?.[b.index];sample.raw[name]=raw;value=calibratedAxis(raw,b);}
      else {const read=i=>{const v=pad.buttons?.[i]?.value;return Number.isFinite(v)?clamp(v,0,1):null;};const positive=read(b.index),negative=b.source==='buttons'?read(b.negative):0;value=positive==null||negative==null?null:positive-negative;sample.raw[name]=value;}
      if(value==null){invalid=true;continue;}
      const alpha=b.smoothing>0?1-Math.exp(-clamp(Number.isFinite(dt)?dt:0,0,.1)/b.smoothing):1;
      const previous=this.filtered[name]??value;
      const filtered=previous+alpha*(value-previous);this.filtered[name]=filtered;
      sample.calibrated[name]=Math.abs(filtered)<1e-5?0:filtered;
      sample.saturated ||= Math.abs(value)>.995;
    }
    if(invalid&&this.armed){sample.lost=true;this.disarm('Asse/pulsante mancante o non finito · controlla la mappatura');}
    const values=sample.calibrated;
    if(this.armed&&this.waitNeutral&&['roll','pitch','yaw','throttle'].every(k=>Math.abs(values[k]||0)<.05)){this.waitNeutral=false;this.message='Controller attivo';}
    if(this.armed&&!this.waitNeutral) {
      sample.source='controller';
      for(const k of Object.keys(sample.axes))sample.axes[k]=values[k]||0;
      if(this.profile.bindings.throttleAbsolute){const absolute=((values.throttleAbsolute??-1)+1)/2;if(Math.abs(absolute-clamp(throttle/100,0,1))<.07)this.pickup=true;if(this.pickup)sample.axes.throttleAbsolute=absolute;else this.message='Allinea la leva al gas attuale per acquisirla';}
      sample.throttleReady=this.pickup;
      sample.camera={x:(values.cameraX||0)*this.profile.cameraSensitivity,y:(values.cameraY||0)*this.profile.cameraSensitivity,zoom:values.zoom||0};
      for(const k of ['recenter','autopilot'])sample.actions[k]=(values[k]||0)>.5&&!(this.previous[k]>.5);
    }
    this.previous={...values};this.last=sample;return sample;
  }
  rumble(){if(!this.profile.haptics||!this.armed)return;try{this.resolve('primary')?.vibrationActuator?.playEffect?.('dual-rumble',{duration:120,strongMagnitude:.2,weakMagnitude:.3})?.catch(()=>{});}catch{}}
}
