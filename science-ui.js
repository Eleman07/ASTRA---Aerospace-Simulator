import {aerospaceDisciplines} from './disciplines.js';
let root, status, settings, last='';
const labels=Object.fromEntries(aerospaceDisciplines.map(x=>[x.id,x.name]));
export function mountSciencePanel(onApply){
 settings={enabled:true,configuration:{seed:42,epoch_utc:'2026-10-28T00:00:00Z'}};
 try{const saved=JSON.parse(localStorage.getItem('astra-science-v1'));if(typeof saved?.enabled==='boolean')settings.enabled=saved.enabled;}catch{}
 root=document.createElement('section');root.className='advanced-science';root.innerHTML=`<div class="panel-kicker">SCIENZA AVANZATA · 13 DISCIPLINE</div><h3>La scienza durante il volo.</h3><p>Stato, forze, vincoli e verifiche aggiornati dal motore. Apri una disciplina per leggere accoppiamento e limiti.</p><form><label><input type="checkbox" name="enabled"> Modelli avanzati nel motore</label><label>Seed riproducibile<input type="number" name="seed" min="0" max="2147483647" value="42" required></label><label>Raffiche von Karman · RMS m/s<input name="sigma" type="number" value="0" min="0" max="5" step="0.05" required></label><label>Epoca UTC<input name="epoch" type="date" value="2026-10-28" min="1800-01-01" max="2049-12-31" required></label><label><input name="radio" type="checkbox"> Comandi Python attraverso il canale radio simulato</label><button>APPLICA E RICARICA MISSIONE</button><p role="status" class="science-status"></p></form><div class="science-models"></div>`;
 const form=root.querySelector('form');form.elements.enabled.checked=settings.enabled;
 status=root.querySelector('[role=status]');
 form.onsubmit=async e=>{e.preventDefault();if(form.querySelector('button').disabled)return;
  const previous=structuredClone(settings);settings.enabled=form.elements.enabled.checked;
  settings.configuration={seed:Number(form.elements.seed.value),turbulence_sigma_m_s:Number(form.elements.sigma.value),epoch_utc:form.elements.epoch.value+'T00:00:00Z',radio_commands:form.elements.radio.checked};
  const ok=await onApply();if(ok){localStorage.setItem('astra-science-v1',JSON.stringify(settings));status.textContent='Configurazione applicata. Stesso seed e stessi comandi riproducono la missione.';}else{Object.assign(settings,previous);status.textContent='Configurazione non applicata. Resetta prima la missione.';}
 };
 document.querySelector('#workspace-systems').prepend(root);
 return settings;
}
function metric(id,v){const f=(n,u,d=2)=>Number.isFinite(n)?`${n.toLocaleString('it-IT',{maximumFractionDigits:d})} ${u}`:'—';
 switch(id){case'propulsion':return f(v.ideal_thrust_N??v.actual_throttle_pct,v.ideal_thrust_N!=null?'N':'%');case'aerodynamics':return f(v.lift_lag_correction,'ΔCL',4);case'celestial-mechanics':return f(Math.hypot(...(v.third_body_acceleration_eci_m_s2||[])),'m/s²',8);case'mission-design':return v.tracking_error_m!=null?f(v.tracking_error_m,'m'):v.phase;case'rendezvous':return f(v.range_m,'m');case'structures':return f(v.root_stress_Pa/1e6,'MPa',3);case'atmosphere':return f(v.dynamic_pressure_Pa,'Pa');case'power':return f(v.soc_pct,'%');case'communications':return f(v.margin_dB,'dB');case'robotics':return f(v.clearance_m,'m · ostacolo più vicino');case'launch-systems':return f(v.mass_kg,'kg');case'planetary-landing':return f(v.altitude_m,'m · quota lunare');case'systems-engineering':return `${v.requirements?.filter(r=>r.evidence.status==='FAIL').length||0} requisiti falliti`;default:return'—';}
}
export function updateSciencePanel(state){if(!root)return;
 const form=root.querySelector('form');form.querySelector('button').disabled=!!state.mission_started;
 const s=state.science;const key=[state.vehicle,state.scenario,state.time_s,s?.enabled].join(':');if(key===last)return;last=key;
 const models=root.querySelector('.science-models');
 if(!s?.enabled){status.textContent='Percorso di riferimento attivo. Abilita i modelli avanzati prima del lancio.';models.replaceChildren();return;}
 status.textContent=`13 discipline integrate · ${Object.values(s.disciplines).filter(d=>d.status==='ACTIVE').length} applicabili alla missione · ${s.version}`;
 const opened=new Set([...models.querySelectorAll('details[open]')].map(e=>e.dataset.science));models.replaceChildren(...Object.entries(s.disciplines).map(([id,d])=>{const el=document.createElement('details');el.dataset.science=id;el.open=opened.has(id);const summary=document.createElement('summary');const name=document.createElement('span');name.textContent=labels[id]||id;const value=document.createElement('strong');value.textContent=d.status==='ACTIVE'?metric(id,d.values):'ALTRA MISSIONE';summary.append(name,value);const coupling=document.createElement('small');coupling.textContent=d.coupling.replaceAll('_',' ');const p=document.createElement('p');p.textContent=d.limits;const data=document.createElement('pre');data.textContent=JSON.stringify(d.values,null,2);el.append(summary,coupling,p,data);return el;}));
}
