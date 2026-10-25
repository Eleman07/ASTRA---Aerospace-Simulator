import { browserApi } from "./browser-api.js";
// ASTRA Engineering Studio: independent SI-domain solvers, no remote services.
const studies={
 planetary_landing_6dof:{name:'EDL · planetario 6-DoF',subtitle:'Corpo rigido e assetto quaternion, RK4, inerzie, RCS ideale, TVC virtuale e propellente finito',inputs:[['surface_gravity_m_s2','Gravità superficiale · m/s²',1.62,.01,30],['initial_altitude_m','Quota iniziale · m',900,2,1e6],['initial_east_m','Offset est · m',95,-1e6,1e6],['initial_north_m','Offset nord · m',-35,-1e6,1e6],['initial_vertical_speed_m_s','Velocità verticale · m/s',-30,-3000,3000],['wet_mass_kg','Massa iniziale · kg',1000,10,1e7],['dry_mass_kg','Massa a secco · kg',650,1,1e7],['maximum_thrust_N','Spinta massima · N',14500,1,1e9],['maximum_body_torque_N_m','Momento massimo · Nm',1800,.01,1e7],['maximum_tilt_deg','Inclinazione limite · °',25,1,80]],metrics:[['landing_status','Esito'],['touchdown_speed_m_s','Velocità contatto · m/s'],['horizontal_touchdown_error_m','Errore laterale · m'],['propellant_used_kg','Propellente usato · kg'],['maximum_dynamic_pressure_Pa','q massimo · Pa']],series:[['altitude_m','Quota · m'],['horizontal_speed_m_s','V laterale · m/s']]},
 rocket_cycle:{name:'Propulsione · ciclo gas generator',subtitle:'Bilancio di potenza turbopompa/turbina, flussi fuel/oxidizer, bleed e Isp effettivo',inputs:[['chamber_pressure_Pa','Pressione camera · Pa',7e6,1e5,2e8],['chamber_temperature_K','Temperatura camera · K',3400,100,10000],['throat_area_m2','Gola · m²',.03,1e-7,100],['expansion_ratio','Rapporto espansione',16,1,200],['tank_pressure_Pa','Pressione serbatoi · Pa',3e5,1e3,1e7],['oxidizer_to_fuel_ratio','Rapporto O/F',2.6,.1,20],['pump_efficiency','Rendimento pompe',.72,.1,1],['turbine_efficiency','Rendimento turbina',.64,.1,1],['turbine_inlet_temperature_K','Temperatura turbina · K',950,150,3000]],metrics:[['nozzle_thrust_N','Spinta ideale · N'],['total_pump_power_W','Potenza pompe · W'],['turbine_mass_flow_kg_s','Portata turbina · kg/s'],['turbine_propellant_fraction','Frazione propellente turbina'],['estimated_effective_isp_s','Isp effettivo · s'],['power_balance_residual_W','Residuo bilancio · W']]},
 lifting_line:{name:'Aerodinamica · lifting-line Fourier',subtitle:'Distribuzione portanza ellittica/non ellittica, induzione, svergolamento e rastremazione',inputs:[['wingspan_m','Apertura alare · m',12,.2,200],['wing_area_m2','Superficie alare · m²',18,.02,2000],['taper_ratio','Rastremazione tip/root',.65,.05,1],['tip_twist_deg','Svergolamento punta · °',-2,-15,15],['angle_of_attack_deg','Incidenza · °',5,-12,14],['airspeed_m_s','Velocità · m/s',65,1,350],['spanwise_stations','Stazioni numeriche',18,6,32]],metrics:[['lift_coefficient_CL','CL'],['induced_drag_coefficient_CDi','CDi'],['oswald_inviscid_efficiency','e indotta'],['lift_N','Portanza · N'],['induced_drag_N','Resistenza indotta · N']],series:[['lift_per_span_N_m','Portanza locale N/m']]},
 lambert:{name:'Traiettorie · Lambert 3D',subtitle:'Problema ai limiti 3D a due corpi, tempo di volo e velocità di partenza/arrivo',inputs:[['time_of_flight_s','Tempo di volo · s',2000,20,1e8]],vectors:[['position_start_eci_m','ECI partenza · m',[7000000,0,0]],['position_target_eci_m','ECI arrivo · m',[0,8000000,0]]],metrics:[['transfer_angle_deg','Angolo trasferimento · °'],['departure_speed_m_s','Velocità partenza · m/s'],['arrival_speed_m_s','Velocità arrivo · m/s'],['semi_latus_rectum_m','Parametro p · m']]},
 orbit_eclipse_power:{name:'Sistemi elettrici · geometria eclissi',subtitle:'Orbita circolare con ombra conica terrestre, incidenza array ECI e SoC',inputs:[['orbital_altitude_m','Quota orbitale · m',450000,150000,1e8],['inclination_deg','Inclinazione · °',51.6,0,180],['ascending_node_deg','RAAN · °',20,-360,360],['sun_right_ascension_deg','RA solare · °',0,-360,360],['sun_declination_deg','Declinazione solare · °',0,-90,90],['solar_array_area_m2','Area array · m²',6,0,1e5],['solar_efficiency','Rendimento celle',.29,0,.95],['bus_load_W','Carico bus · W',400,0,1e8],['battery_capacity_Wh','Capacità batteria · Wh',1000,1,1e8]],vectors:[['panel_normal_eci','Normale pannello ECI',[1,0,0]]],metrics:[['eclipse_fraction','Frazione d’eclissi'],['generated_energy_Wh','Generazione · Wh'],['final_soc_fraction','SOC finale'],['unserved_load_Wh','Carico non servito · Wh']],series:[['soc_fraction','SOC'],['generated_power_W','Potenza · W']]},
 radio_link:{name:'Radio · antenne/attenuazione/BER',subtitle:'Puntamento antenna, attenuazione atmosferica, BPSK AWGN, latenza e packet error',inputs:[['range_m','Distanza · m',400000,1,1e13],['frequency_Hz','Frequenza · Hz',2.2e9,1e5,1e12],['antenna_diameter_m','Diametro antenna · m',1.2,.01,100],['pointing_error_deg','Errore puntamento · °',.1,0,180],['elevation_angle_deg','Elevazione stazione · °',45,-90,90],['specific_atmospheric_attenuation_dB_km','Attenuazione atmosfera · dB/km',.02,0,1000],['data_rate_bps','Data rate · bps',100000,1,1e10]],metrics:[['line_of_sight','Visibilità'],['pointing_loss_dB','Perdita puntamento · dB'],['atmospheric_loss_dB','Perdita atmosfera · dB'],['ebn0_dB','Eb/N0 · dB'],['bit_error_probability','BER teorico'],['packet_error_probability','Packet error'],['propagation_latency_s','Latenza propagazione · s']]},

 propulsion:{name:'Propulsione · ugello Laval',subtitle:'Flusso comprimibile isentropico con inversione Mach supersonica',inputs:[['chamber_pressure_Pa','Pressione camera · Pa',7e6,1e4,2e8],['chamber_temperature_K','Temperatura camera · K',3400,100,10000],['throat_area_m2','Area di gola · m²',.03,.0000001,100],['expansion_ratio','Rapporto espansione Ae/At',16,1,200],['specific_heat_ratio','γ gas',1.22,1.05,1.67],['altitude_m','Quota · m',0,0,1000000]],metrics:[['exit_mach','Mach uscita'],['ideal_thrust_N','Spinta ideale · N'],['ideal_isp_s','Isp ideale · s'],['exhaust_mass_flow_kg_s','Portata · kg/s'],['risk_of_overexpanded_flow_separation','Rischio separazione'],['ideal_pressure_matched_expansion_ratio_capped_200','Rapporto ottimo teorico']]},
 orbit:{name:'Orbita · Cowell RK5(4)',subtitle:'Gravità J₂, resistenza COESA76 e passo adattivo',inputs:[['initial_altitude_m','Quota iniziale · m',400000,80001,100000000],['duration_s','Propagazione · s',5400,1,604800],['drag_area_m2','Area di resistenza · m²',1,0,100000],['mass_kg','Massa · kg',500,1,10000000],['relative_tolerance','Errore relativo',1e-8,1e-12,.001]],metrics:[['accepted_steps','Passi accettati'],['rejected_steps','Passi scartati'],['minimum_altitude_m','Quota minima · m'],['specific_kepler_energy_relative_change','Variazione energia kepleriana']],series:[['altitude_m','Quota (m)']]},
 aircraft_trim:{name:'Aerodinamica · trim',subtitle:'Equilibrio portanza/peso, polare con stallo, bisezione',inputs:[['airspeed_m_s','Velocità vera · m/s',95,.1,1000],['altitude_m','Quota · m',1000,0,85000],['mass_kg','Massa · kg',6124,1,10000000],['bank_deg','Angolo di banca · °',0,-70,70]],metrics:[['feasible','Trim possibile'],['angle_of_attack_deg','Angolo α · °'],['drag_N','Resistenza · N'],['stall_margin_deg','Margine stallo · °'],['required_throttle_pct_static_estimate','Spinta statica richiesta · %']]},
 beam:{name:'Strutture · FEM trave',subtitle:'Elementi di Hermite, equilibrio carichi e tensione di flessione',inputs:[['length_m','Lunghezza · m',2,.01,100],['young_modulus_Pa','Modulo E · Pa',7e10,100000,1e13],['width_m','Larghezza · m',.1,.00001,10],['height_m','Altezza · m',.08,.00001,10],['tip_force_N','Forza all’estremità · N',-1000,-1e8,1e8],['distributed_force_N_m','Carico distribuito · N/m',-200,-1e7,1e7]],metrics:[['tip_deflection_m','Flessione finale · m'],['max_abs_bending_stress_Pa','Tensione max · Pa'],['yield_safety_factor','Fattore sicurezza'],['root_reaction_force_N','Reazione vincolo · N']],series:[['deflection_m','Flessione (m)']]},
 thermal:{name:'Termica · volumi finiti',subtitle:'Conduzione implicita, radiazione non lineare risolta con Newton',inputs:[['thickness_m','Spessore · m',.05,.00001,2],['conductivity_W_mK','Conducibilità · W/(m·K)',1.1,.0001,1000],['incident_heat_flux_W_m2','Flusso incidente · W/m²',20000,0,1e8],['duration_s','Tempo · s',120,.001,86400],['emissivity','Emissività',.8,0,1]],metrics:[['maximum_temperature_K','Temperatura max · K'],['thermal_diffusivity_m2_s','Diffusività · m²/s']],series:[['front_temperature_K','Superficie (K)'],['back_temperature_K','Retro (K)']]},
 power:{name:'Elettrica · orbita/eclipse',subtitle:'Efficienza pannelli, carica/scarica e saturazione SoC',inputs:[['solar_array_area_m2','Superficie solare · m²',4,0,1e5],['solar_efficiency','Efficienza array',.28,0,.95],['load_W','Consumo · W',450,0,1e8],['battery_capacity_Wh','Batteria · Wh',800,0,1e8],['eclipse_fraction','Frazione in eclissi',.35,0,.95]],metrics:[['periodic_average_generation_W','Generazione media · W'],['minimum_soc_fraction','SoC minimo'],['unserved_load_Wh','Energia non fornita · Wh'],['energy_neutral_orbit','Bilancio energetico sufficiente']],series:[['soc_fraction','Carica batteria']]},
 robotics_route:{name:'Robotica UAV · pianificazione A*',subtitle:'Percorso 2D, griglia di occupazione e ostacoli sintetici',inputs:[['grid_width','Larghezza griglia · celle',36,8,96],['grid_height','Altezza griglia · celle',28,8,96],['cell_size_m','Dimensione cella · m',2,.05,100],['obstacle_fraction','Densità ostacoli',.15,0,.45],['seed','Seed deterministico',42,0,2147483647]],metrics:[['found','Percorso trovato'],['path_length_m','Lunghezza · m'],['expanded_nodes','Nodi esplorati'],['obstacle_cells','Celle occupate']],route:true},
 planetary_descent:{name:'Planetary EDL · discesa propulsa',subtitle:'Modello verticale RK4 con massa variabile, gravità e controllo di frenata',inputs:[['surface_gravity_m_s2','Gravità superficiale · m/s²',1.62,.01,30],['initial_altitude_m','Quota iniziale · m',1200,1,1000000],['initial_vertical_speed_m_s','Velocità verticale · m/s',-35,-10000,10000],['initial_mass_kg','Massa iniziale · kg',1000,10,10000000],['dry_mass_kg','Massa a secco · kg',650,1,10000000],['maximum_thrust_N','Spinta max · N',14500,1,1000000000],['isp_s','Isp · s',310,20,10000],['surface_density_kg_m3','Densità atmosfera · kg/m³',0,0,15]],metrics:[['landing_status','Esito'],['touchdown_speed_m_s','Velocità impatto · m/s'],['propellant_consumed_kg','Propellente usato · kg'],['elapsed_s','Tempo · s']],series:[['altitude_m','Quota (m)'],['vertical_speed_m_s','Velocità verticale (m/s)']]},
 link:{name:'Comunicazioni · link budget',subtitle:'Friis, rumore termico, Eb/N₀, capacità Shannon',inputs:[['range_m','Distanza · m',4e5,1,1e13],['frequency_Hz','Frequenza · Hz',2.2e9,1000,1e12],['tx_power_dBm','Potenza trasmettitore · dBm',30,-100,100],['tx_gain_dBi','Guadagno antenna Tx · dBi',15,-100,100],['rx_gain_dBi','Guadagno antenna Rx · dBi',20,-100,100],['data_rate_bps','Data rate · bit/s',100000,1,1e11]],metrics:[['received_power_dBm','Potenza ricevuta · dBm'],['ebn0_dB','Eb/N₀ · dB'],['link_margin_dB','Margine · dB'],['shannon_capacity_bps','Capacità teorica · bit/s'],['passes_link_budget','Link budget verificato']]}
};
// ASTRA_V14_STUDIES: tested scientific analysis UI entries.
Object.assign(studies, {
  aero_envelope:{name:'Aerodynamics / Performance envelope',subtitle:'Finite wing, stall boundary and Mach-corrected quasi-steady drag',inputs:[['mass_kg','Mass · kg',1250,1,1e7],['wing_area_m2','Wing area · m²',16.2,.1,2000],['aspect_ratio','Aspect ratio',7.4,2,30],['oswald_efficiency','Oswald efficiency',.8,.3,1],['CL_max','CL max',1.5,.2,4],['CD0','Parasite drag CD0',.027,.001,.3],['altitude_m','Altitude · m',2000,-500,20000]],metrics:[['stall_speed_estimate_m_s','Stall speed estimate · m/s'],['induced_drag_factor','Induced-drag factor']],series:[['drag_N','Drag · N']]},
  rocket_nozzle_sweep:{name:'Propulsion / Nozzle altitude sweep',subtitle:'Choked mass flow, supersonic expansion and altitude-dependent thrust',inputs:[['chamber_pressure_Pa','Chamber pressure · Pa',7e6,1e5,1e9],['chamber_temperature_K','Chamber temperature · K',3500,300,10000],['gamma','Isentropic gamma',1.22,1.05,1.67],['throat_diameter_m','Throat diameter · m',.16,.005,10],['expansion_ratio','Expansion ratio',12,1,2000]],metrics:[['mass_flow_kg_s','Mass flow · kg/s'],['exit_mach','Nozzle exit Mach'],['exit_pressure_Pa','Exit pressure · Pa'],['exit_velocity_m_s','Exit speed · m/s']],series:[['thrust_N','Thrust · N']]},
  wind_shear:{name:'Atmosphere / Boundary-layer wind shear',subtitle:'Neutral surface-layer log profile with wind gradient and ground roughness',inputs:[['reference_wind_m_s','Wind speed at reference · m/s',8,0,80],['reference_height_m','Reference height · m',10,2,200],['roughness_length_m','Surface roughness · m',.03,.0001,1],['direction_toward_deg','Wind direction toward · °',90,-360,360]],metrics:[['reference_height_m','Reference height · m'],['roughness_length_m','Roughness · m']],series:[['wind_speed_m_s','Wind · m/s']]}
});

