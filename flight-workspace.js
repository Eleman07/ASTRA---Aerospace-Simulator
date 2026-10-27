/* Workspace presentation is isolated from the flight model and control handlers. */
import { browserApi } from './browser-api.js';
const $=s=>document.querySelector(s);
let latest=null, canvas, history=[], lastTime=-1, lastVehicle='', activeTab='mission';
const number=(value,digits=1)=>Number.isFinite(value)?value.toLocaleString('it-IT',{maximumFractionDigits:digits}):'—';
export function initFlightWorkspace(){
 const hud=$('.right-hud');
 const tabs=document.createElement('div');tabs.className='workspace-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Pannelli missione');
 const scenario=hud.querySelector('.scenario-select'),telemetry=hud.querySelector('.hud-section');
 const controls=hud.querySelector('.controls-section');
 const systems=document.createElement('section');systems.id='workspace-systems';systems.className='systems-panel';
 systems.innerHTML=`<div class="panel-kicker">MODELLI DI MISSIONE</div><h3>Ogni parametro.<br>Un risultato misurabile.</h3><p class="systems-intro">Calcolati a ogni passo fisico. I monitor di riferimento ricevono lo stato del volo senza comandare gli attuatori.</p><div class="system-values" id="systemValues"><p>In attesa del motore…</p></div><details class="system-assumptions"><summary>Parametri e ipotesi</summary><p>Trave di riferimento caricata dalla pressione dinamica; pannello termico a capacità concentrata; bus elettrico di riferimento (batteria reale per UAV); radio BPSK verso la stazione iniziale. Sole fisso +ECI X. Nessuna ablazione, FEM 3D o fading.</p><form id="systemsConfig"><label>Area pannelli solari · m²<input name="panel_area_m2" type="number" min="0" max="1000" step="0.1" value="4" required></label><label>Carico bus di riferimento · W<input name="bus_load_W" type="number" min="0" max="10000000" value="180" required></label><label>Batteria di riferimento · Wh<input name="battery_capacity_Wh" type="number" min="1" max="10000000" value="1200" required></label><label>Lunghezza trave · m<input name="beam_length_m" type="number" min="0.01" max="100" step="0.01" value="2" required></label><label>Potenza trasmittente · W<input name="transmit_power_W" type="number" min="0.001" max="1000000" step="0.001" value="10" required></label><button type="submit">APPLICA ALLA MISSIONE PRONTA</button><p id="systemsConfigStatus" role="status">I parametri si possono modificare prima del lancio. Reset ripristina i valori di riferimento.</p></form></details><button id="workspaceLibrary" class="workspace-link">Tutti i modelli e i limiti ↗</button>`;
 hud.append(systems);
 const panes=[scenario,telemetry,controls,systems].filter(Boolean);
 // Some legacy sections are nested; extract only the GNC section to create independent panels.
 if(controls)hud.append(controls);
 for(const [id,label,pane] of [['mission','MISSIONE',scenario],['data','DATI',telemetry],['gnc','GNC',controls],['systems','MODELLI',systems]]){
  if(!pane)continue;pane.classList.add('workspace-pane');pane.id ||= 'workspace-'+id;pane.setAttribute('role','tabpanel');pane.setAttribute('aria-labelledby','tab-'+id);
  const b=document.createElement('button');b.type='button';b.id='tab-'+id;b.textContent=label;b.setAttribute('role','tab');b.setAttribute('aria-controls',pane.id);
  b.addEventListener('click',()=>selectTab(id));
  b.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const buttons=[...tabs.children];const i=buttons.indexOf(b);buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length].click();tabs.querySelector('[aria-selected=true]').focus()});tabs.append(b);pane.dataset.workspace=id;
 }
 hud.querySelector('.hud-top').after(tabs);
 function selectTab(id){activeTab=id;for(const pane of panes)pane.classList.toggle('workspace-inactive',pane.dataset.workspace!==id);for(const b of tabs.children){const selected=b.id==='tab-'+id;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1}hud.scrollTop=0;}
 selectTab('mission');
 document.addEventListener('astra:workspace',e=>selectTab(e.detail));
 $('#workspaceLibrary').onclick=()=>$('#disciplineExplorer').click();
 // Turn lengthy asset details into a disclosure while retaining original nodes/IDs.
 for(const selector of ['#visualModelSummary','.vehicle-import']){
  const content=$(selector);if(!content)continue;
  const details=document.createElement('details');details.className='asset-disclosure';const summary=document.createElement('summary');summary.textContent=selector==='#visualModelSummary'?'Modello 3D · dettagli e crediti':'Importa un modello GLB';content.before(details);details.append(summary,content);
 }
 const loading=document.createElement('div');loading.className='asset-loading';loading.setAttribute('role','status');loading.hidden=true;$('.stage').append(loading);
 const summary=$('#visualModelSummary');const checkAsset=()=>{const text=summary?.textContent||'';const pending=/caricamento modello|loading 3D|loading model/i.test(text);const error=/non disponibile|errore|unavailable|non riuscit/i.test(text);loading.hidden=!pending&&!error;loading.textContent=pending?'Caricamento del modello 3D…':'Modello 3D non disponibile · apri dettagli e crediti';};
 if(summary)new MutationObserver(checkAsset).observe(summary,{childList:true,subtree:true,characterData:true});
 const ribbon=document.createElement('section');ribbon.className='flight-ribbon';ribbon.setAttribute('aria-label','Telemetria essenziale');
 ribbon.innerHTML='<div><small>QUOTA</small><strong id="ribbonAltitude">—</strong><span>MSL</span></div><div><small>VELOCITÀ</small><strong id="ribbonSpeed">—</strong><span id="ribbonFrame">ECI</span></div><div><small>RISORSA</small><strong id="ribbonResource">—</strong><span id="ribbonResourceType">PROPELLENTE</span></div><div class="ribbon-trace"><small>PROFILO DI QUOTA</small><canvas width="250" height="52" id="ribbonTrace" aria-label="Andamento quota durante la missione"></canvas></div>';
 $('.stage').append(ribbon);canvas=$('#ribbonTrace');
 const focus=document.createElement('button');focus.id='focusView';focus.type='button';focus.textContent='⤢ VISTA LIBERA';focus.setAttribute('aria-pressed','false');focus.onclick=()=>{const on=document.body.classList.toggle('focus-view');focus.setAttribute('aria-pressed',String(on));focus.textContent=on?'⊞ MOSTRA PANNELLI':'⤢ VISTA LIBERA'};$('.top-actions').prepend(focus);
 const timeline=document.createElement('button');timeline.className='timeline-toggle';timeline.type='button';timeline.textContent='SEQUENZA MISSIONE';timeline.setAttribute('aria-expanded','false');timeline.onclick=()=>{const on=$('.control-deck').classList.toggle('timeline-expanded');timeline.setAttribute('aria-expanded',String(on))};$('.deck-top').append(timeline);
 $('#systemsConfig').addEventListener('submit',async e=>{e.preventDefault();const status=$('#systemsConfigStatus'),button=e.target.querySelector('button');button.disabled=true;try{const payload=Object.fromEntries([...new FormData(e.target)].map(([k,v])=>[k,Number(v)]));const result=await browserApi('/systems/configure',payload);document.dispatchEvent(new CustomEvent('astra:engine-state',{detail:result}));status.textContent='Parametri applicati. I prossimi passi useranno queste ipotesi.'}catch(error){status.textContent=error.message}finally{button.disabled=!!latest?.mission_started}});
 // Default presentation is calm; the existing guide remains one click away.
 queueMicrotask(()=>{if($('#learnToggle')?.getAttribute('aria-pressed')==='true')$('#learnToggle').click()});
}
export function updateFlightWorkspace(state){
 latest=state;
 $('#ribbonAltitude').textContent=number(state.altitude_m>=10000?state.altitude_m/1000:state.altitude_m,1)+(state.altitude_m>=10000?' km':' m');
 $('#ribbonSpeed').textContent=number(state.air_relative_speed_m_s??state.speed_m_s,1)+' m/s';
 $('#ribbonFrame').textContent=state.air_relative_speed_m_s!=null?'RISPETTO ALL’ARIA':state.frame;
 $('#ribbonResource').textContent=number(state.battery_pct??state.propellant_pct,1)+' %';
 $('#ribbonResourceType').textContent=state.vehicle==='drone'?'BATTERIA':'PROPELLENTE';
 if(state.time_s<lastTime||state.vehicle!==lastVehicle||state.time_s===0){history=[];lastTime=-1;lastVehicle=state.vehicle}
 if(state.time_s>lastTime){history.push(state.altitude_m);if(history.length>160)history.shift();lastTime=state.time_s;drawTrace()}
 const s=state.live_systems;if(!s?.thermal)return;
 const rows=[['TERMICA',number(s.thermal.temperature_K)+' K',s.checks.thermal,'Pannello di riferimento'],['STRUTTURE',number(s.structures.stress_Pa/1e6,2)+' MPa',s.checks.structure,'Tensione alla radice · trave'],['ENERGIA',number(s.power.soc_pct)+' %',s.checks.energy,s.power.source==='FLIGHT_BATTERY'?'Batteria del motore UAV':s.power.eclipse?'Bus di riferimento · eclisse':'Bus di riferimento'],['RADIO',s.communications.margin_dB==null?'OCCULTATO':number(s.communications.margin_dB)+' dB',s.checks.radio,'Margine Eb/N₀ · stazione iniziale']];
 $('#systemValues').replaceChildren(...rows.map(([title,value,check,detail])=>{const el=document.createElement('article');el.className='system-metric';const top=document.createElement('div'),small=document.createElement('small'),badge=document.createElement('span'),strong=document.createElement('strong'),note=document.createElement('p');small.textContent=title;badge.textContent=check;badge.dataset.check=check;top.append(small,badge);strong.textContent=value;note.textContent=detail;el.append(top,strong,note);return el}));
 const form=$('#systemsConfig');form.querySelector('button').disabled=!!state.mission_started;
 for(const input of form.querySelectorAll('input')){input.disabled=!!state.mission_started;if(document.activeElement!==input&&state.time_s===0)input.value=s.configuration[input.name]}
}
function drawTrace(){if(!canvas)return;const c=canvas.getContext('2d');c.clearRect(0,0,250,52);c.strokeStyle='#ffffff18';c.beginPath();c.moveTo(0,48);c.lineTo(250,48);c.stroke();if(history.length<2)return;const hi=Math.max(1,...history),lo=Math.min(0,...history);c.beginPath();history.forEach((h,i)=>{const x=i*248/(history.length-1),y=46-(h-lo)/(hi-lo)*40;i?c.lineTo(x,y):c.moveTo(x,y)});c.strokeStyle='#b9aff3';c.lineWidth=1.7;c.stroke();}
