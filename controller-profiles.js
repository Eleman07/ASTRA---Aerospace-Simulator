/* Versioned, data-only Gamepad mappings. No vendor ID implies an axis layout. */
export const FUNCTIONS = ['roll','pitch','yaw','throttle','throttleAbsolute','brakes','cameraX','cameraY','zoom','recenter','autopilot'];
export const SLOTS = ['primary','throttle','pedals'];
const axis=(index,invert=false)=>({source:'axis',device:'primary',index,min:-1,center:0,max:1,deadzone:.12,expo:.25,invert,smoothing:.025});
const buttons=(index,negative)=>({source:'buttons',device:'primary',index,negative});
export function defaultProfile(vehicle='aircraft',preset='standard') {
  const bindings={roll:axis(0),pitch:axis(1,true),yaw:axis(2),throttle:buttons(7,6),brakes:{source:'button',device:'primary',index:0},cameraX:buttons(15,14),cameraY:axis(3),recenter:{source:'button',device:'primary',index:10},autopilot:{source:'button',device:'primary',index:9}};
  if(preset==='legacy'){bindings.roll=axis(2);bindings.pitch=axis(3,true);bindings.yaw=axis(0);delete bindings.cameraY;}
  if(preset==='drone-mode-2'||preset==='drone-mode-1') {
    bindings.yaw=axis(0);bindings.roll=axis(2);bindings.pitch=axis(preset==='drone-mode-2'?3:1,true);bindings.throttle=axis(preset==='drone-mode-2'?1:3,true);delete bindings.cameraY;
  }
  if(preset==='hotas') {
    bindings.roll=axis(0);bindings.pitch=axis(1,true);bindings.yaw=axis(2);delete bindings.throttle;delete bindings.cameraY;
    bindings.throttleAbsolute={...axis(3,true),deadzone:0,expo:0};
    delete bindings.autopilot;delete bindings.recenter;delete bindings.cameraX;delete bindings.brakes;
  }
  return {version:1,name:preset==='hotas'?'HOTAS · calibrazione richiesta':preset,vehicle,preset,devices:{primary:null,throttle:null,pedals:null},bindings,cameraSensitivity:1,haptics:false};
}
export function validateProfile(value) {
  if(!value||typeof value!=='object'||value.version!==1||!['aircraft','drone','space'].includes(value.vehicle)||typeof value.name!=='string'||value.name.length<1||value.name.length>80||!value.bindings||typeof value.bindings!=='object'||Array.isArray(value.bindings))throw Error('Profilo controller non valido');
  const result={version:1,name:value.name,vehicle:value.vehicle,preset:typeof value.preset==='string'?value.preset.slice(0,40):'custom',devices:{},bindings:{},cameraSensitivity:value.cameraSensitivity??1,haptics:value.haptics===true};
  if(!Number.isFinite(result.cameraSensitivity)||result.cameraSensitivity<.1||result.cameraSensitivity>5)throw Error('Sensibilità camera fuori intervallo');
  for(const slot of SLOTS){const d=value.devices?.[slot];if(d!=null&&(typeof d.id!=='string'||d.id.length>512||!Number.isInteger(d.index)||d.index<0||d.index>63))throw Error('Identità dispositivo non valida');result.devices[slot]=d?{id:d.id,index:d.index}:null;}
  for(const [name,b] of Object.entries(value.bindings)) {
    if(!FUNCTIONS.includes(name)||!b||!['axis','button','buttons'].includes(b.source)||!SLOTS.includes(b.device)||!Number.isInteger(b.index)||b.index<0||b.index>255)throw Error('Mappatura non valida: '+name);
    const clean={source:b.source,device:b.device,index:b.index};
    if(b.source==='buttons'){if(!Number.isInteger(b.negative)||b.negative<0||b.negative>255||b.negative===b.index)throw Error('Coppia pulsanti non valida');clean.negative=b.negative;}
    if(b.source==='axis') {
      for(const [k,def] of Object.entries({min:-1,center:0,max:1,deadzone:.12,expo:0,smoothing:0}))clean[k]=b[k]??def;
      if(!['min','center','max','deadzone','expo','smoothing'].every(k=>Number.isFinite(clean[k]))||clean.min< -1||clean.max>1||clean.min>=clean.center||clean.center>=clean.max||clean.deadzone<0||clean.deadzone>.5||clean.expo<0||clean.expo>1||clean.smoothing<0||clean.smoothing>.3)throw Error('Calibrazione asse non valida');
      clean.invert=b.invert===true;
    }
    result.bindings[name]=clean;
  }
  // A physical axis cannot rotate both camera and vehicle accidentally.
  const flight=Object.entries(result.bindings).filter(([k,b])=>['roll','pitch','yaw','throttle','throttleAbsolute'].includes(k)&&b.source==='axis');
  for(const [name,b] of Object.entries(result.bindings))if(['cameraX','cameraY','zoom'].includes(name)&&b.source==='axis'&&flight.some(([,f])=>f.device===b.device&&f.index===b.index))throw Error('Asse condiviso tra camera e volo');
  if(result.bindings.throttle&&result.bindings.throttleAbsolute)throw Error('Scegli gas assoluto oppure incrementale');
  return result;
}
export const buttonName=(index,id='')=>(/dualsense|playstation|054c|sony/i.test(id)?['Croce','Cerchio','Quadrato','Triangolo','L1','R1','L2','R2','Create','Options','L3','R3','D-pad ↑','D-pad ↓','D-pad ←','D-pad →','PS']:['A','B','X','Y','LB','RB','LT','RT','View','Menu','LS','RS','D-pad ↑','D-pad ↓','D-pad ←','D-pad →','Xbox'])[index]||'Pulsante '+index;