const $=selector=>document.querySelector(selector);
const fmt=value=>typeof value==='boolean'?(value?'SÌ':'NO'):typeof value==='number'?(Math.abs(value)>=100000||Math.abs(value)<.001&&value!==0?value.toExponential(3):value.toLocaleString('it-IT',{maximumFractionDigits:5})):String(value??'—');
function plot(canvas,data,keys){
 const ctx=canvas.getContext('2d');if(!ctx)return;
 const dpr=Math.min(window.devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(300,rect.width),h=220;
 canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 const traces=keys.map(([key,label])=>({label,points:data.map((row,i)=>({x:i,y:Number(row[key])})).filter(p=>Number.isFinite(p.y))})).filter(t=>t.points.length>1);
 if(!traces.length)return;
 const values=traces.flatMap(t=>t.points.map(p=>p.y)),vmin=Math.min(...values),vmax=Math.max(...values),span=Math.max(1e-12,vmax-vmin),left=55,right=w-20,top=20,bottom=h-38;
 ctx.strokeStyle='rgba(160,211,236,.18)';ctx.lineWidth=1;ctx.fillStyle='#b5ced8';ctx.font='12px system-ui';
 for(let i=0;i<=4;i++){const y=top+(bottom-top)*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(fmt(vmax-span*i/4),4,y+4)}
 const colors=['#65e1c7','#ffaa6b','#8ba8ff'];
 traces.forEach((trace,i)=>{ctx.strokeStyle=colors[i%colors.length];ctx.lineWidth=2;ctx.beginPath();trace.points.forEach((point,j)=>{const x=left+(right-left)*point.x/Math.max(1,data.length-1),y=bottom-(bottom-top)*(point.y-vmin)/span;j?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.fillStyle=colors[i%colors.length];ctx.fillText(trace.label,left+i*(right-left)/Math.max(1,traces.length),h-12)});
}

function plotRoute(canvas,result){
 const ctx=canvas.getContext('2d');if(!ctx)return;
 const dpr=Math.min(devicePixelRatio||1,2),rect=canvas.getBoundingClientRect(),w=Math.max(300,Math.floor(rect.width)),h=260;
 canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 const [cols,rows]=result.grid_size_cells,pad=18,scale=Math.min((w-2*pad)/cols,(h-2*pad)/rows),ox=(w-cols*scale)/2,oy=(h-rows*scale)/2;
 ctx.fillStyle='#102638';ctx.fillRect(ox,oy,cols*scale,rows*scale);
 ctx.fillStyle='#5a707f';for(const [x,y] of result.obstacles)ctx.fillRect(ox+x*scale,oy+y*scale,scale*.93,scale*.93);
 if(result.waypoints_m.length){ctx.strokeStyle='#6cf4c9';ctx.lineWidth=Math.max(2,scale*.42);ctx.lineCap='round';ctx.beginPath();result.waypoints_m.forEach(([x,y],index)=>{const xx=ox+(x/result.cell_size_m+.5)*scale,yy=oy+(y/result.cell_size_m+.5)*scale;index?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy)});ctx.stroke()}
 ctx.fillStyle='#69d9ff';ctx.beginPath();ctx.arc(ox+1.5*scale,oy+1.5*scale,Math.max(3,scale*.5),0,2*Math.PI);ctx.fill();
 ctx.fillStyle='#ffae72';ctx.beginPath();ctx.arc(ox+(cols-1.5)*scale,oy+(rows-1.5)*scale,Math.max(3,scale*.5),0,2*Math.PI);ctx.fill();
}

export function initEngineeringStudio(){
 const launcher=$('#openEngineeringStudio'),dialog=$('#engineeringStudioDialog'),select=$('#engineeringAnalysis'),form=$('#engineeringFields'),run=$('#engineeringRun'),summary=$('#engineeringMetrics'),info=$('#engineeringStatus'),canvas=$('#engineeringChart'),download=$('#engineeringDownload');
 if(!launcher||!dialog)return;
 let last=null,runId=0,livePending=false;
 const applyWind=$('#engineeringApplyWind');
 const selectType=()=>{
  if(applyWind)applyWind.hidden=select.value!=='wind_shear';
  const spec=studies[select.value];if(!spec)return;
  $('#engineeringSubtitle').textContent=spec.subtitle;
  form.replaceChildren();
  for(const [key,label,value,min,max] of spec.inputs){const wrap=document.createElement('label');wrap.textContent=label;const input=document.createElement('input');input.type='number';input.name=key;input.value=String(value);input.min=String(min);input.max=String(max);input.step='any';input.required=true;wrap.append(input);form.append(wrap)}
  for(const [key,label,values] of spec.vectors||[]){
   const title=document.createElement('div');title.className='engineering-vector-label';title.textContent=label;form.append(title);
   for(const [axis,value] of values.map((v,i)=>[['x','y','z'][i],v])){
    const wrap=document.createElement('label');wrap.textContent=axis.toUpperCase();
    const input=document.createElement('input');input.type='number';input.name=`${key}_${axis}`;
    input.value=String(value);input.step='any';input.required=true;wrap.append(input);form.append(wrap);
   }
  }
  summary.replaceChildren();canvas.hidden=true;download.disabled=true;last=null;const current=$('#engineeringLiveContext');if(current)current.hidden=true;info.textContent='Imposta i parametri e avvia il solver. La simulazione di volo attiva non viene modificata.';
 };
 for(const [key,spec] of Object.entries(studies)){const option=document.createElement('option');option.value=key;option.textContent=spec.name;select.append(option)}
 select.addEventListener('change',selectType);selectType();
 launcher.addEventListener('click',()=>{if(!dialog.open)dialog.showModal();launcher.classList.add('rail-active')});
 $('#engineeringClose').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>launcher.classList.remove('rail-active'));
 run.addEventListener('click',async()=>{
  if(![...form.querySelectorAll('input')].every(input=>input.reportValidity())){info.textContent='Controlla i parametri: uno o più valori non sono validi.';return;}
  const liveMode=livePending;livePending=false;const id=++runId,spec=studies[select.value],request={analysis:select.value};
  for(const input of form.querySelectorAll('input')){const val=Number(input.value);if(!input.value.trim()||!Number.isFinite(val)){info.textContent='Inserire valori numerici finiti.';return}request[input.name]=val}
  for(const [key] of spec.vectors||[]){request[key]=['x','y','z'].map(axis=>{const id=`${key}_${axis}`,v=request[id];delete request[id];return v})}
  run.disabled=true;info.textContent='Calcolo scientifico in esecuzione…';download.disabled=true;
  try{
   const result=await browserApi(liveMode?'/engineering/live':'/engineering',request);
   if(id!==runId)return;
   last={request,result};summary.replaceChildren();
   for(const [key,label] of spec.metrics){if(!(key in result))continue;const item=document.createElement('div'),caption=document.createElement('small'),value=document.createElement('strong');caption.textContent=label;value.textContent=fmt(result[key]);item.append(caption,value);summary.append(item)}
   canvas.hidden=true;
   if(spec.route&&Array.isArray(result.waypoints_m)){
    canvas.hidden=false;requestAnimationFrame(()=>plotRoute(canvas,result));
   }else if(spec.series&&Array.isArray(result.samples)&&result.samples.length>1){canvas.hidden=false;requestAnimationFrame(()=>plot(canvas,result.samples,spec.series))}
   info.textContent=`${result.solver||result.model||result.analysis}. LIMITS: ${Array.isArray(result.limitations)?result.limitations.join(' · '):(result.limits||'See the exported JSON report')}`;if(result.mission_context){const c=result.mission_context;const used=Object.keys(c.inputs_from_telemetry||{});info.textContent+=` | ${c.mode} · t=${Number(c.time_s||0).toFixed(1)} s · ${used.length} telemetry-derived inputs. Does not change flight physics.`;const evidence=document.querySelector('#engineeringLiveContext');if(evidence){evidence.hidden=false;evidence.dataset.coupled=String(used.length>0);evidence.textContent=used.length?`MISSION INPUTS: ${used.join(', ')} · ${c.vehicle} · ${c.phase}`:'STUDIO INDIPENDENTE: non applica forze alla missione.'}}download.disabled=false;
  }catch(error){info.textContent='Errore di analisi: '+error.message}
  finally{if(id===runId)run.disabled=false}
 });
 // ASTRA_141_APPLY_WIND_TO_FLIGHT: explicit opt-in, resets mission.
 if(applyWind)applyWind.addEventListener('click',async()=>{
  try{
   const snapshot=await browserApi('/state');
   if(!['aircraft','drone'].includes(snapshot.vehicle)){
    info.textContent='Seleziona prima AEREO oppure DRONE, non SPAZIO.';
    return;
   }
   const f=name=>Number(form.querySelector(`[name="${name}"]`)?.value);
   const speed=f('reference_wind_m_s'), zref=f('reference_height_m');
   const rough=f('roughness_length_m'), degrees=f('direction_toward_deg');
   if(![speed,zref,rough,degrees].every(Number.isFinite)||zref<=rough){
    info.textContent='Parametri di vento non validi.';return;
   }
   if(!confirm('Questa operazione riavvia la missione '+snapshot.vehicle+' con il vento attivo. Continuare?'))return;
   const radians=degrees*Math.PI/180;
   const config={reference_wind_ned_m_s:[speed*Math.cos(radians),speed*Math.sin(radians),0],
                 reference_height_m:zref,roughness_length_m:rough,boundary_layer_height_m:100};
   const status=await browserApi('/reset',{vehicle:snapshot.vehicle,scenario:'mission',
                                             model_id:snapshot.model_id,surface_layer_wind:config});
   info.textContent='VENTO APPLICATO ALLA DINAMICA · '+status.environment.wind_profile_model+
                    ' · Premi PLAY nella missione.';
  }catch(error){info.textContent='Attivazione vento: '+error.message}
 });
 // ASTRA_V14_LIVE_BUTTON
 $('#engineeringRunLive')?.addEventListener('click',()=>{livePending=true;run.click()});
 const verifyButton=$('#engineeringVerifyLive'),verifyText=$('#engineeringRequirements'),verifyOutput=$('#engineeringVerificationResult');
 if(verifyButton&&verifyText&&verifyOutput){verifyButton.addEventListener('click',async()=>{
  try{
   const requirements=JSON.parse(verifyText.value);
   verifyButton.disabled=true;verifyOutput.textContent='Verifica telemetria in corso…';
   const result=await browserApi('/requirements/verify',{requirements});
   verifyOutput.textContent=`PASS ${result.passed} · FAIL ${result.failed} · NON VERIFICATI ${result.not_evaluated}\n`+JSON.stringify(result.requirements,null,2);
  }catch(error){verifyOutput.textContent='Errore requisiti: '+error.message}
  finally{verifyButton.disabled=false}
 })}
 download.addEventListener('click',()=>{
  if(!last)return;
  const blob=new Blob([JSON.stringify({...last.result,request:last.request},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`astra-engineering-${last.request.analysis}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
 });
}
