import { browserApi } from "./browser-api.js";
import { parseGlb } from "./vehicle-glb.js?build=260";
import { aircraftPoseMatrix } from "./flight-frames.js?build=260";
import { keyboardAxes, gamepadAxes, pilotStep } from "./pilot-controls.js?build=260";
import { aerospaceDisciplines, disciplineStatuses } from "./disciplines.js?build=260";
import { MissionRecorder, bindMissionDataLab } from "./mission-recorder.js?build=260";
(() => {
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const TEXTURE_BUILD_ID="260";
const formatEnvironmentValue=value=>value===0?"0":Math.abs(value)<.01||Math.abs(value)>=1e5?value.toExponential(2):value.toFixed(3);
const formatPressure=value=>value>=1000?(value/1000).toFixed(2)+" kPa":formatEnvironmentValue(value)+" Pa";
const savedDesign=(()=>{try{const d=JSON.parse(localStorage.getItem("astra-vehicle-design-v1"));if(d&&typeof d.name==="string"){const stages=Array.isArray(d.stages)?d.stages:[{tank_count:d.tank_count,engine_count:d.engine_count}];if(stages.length>=1&&stages.length<=4&&stages.every(x=>Number.isInteger(x.tank_count)&&x.tank_count>=1&&x.tank_count<=3&&Number.isInteger(x.engine_count)&&x.engine_count>=1&&x.engine_count<=8))return{name:d.name,stages}}}catch{}return{name:"ASTRA-LAB M1",stages:[{tank_count:2,engine_count:1}]}})();
const savedModels=(()=>{try{const d=JSON.parse(localStorage.getItem("astra-model-selection-v1"));if(d&&typeof d==="object")return{space:["asteria-capsule","dardo-lifting-body","astra-custom-stack"].includes(d.space)?d.space:"asteria-capsule",aircraft:["aquila-x4","corvo-t2"].includes(d.aircraft)?d.aircraft:"aquila-x4",drone:["falco-q8","merlo-h6"].includes(d.drone)?d.drone:"falco-q8"}}catch{}return{space:"asteria-capsule",aircraft:"aquila-x4",drone:"falco-q8"}})();
const defaultVisualModels={space:"nasa-sls-block1",aircraft:"innerscene-propeller-aircraft",drone:"innerscene-quadcopter"};
const savedVisualModels=(()=>{try{const d=JSON.parse(localStorage.getItem("astra-visual-model-selection-v1"));if(d&&typeof d==="object")return{space:typeof d.space==="string"?d.space:defaultVisualModels.space,aircraft:typeof d.aircraft==="string"?d.aircraft:defaultVisualModels.aircraft,drone:typeof d.drone==="string"?d.drone:defaultVisualModels.drone}}catch{}return{...defaultVisualModels}})();
// Presentation coordinates use a compressed, consistent view transform; physics remains in SI/ECI.
const EARTH_RADIUS=6378137,EARTH_RENDER_RADIUS=12,EARTH_RENDER_SCALE=EARTH_RENDER_RADIUS/EARTH_RADIUS,SPACE_LAUNCH_CAMERA_RANGE=2.4*115.8*EARTH_RENDER_SCALE,AIR_RUNWAY_HALF_THICKNESS=.008,AIR_RUNWAY_TOP=2*AIR_RUNWAY_HALF_THICKNESS,EARTH_ROTATION_RATE=7.292115e-5,LAUNCH_SITE_LATITUDE=28.5721*Math.PI/180,LAUNCH_SITE_LONGITUDE=-80.648*Math.PI/180,AU=149597870700;const windPresets={calm:[0,0,0],headwind:[-8,0,0],tailwind:[8,0,0],crosswind:[0,6,0]};const windShearProfile=[{altitude_m:0,velocity_ned_m_s:[0,0,0]},{altitude_m:100,velocity_ned_m_s:[0,1,0]},{altitude_m:1000,velocity_ned_m_s:[0,4,0]},{altitude_m:3000,velocity_ned_m_s:[0,8,0]},{altitude_m:8000,velocity_ned_m_s:[0,12,0]}];function windProfilePayload(){return state.windPreset==="shear"?windShearProfile.map(knot=>({altitude_m:knot.altitude_m,velocity_ned_m_s:[...knot.velocity_ned_m_s]})):null}const savedDryden=(()=>{try{const d=JSON.parse(localStorage.getItem("astra-dryden-environment-v1"));const validVector=v=>Array.isArray(v)&&v.length===3&&v.every(x=>Number.isFinite(x));if(d&&["none","light","moderate","severe","custom"].includes(d.preset)&&Number.isInteger(d.seed)&&d.seed>=0&&d.seed<=4294967295&&validVector(d.sigma)&&validVector(d.lengths))return{preset:d.preset,seed:d.seed,sigma:d.sigma,lengths:d.lengths}}catch{}return{preset:"none",seed:20261023,sigma:[1.5,1.0,0.8],lengths:[200,200,60]}})();const state={kind:"space",missionProfile:"mission",pendingDesignProfile:null,requestEpoch:0,resetPending:false,launchPending:false,running:false,seconds:0,speed:1,roll:0,pitch:0,yaw:0,attitudeTarget:[0,0,0],thrust:0,brakes:0,fuel:100,az:2.66,el:.19,zoom:8.2,spaceZoom:SPACE_LAUNCH_CAMERA_RANGE,spaceCameraManual:false,visualPropellerPhase:0,visualPropellerRpm:0,visualPropellerModelId:null,visualAnimationTime:null,drag:null,events:0,engine:null,stageEventCount:0,pending:false,lastAdvance:0,mode:"auto",modelId:savedModels.space,catalog:null,vehicleParts:null,customDesign:savedDesign,modelPreferences:savedModels,userVehicles:{space:null,aircraft:null,drone:null},visualCatalog:null,visualModelPreferences:savedVisualModels,visualModelId:savedVisualModels.space,catalogVehicles:{},catalogVehicleLoads:{},visualModelError:null,visualModelErrorMessage:null,modelOrientations:{space:"auto",aircraft:"auto",drone:"auto"},windPreset:"calm",drydenPreset:savedDryden.preset,drydenSeed:savedDryden.seed,drydenSigma:[...savedDryden.sigma],drydenLengths:[...savedDryden.lengths],product:"sim",careerTrack:"pilot",careerActive:false,careerAwarded:false,careerObservations:[],careerPhases:new Set(),solarView:false,celestialCamera:null,celestial:null,celestialDate:null,selectedBodyId:"moon",transferPlan:null,transferProgress:0,transferPlaying:false,transferPosition:null,transferVelocity:null,transferPositionPending:false,transferPositionToken:0,launchSiteGeo:{latitude:LAUNCH_SITE_LATITUDE,longitude:LAUNCH_SITE_LONGITUDE}};
const AIRFIELD_RUNWAY_LENGTH_M=3000,AIRFIELD_RUNWAY_WIDTH_M=30,AIRFIELD_RUNWAY_START_OFFSET_M=150,AIRFIELD_RUNWAY_LENGTH_WORLD=AIRFIELD_RUNWAY_LENGTH_M*.1,AIRFIELD_RUNWAY_WIDTH_WORLD=AIRFIELD_RUNWAY_WIDTH_M*.1,AIRFIELD_RUNWAY_START_WORLD=-AIRFIELD_RUNWAY_START_OFFSET_M*.1,TERRAIN_HALF_X_WORLD=320,TERRAIN_HALF_Z_WORLD=210,TERRAIN_TILE_STEP_X=TERRAIN_HALF_X_WORLD*2,TERRAIN_TILE_STEP_Z=TERRAIN_HALF_Z_WORLD*2;
const missionRecorder=new MissionRecorder();
const missionRecorderUi=bindMissionDataLab(missionRecorder,{
 runCampaign:payload=>api("/robustness",payload),
 runConvergence:payload=>api("/convergence",payload),
 injectFault:payload=>api("/fault",payload),
 clearFaults:()=>api("/fault/clear",{}),
 faultConfig:()=>({vehicle:state.kind,scenario:state.engine?.scenario||state.missionProfile,rotorCount:state.engine?.vehicle_parameters?.rotors}),
 onFaultState:data=>consumeEngine(data),
 campaignConfig:()=>{
  const engine=state.engine,design=engine?.vehicle_design;
  return {vehicle:state.kind,scenario:state.kind==="space"?(engine?.scenario||state.missionProfile):"mission",
   model_id:state.modelId==="astra-custom-stack"?null:state.modelId,
   custom_design:design?{name:design.name,stages:design.stages.map(stage=>({tank_count:stage.tank_count,engine_count:stage.engine_count}))}:null,
   baseline_wind_ned_m_s:state.kind==="space"||state.windPreset==="shear"?[0,0,0]:(windPresets[state.windPreset]||[0,0,0]),baseline_wind_profile_ned_m_s:state.kind==="space"?null:windProfilePayload(),baseline_turbulence:turbulencePayload()};
 }
});
let spaceSkyBlend=0;
const rankLadders={pilot:[[0,"Cadetto"],[300,"Allievo pilota"],[900,"Pilota ASTRA"],[1800,"Comandante di volo"],[3200,"Asso orbitale"]],engineer:[[0,"Cadetto tecnico"],[300,"Progettista junior"],[900,"Ingegnere di volo"],[1800,"Ingegnere capo"],[3200,"Architetto di missione"]],scientist:[[0,"Cadetto scientifico"],[300,"Ricercatore junior"],[900,"Analista di missione"],[1800,"Scienziato principale"],[3200,"Pioniere scientifico"]]};
const careerLabels={pilot:"PILOTA",engineer:"INGEGNERE",scientist:"SCIENZIATO"};
const careerCopy={pilot:"Vola la missione, raggiungi la quota obiettivo e rientra con un contatto morbido.",engineer:"Valuta carichi e margini del veicolo: completa il profilo entro l’inviluppo dinamico.",scientist:"Raccogli osservazioni in fasi diverse e usa la telemetria per documentare il volo."};
const careerGoals={space:{altitude:80000,qbar:65000,touchdown:12},aircraft:{altitude:450,qbar:8000,touchdown:75},drone:{altitude:25,qbar:500,touchdown:2.5}};
const campaign=(()=>{try{return JSON.parse(localStorage.getItem("astra-career-v1"))||{xp:{pilot:0,engineer:0,scientist:0},missions:{pilot:0,engineer:0,scientist:0},observations:[]}}catch{return{xp:{pilot:0,engineer:0,scientist:0},missions:{pilot:0,engineer:0,scientist:0},observations:[]}}})();
for(const track of Object.keys(rankLadders)){campaign.xp[track]??=0;campaign.missions[track]??=0}campaign.observations??=[];
const info={
space:["Rientro suborbitale","LANCIO · COAST · RIENTRO · RECUPERO","ECI · INERZIALE","LANCIO E RECUPERO","ASTERIA","CAPSULE","ECI · J₂ · COESA76 DRAG · RK4","LANCIO · VOLO SUBORBITALE","ALTITUDE","0.0","km","MSL","INERTIAL SPEED","0.465","km/s","ECI","PROPELLANT",100,"%","ASCENT"],
aircraft:["Circuito di volo","DECOLLO · CIRCUITO · AVVICINAMENTO · ATTERRAGGIO","NED · LOCALE","VOLO CON ATTERRAGGIO","AQUILA","X-4","6-DOF · COESA76 · RUNWAY CONTACT","PISTA · MISSIONE AUTOMATICA","ALTITUDE MSL","0.0","km","MSL","TRUE AIRSPEED","0.0","m/s","TAS","FUEL REMAINING",68,"%","TAKEOFF"],
drone:["Missione di ispezione UAV","DECOLLO VTOL · ISPEZIONE · ATTERRAGGIO","NED · BODY","ISPEZIONE CON RIENTRO","FALCO","Q8","6-DOF · QUADROTOR · COESA76","PIAZZOLA · VOLO VTOL","ALTITUDE AGL","0","m","AGL","GROUND SPEED","0.0","m/s","GROUND","BATTERY",74,"%","TAKEOFF"]
};
const defaultModels={space:"asteria-capsule",aircraft:"aquila-x4",drone:"falco-q8"};
const codeExamples={
python:{file:"controller.py",label:"PYTHON CLIENT · REST JSON",note:"Controllo esterno con stime Kalman. Ogni comando rinnova il watchdog da 1 s simulato; usa sim.heartbeat() per rinnovarlo senza cambiare setpoint. Se il link scade, ASTRA riprende una risposta automatica specifica per veicolo. Esempio UAV: examples/python_uav_autopilot.py.",code:[
"from astra.client import AstraClient",
"sim = AstraClient()",
"state = sim.reset(\"drone\", model_id=\"falco-q8\")",
"sim.command(mode=\"python\", throttle_pct=0)",
"state = sim.launch()",
"vnav = state[\"navigation_estimate\"]",
"hnav = state[\"horizontal_navigation_estimate\"]",
"state = sim.command(mode=\"python\", throttle_pct=52,",
"    roll_deg=0, pitch_deg=0)",
"state = sim.step(0.05)",
"print(vnav[\"altitude_m\"], hnav[\"position_ned_m\"])"
].join("\n")},
matlab:{file:"controller.m",label:"MATLAB CLIENT · REST JSON",note:"Aggiungi la cartella matlab al path. Usa mode='python' per il controllo programmato e sim.heartbeat() per rinnovare il link senza modificare i setpoint. AstraClient.m usa webread/webwrite.",code:[
"addpath(\"matlab\")",
"sim = astra.AstraClient();",
"state = sim.reset(\"aircraft\", \"aquila-x4\");",
"state = sim.launch();",
"sim.command(\"mode\", \"python\", ...",
"    \"throttle_pct\", 35, \"pitch_deg\", 2);",
"state = sim.step(0.05);",
"disp([state.altitude_m, state.speed_m_s])"
].join("\n")},
simulink:{file:"AstraSimulinkSystem.m",label:"SIMULINK · MATLAB SYSTEM BLOCK",note:"Aggiungi matlab al path; usa un blocco MATLAB System in simulazione normale. Il blocco aggiorna il watchdog a ogni passo programmato. Ingressi: throttle %, pitch °, roll °.",code:[
"addpath(\"matlab\")",
"% Simulink Library Browser > User-Defined Functions",
"% Inserisci il blocco MATLAB System.",
"% System object: AstraSimulinkSystem",
"% Ingressi: throttle_pct, pitch_deg, roll_deg.",
"% Reset e lancio avvengono al setup del blocco."
].join("\n")}
};
const fallbackModels={space:{"asteria-capsule":{name:"Asteria · capsula recuperabile",summary:"Lancio suborbitale e recupero con paracadute."},"dardo-lifting-body":{name:"Dardo · corpo portante",summary:"Capsula con ali di portanza e recupero."},"astra-leo-servicer":{name:"ASTRA · veicolo di servizio LEO",summary:"Rendezvous LEO · massa secca 400 kg · 80 kg ACS · carica iniziale 65,6 kg · RCS 24 N · Isp 220 s."}},aircraft:{"aquila-x4":{name:"Aquila X-4 · bimotore",summary:"Aereo di riferimento per circuito e atterraggio."},"corvo-t2":{name:"Corvo T-2 · addestratore",summary:"Aereo leggero, più lento e agile."}},drone:{"falco-q8":{name:"Falco Q8 · quadricottero",summary:"Quattro rotori, per ispezioni ravvicinate."},"merlo-h6":{name:"Merlo H6 · esacottero",summary:"Sei rotori e maggiore spinta."}}};
const lessons={space:{READY:["La capsula è sulla rampa","Premi AVVIA MISSIONE per lanciarla. Seguirà una salita nello spazio e poi tornerà a terra.","Il motore espelle gas verso il basso: la spinta risultante accelera il razzo verso l’alto."],ASCENT:["Il razzo sta salendo","Il motore consuma propellente per aumentare la velocità. Guarda quota e riserva mentre l’assetto cambia.","La spinta dipende dal motore e dalla massa. Quando il propellente finisce, il razzo continua per inerzia."],COAST:["La capsula continua per inerzia","Il motore è spento. La gravità terrestre curva la traiettoria e la capsula raggiunge il punto più alto.","Nello spazio non serve una spinta continua per continuare a muoversi: la velocità cambia soprattutto per effetto della gravità." ],COAST_TO_APOGEE:["Il razzo sale per inerzia","Il motore è spento. La gravità porta il veicolo verso l’apogeo mentre il computer verifica la traiettoria prevista.","L’apogeo è il punto più alto dell’orbita; la spinta successiva alza il perigeo per evitare il rientro immediato."],CIRCULARIZE:["Il motore regola l’orbita","Un impulso prograde vicino all’apogeo rende più circolare l’orbita. Segui eccentricità, perigeo e apogeo nei dati tecnici.","Ridurre l’eccentricità rende simili il punto più alto e quello più basso dell’orbita."],ORBIT_COAST:["La capsula è in orbita LEO","I motori sono spenti. La capsula completa un giro a circa 300 km mentre ASTRA controlla il tempo orbitale.","In orbita la gravità continua a curvare la traiettoria; la velocità laterale fa sì che il veicolo continui a mancare la Terra."],DEORBIT_ALIGN:["Assetto retrogrado","I propulsori RCS orientano il veicolo contro il moto orbitale prima dell’accensione del motore.","La manovra di deorbita deve iniziare quando la spinta è allineata alla direzione retrograda; così la velocità orbitale diminuisce nel verso corretto."],DEORBIT_BURN:["Manovra di deorbita","Il motore spinge brevemente in direzione retrograda per abbassare il perigeo sotto l’atmosfera.","Ridurre la velocità orbitale sul lato opposto all’ingresso crea una traiettoria che incontra l’atmosfera al perigeo."],DEORBIT_COAST:["La capsula torna verso l’atmosfera","La manovra è terminata. La gravità porta il veicolo verso l’interfaccia a 120 km, poi lo scudo e i paracadute lo rallentano.","Il punto più basso previsto dopo la manovra determina dove la capsula incontra l’atmosfera."],ABORTED:["Missione interrotta","ASTRA ha fermato la sequenza perché il veicolo non aveva riserva sufficiente per completare la manovra successiva.","Le riserve di propellente sono un vincolo di missione: Δv ideale da solo non garantisce l’inserzione."],REENTRY:["La capsula sta rientrando","Scendendo, incontra aria sempre più densa che la rallenta. La pressione dinamica è mostrata nei dati tecnici.","Anche se l’aria è rarefatta in alto, a velocità elevata può esercitare una forza molto grande."],AEROSHELL:["Si apre lo scudo frenante","Lo scudo aumenta la resistenza dell’aria e riduce la velocità prima di aprire i paracadute.","Una superficie più grande sposta più aria. Il modello limita la forza prevista per non aprire il paracadute a carichi eccessivi."],DROGUE:["Si apre il paracadute guida","Il paracadute più piccolo stabilizza la capsula e la rallenta prima dell’apertura principale.","Aprire il paracadute in più fasi riduce lo strappo sulla struttura."],PARACHUTE:["La capsula scende sotto il paracadute","La grande vela aumenta la resistenza dell’aria e porta la velocità verso un valore sicuro.","La forza di resistenza cresce con la densità dell’aria e con il quadrato della velocità."],LANDED:["Missione conclusa","La capsula è tornata a terra. Puoi esportare i dati o scegliere un altro modello.","Confronta velocità, quota e pressione dinamica nelle diverse fasi."],CRASHED:["Atterraggio non sicuro","La capsula ha toccato il suolo troppo velocemente. Puoi riavviare la missione o confrontare i dati del rientro.","Il profilo usa modelli semplificati e serve a imparare; non è un progetto per costruire o pilotare un razzo reale."]},aircraft:{READY:["L’aereo è pronto in pista","Premi AVVIA MISSIONE: accelererà, salirà, farà un circuito e tornerà per l’atterraggio.","Le ali producono portanza quando l’aria scorre attorno a loro."],TAKEOFF:["Decollo","I motori accelerano l’aereo. Quando le ali generano abbastanza portanza, le ruote si staccano dalla pista.","La portanza cresce con la velocità dell’aria, la superficie alare e l’angolo delle ali rispetto al flusso."],CLIMB:["Salita","L’autopilota mantiene la salita e stabilizza l’assetto.","La spinta porta avanti l’aereo; le ali trasformano parte del flusso d’aria in una forza verso l’alto."],CRUISE:["Volo in circuito","L’aereo vola a quota quasi costante e segue il profilo della missione.","In volo stabile, portanza e peso si bilanciano, così la quota cambia poco."],APPROACH:["Avvicinamento alla pista","La velocità diminuisce e la quota scende verso la pista.","L’aereo deve arrivare abbastanza lento da fermarsi, ma abbastanza veloce da mantenere la portanza."],LANDING:["Atterraggio","Le ruote toccano la pista e l’aereo comincia a rallentare.","Il pilota usa motore, assetto e freni per dissipare l’energia del movimento."],ROLLOUT:["L’aereo sta frenando","Resta sulla pista mentre la velocità diminuisce.","L’attrito delle ruote e la resistenza dell’aria trasformano energia di movimento in calore."],LANDED:["Missione conclusa","L’aereo è fermo sulla pista. Puoi scegliere un altro modello o rivedere i dati.","Confronta la velocità di decollo con quella al contatto." ]},drone:{READY:["Il drone è sulla piazzola","Premi AVVIA MISSIONE: salirà in verticale, farà un’ispezione e tornerà al punto di partenza.","I rotori spingono aria verso il basso. La reazione sostiene il drone."],TAKEOFF:["Decollo verticale","I rotori aumentano la spinta e il drone sale mantenendosi in equilibrio.","Per restare fermo in aria, la spinta totale deve bilanciare il peso."],INSPECT:["Ispezione in corso","Il filtro IMU + GNSS mantiene la posizione N/E mentre il drone percorre un piccolo anello di ispezione.","La guida compensa vento e resistenza; il rientro aspetta la piazzola prima di iniziare la discesa."],RETURN:["Rientro alla piazzola","Il drone riduce la quota per preparare l’atterraggio.","La discesa controllata evita di spegnere i rotori troppo presto."],LANDING:["Atterraggio verticale","Il drone scende piano e riduce la spinta quando è vicino al suolo.","La spinta diminuisce gradualmente per evitare un impatto brusco."],LANDED:["Missione conclusa","Il drone è tornato a terra. Scegli un altro modello o avvia una nuova missione.","Confronta altezza e batteria all’inizio e alla fine." ]}};
lessons.space.RENDEZVOUS=["Avvicinamento alla stazione","La guida usa il modello Clohessy–Wiltshire nel riferimento RTN: confronta posizione e velocità relative con un punto di mantenimento a 20 m.","Il controllore PD comanda piccoli impulsi RCS e li limita alla spinta disponibile. La velocità relativa, non quella orbitale, deve quasi annullarsi all’arrivo."];lessons.space.STATION_KEEPING=["Punto di mantenimento raggiunto","La capsula resta a circa 20 m dalla stazione; il controllore corregge lentamente gli errori relativi.","Il modello usa lo stato ECI come verità e una dinamica relativa linearizzata. Non simula sensori rumorosi, attracco o assetto del corpo."];lessons.aircraft.EMERGENCY_GLIDE=["Planata di emergenza","L’FDIR ha isolato una perdita di spinta. Il controllo mantiene la velocità di massima efficienza aerodinamica e la traccia stimata da GNSS mentre prepara l’avvicinamento.","La velocità di planata deriva dalla polare CL/CD e dalla densità locale. La scena non contiene terreno o scelta di piste: il recupero usa una superficie piana di riferimento."];
const host=$("#scene"),canvas=document.createElement("canvas");host.appendChild(canvas);
function detectDeviceProfile(){const cores=navigator.hardwareConcurrency||4, memory=navigator.deviceMemory||4, touch=matchMedia("(pointer: coarse)").matches, small=innerWidth<800;let tier="high";if(cores<=4||memory<=3||(touch&&small&&memory<=4))tier="low";else if(cores<=8||memory<=8||touch)tier="balanced";return{tier,cores,memory,touch,pixelBudget:tier==="low"?1_300_000:tier==="balanced"?3_200_000:8_294_400,dprCap:tier==="low"?1:tier==="balanced"?1.5:2,targetFps:tier==="low"?30:tier==="balanced"?45:60,apiIntervalMs:tier==="low"?100:tier==="balanced"?80:50,textureMax:tier==="low"?1024:tier==="balanced"?2048:4096,geometry:tier==="low"?0.48:tier==="balanced"?0.72:1,stars:tier==="low"?120:tier==="balanced"?240:420}}
const deviceProfile=detectDeviceProfile();let renderScale=1,ctx2d=null;
const gl=canvas.getContext("webgl2",{antialias:deviceProfile.tier==="high",alpha:false,powerPreference:deviceProfile.tier==="high"?"high-performance":"low-power"});
if(!gl)ctx2d=canvas.getContext("2d",{alpha:false,desynchronized:true});
 let p,sp,skyProgram,globe,launchSurfaceGeo,launchSurfaceNearGeo,launchSurfaceFallbackGeo,cube,terrainGeo,runwayMarkingsGeo,dishMesh,panelMesh,cylinderMesh,earthTex,launchGroundTex,launchGroundNearTex,skyTex,atmosphereSkyTex,solarTex,foilTex,terrainTex,asphaltTex,shadowTex,stars,starCount,cams,view,projection,sceneFovY=1.12,parachuteLineMesh=null,launchGroundTextureEpoch=0;const celestialView=new Float32Array(16),lineCache=new Map(),terrainTextureCache=Object.create(null);let terrainTileX=0,terrainTileZ=0,terrainDetail=56,terrainOuterTiles=[];
const pad=n=>String(n).padStart(2,"0"),tc=s=>"T+ "+pad(Math.floor(s/3600))+":"+pad(Math.floor(s%3600/60))+":"+pad(Math.floor(s%60));
function toast(s){const t=$("#toast");t.textContent=s;t.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),2200)}
function mat(){return new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])}
function mul(a,b){const o=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)o[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3];return o}
function T(x,y,z){const m=mat();m[12]=x;m[13]=y;m[14]=z;return m}
function S(x,y,z){const m=mat();m[0]=x;m[5]=y;m[10]=z;return m}
function RY(a){const m=mat(),c=Math.cos(a),s=Math.sin(a);m[0]=c;m[2]=-s;m[8]=s;m[10]=c;return m}
function RX(a){const m=mat(),c=Math.cos(a),s=Math.sin(a);m[5]=c;m[6]=s;m[9]=-s;m[10]=c;return m}
// Keep the panorama in a fixed celestial frame; camera motion only changes the view.
const GALACTIC_FRAME=mul(RY(.35),RX(.30)),SKY_SCALE=S(95,95,95);
function RZ(a){const m=mat(),c=Math.cos(a),s=Math.sin(a);m[0]=c;m[1]=s;m[4]=-s;m[5]=c;return m}
function norm(v){const l=Math.hypot(...v)||1;return v.map(x=>x/l)}
function cross(a,b){return[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]}
function look(eye,at,upHint=[0,1,0]){const z=norm(eye.map((v,i)=>v-at[i]));let x=cross(upHint,z);if(Math.hypot(...x)<1e-5)x=cross([0,0,1],z);x=norm(x);const y=cross(z,x),m=mat();[m[0],m[1],m[2],m[4],m[5],m[6],m[8],m[9],m[10]]=[x[0],y[0],z[0],x[1],y[1],z[1],x[2],y[2],z[2]];m[12]=-x.reduce((s,v,i)=>s+v*eye[i],0);m[13]=-y.reduce((s,v,i)=>s+v*eye[i],0);m[14]=-z.reduce((s,v,i)=>s+v*eye[i],0);return m}
function persp(f,a,n,far){const t=1/Math.tan(f/2),m=new Float32Array(16);m[0]=t/a;m[5]=t;m[10]=(far+n)/(n-far);m[11]=-1;m[14]=2*far*n/(n-far);return m}
function makeShader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
function makeProgram(v,f){const x=gl.createProgram();gl.attachShader(x,makeShader(gl.VERTEX_SHADER,v));gl.attachShader(x,makeShader(gl.FRAGMENT_SHADER,f));gl.linkProgram(x);if(!gl.getProgramParameter(x,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(x));return x}
function geo(pos,nor,uv,ind,mode){const o={vao:gl.createVertexArray(),mode:mode||gl.TRIANGLES,count:ind.length,buffers:[]};gl.bindVertexArray(o.vao);[[0,pos,3],[1,nor,3],[2,uv,2]].forEach(a=>{const b=gl.createBuffer();o.buffers.push(b);gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(a[1]),gl.STATIC_DRAW);gl.enableVertexAttribArray(a[0]);gl.vertexAttribPointer(a[0],a[2],gl.FLOAT,false,0,0)});o.ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,o.ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint32Array(ind),gl.STATIC_DRAW);gl.bindVertexArray(null);return o}
function disposeGeometry(g){if(!g)return;gl.deleteVertexArray(g.vao);gl.deleteBuffer(g.ib);for(const b of g.buffers||[])gl.deleteBuffer(b)}
function sphere(rows,cols){const a=[],n=[],u=[],ix=[];for(let y=0;y<=rows;y++){const v=y/rows,ph=v*Math.PI;for(let x=0;x<=cols;x++){const q=x/cols*2*Math.PI,X=-Math.cos(q)*Math.sin(ph),Y=Math.cos(ph),Z=Math.sin(q)*Math.sin(ph);a.push(X,Y,Z);n.push(X,Y,Z);u.push(1-x/cols,1-v)}}for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){let k=y*(cols+1)+x,b=k+cols+1;ix.push(k,b,k+1,b,b+1,k+1)}return geo(a,n,u,ix)}
function launchSurfacePatch(rows=256,cols=256,halfDistance_m=60000,centerLat=state.launchSiteGeo.latitude,centerLon=state.launchSiteGeo.longitude,localUV=false,surfaceOffset_m=.30){const p=[],n=[],uv=[],ix=[],halfLat=halfDistance_m/EARTH_RADIUS,raisedRadius=1+surfaceOffset_m/EARTH_RADIUS;for(let j=0;j<=rows;j++){const north=-1+2*j/rows,lat=centerLat+north*halfLat;for(let i=0;i<=cols;i++){const east=-1+2*i/cols,lon=centerLon+east*halfLat/Math.max(.1,Math.cos(lat)),cl=Math.cos(lat),x=cl*Math.cos(lon)*raisedRadius,y=Math.sin(lat)*raisedRadius,z=cl*Math.sin(lon)*raisedRadius;p.push(x,y,z);n.push(x,y,z);uv.push(localUV?i/cols:.5+lon/(2*Math.PI),localUV?j/rows:.5+lat/Math.PI)}}for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const a=j*(cols+1)+i,b=a+cols+1;ix.push(a,b,a+1,b,b+1,a+1)}return geo(p,n,uv,ix)}
function setLaunchSiteReference(position){if(!Array.isArray(position)||position.length!==3||!position.every(Number.isFinite))return;const radius=Math.hypot(...position);if(radius<EARTH_RADIUS-1000)return;const latitude=Math.asin(Math.max(-1,Math.min(1,position[2]/radius))),longitude=Math.atan2(position[1],position[0]),previous=state.launchSiteGeo,moved=Math.abs(latitude-previous.latitude)>1e-6||Math.abs(Math.atan2(Math.sin(longitude-previous.longitude),Math.cos(longitude-previous.longitude)))>1e-6;state.launchSiteGeo={latitude,longitude};if(gl){const oldLocal=launchSurfaceGeo,oldNear=launchSurfaceNearGeo,oldFallback=launchSurfaceFallbackGeo;launchSurfaceGeo=launchSurfacePatch(256,256,60000,latitude,longitude,true,.30);launchSurfaceNearGeo=launchSurfacePatch(256,256,3000,latitude,longitude,true,.32);launchSurfaceFallbackGeo=launchSurfacePatch(256,256,60000,latitude,longitude,false,.30);disposeGeometry(oldLocal);disposeGeometry(oldNear);disposeGeometry(oldFallback);if(moved)launchGroundTexture(latitude,longitude)}}
function boxGeo(){const p=[],n=[],u=[],ix=[],faces=[[[0,0,1],[[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]],[[0,0,-1],[[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1]]],[[0,1,0],[[-1,1,1],[1,1,1],[1,1,-1],[-1,1,-1]]],[[0,-1,0],[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1]]],[[1,0,0],[[1,-1,1],[1,-1,-1],[1,1,-1],[1,1,1]]],[[-1,0,0],[[-1,-1,-1],[-1,-1,1],[-1,1,1],[-1,1,-1]]]];faces.forEach(f=>{let k=p.length/3;f[1].forEach(v=>{p.push(...v);n.push(...f[0])});u.push(0,0,1,0,1,1,0,1);ix.push(k,k+1,k+2,k,k+2,k+3)});return geo(p,n,u,ix)}
function aircraftTailFin(){const p=[-5.45,.04,-.055,-4.12,.04,-.055,-5.15,1.35,-.055,-5.45,.04,.055,-5.15,1.35,.055,-4.12,.04,.055],n=Array.from({length:6},(_,i)=>[0,0,i<3?1:-1]).flat(),u=[0,0,1,0,.5,1,0,0,.5,1,1,0],ix=[0,1,2,3,4,5];return geo(p,n,u,ix)}
function terrainHeight(x,z){
 // A coastal airport is nearly level. Keep drainage swales subtle and move
 // the low scrub ridges to the distant perimeter instead of blocking the runway.
 const radius=Math.hypot(x,z),fade=Math.max(0,Math.min(1,(radius-10)/22));
 const swales=.018*Math.sin(x*.075+Math.sin(z*.045)*.7)*Math.cos(z*.061-x*.021)
  +.009*Math.sin((x+z)*.16)*Math.cos((x-z)*.105);
 const wetlandBank=.075*Math.exp(-.5*((z+39+1.5*Math.sin(x*.025)) / 5.5)**2)
  +.055*Math.exp(-.5*((z-44+1.2*Math.sin(x*.021+.8)) / 7.0)**2);
 return -2.07+swales+fade*wetlandBank;
}
function terrain(detail=56,originX=0,originZ=0){const p=[],n=[],u=[],ix=[],nx=detail,nz=Math.max(24,Math.round(detail*.72)),e=.15,minX=-TERRAIN_HALF_X_WORLD,maxX=TERRAIN_HALF_X_WORLD,minZ=-TERRAIN_HALF_Z_WORLD,maxZ=TERRAIN_HALF_Z_WORLD;for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){const x=minX+i*((maxX-minX)/nx),z=minZ+j*((maxZ-minZ)/nz),worldX=originX+x,worldZ=originZ+z,h=terrainHeight(worldX,worldZ),normal=norm([(terrainHeight(worldX-e,worldZ)-terrainHeight(worldX+e,worldZ))/(2*e),1,(terrainHeight(worldX,worldZ-e)-terrainHeight(worldX,worldZ+e))/(2*e)]);p.push(x,h,z);n.push(...normal);u.push(i/nx,j/nz)}for(let z=0;z<nz;z++)for(let x=0;x<nx;x++){const a=z*(nx+1)+x,b=a+nx+1;ix.push(a,a+1,b,b,a+1,b+1)}return geo(p,n,u,ix)}
function updateTerrainTile(centerX,centerZ){
 const nextX=Math.round(centerX/TERRAIN_TILE_STEP_X)*TERRAIN_TILE_STEP_X,nextZ=Math.round(centerZ/TERRAIN_TILE_STEP_Z)*TERRAIN_TILE_STEP_Z;
 if(nextX===terrainTileX&&nextZ===terrainTileZ&&terrainOuterTiles.length)return;
 const previous=terrainGeo,previousOuter=terrainOuterTiles;
 terrainGeo=terrain(terrainDetail,nextX,nextZ);
 // Eight lower-LOD real ground chunks with continuous terrainHeight at shared edges.
 terrainOuterTiles=[];
 for(let dz=-1;dz<=1;dz++)for(let dx=-1;dx<=1;dx++){
  if(!dx&&!dz)continue;
  const x=nextX+dx*TERRAIN_TILE_STEP_X,z=nextZ+dz*TERRAIN_TILE_STEP_Z;
  terrainOuterTiles.push({x,z,mesh:terrain(Math.max(24,Math.round(terrainDetail*.55)),x,z)});
 }
 terrainTileX=nextX;terrainTileZ=nextZ;
 disposeGeometry(previous);for(const tile of previousOuter)disposeGeometry(tile.mesh);
}
function panelGeo(){const p=[-1,0,-1,1,0,-1,1,0,1,-1,0,1],n=[0,1,0,0,1,0,0,1,0,0,1,0],u=[0,0,1,0,1,1,0,1],ix=[0,2,1,0,3,2];return geo(p,n,u,ix)}
function runwayMarkingsGeometry(){const p=[],n=[],uv=[],ix=[],start=AIRFIELD_RUNWAY_START_WORLD,end=start+AIRFIELD_RUNWAY_LENGTH_WORLD,halfWidth=AIRFIELD_RUNWAY_WIDTH_WORLD*.5,y=AIR_RUNWAY_TOP+.002;function rect(cx,cz,hx,hz){const base=p.length/3;p.push(cx-hx,y,cz-hz,cx+hx,y,cz-hz,cx+hx,y,cz+hz,cx-hx,y,cz+hz);for(let i=0;i<4;i++){n.push(0,1,0);uv.push(0,0)}ix.push(base,base+2,base+1,base,base+3,base+2)}rect(start+AIRFIELD_RUNWAY_LENGTH_WORLD*.5,-halfWidth+.08,AIRFIELD_RUNWAY_LENGTH_WORLD*.5,.022);rect(start+AIRFIELD_RUNWAY_LENGTH_WORLD*.5,halfWidth-.08,AIRFIELD_RUNWAY_LENGTH_WORLD*.5,.022);for(const x of [start+5,end-5])for(let i=-6;i<=6;i++)rect(x,i*.22,.7,.085);for(let x=start+8;x<=end-8;x+=5)rect(x,0,1.4,.045);for(const x of [start+45,end-45])for(const z of [-.55,.55])rect(x,z,2,.09);return geo(p,n,uv,ix)}
function drawDronePad(){solid(0,AIR_RUNWAY_HALF_THICKNESS/2,0,.58,AIR_RUNWAY_HALF_THICKNESS/2,.58,[.27,.31,.32],0);for(const x of [-.2,.2])solid(x,AIR_RUNWAY_TOP+.003,0,.025,.002,.30,[.88,.88,.78],0);solid(0,AIR_RUNWAY_TOP+.003,0,.22,.002,.025,[.88,.88,.78],0);for(const x of [-.49,.49])for(const z of [-.49,.49])solid(x,.03,z,.018,.006,.018,[.25,.88,.76],0)}
function cylinderGeo(){const p=[],n=[],u=[],ix=[],seg=24;for(let z=0;z<2;z++)for(let i=0;i<=seg;i++){const a=i/seg*Math.PI*2,x=Math.cos(a),y=Math.sin(a);p.push(x,y,z?1:-1);n.push(x,y,0);u.push(i/seg,z)}for(let i=0;i<seg;i++){const a=i,b=i+seg+1;ix.push(a,a+1,b,a+1,b+1,b)}return geo(p,n,u,ix)}
function dishGeo(){const p=[],n=[],u=[],ix=[],rings=10,seg=32;for(let r=0;r<=rings;r++){const f=r/rings;for(let i=0;i<=seg;i++){const a=i/seg*Math.PI*2,x=f*Math.cos(a),y=f*Math.sin(a),z=.12*f*f;const nn=norm([-0.24*x,-0.24*y,1]);p.push(x,y,z);n.push(...nn);u.push(.5+x*.5,.5+y*.5)}}for(let r=0;r<rings;r++)for(let i=0;i<seg;i++){const a=r*(seg+1)+i,b=a+seg+1;ix.push(a,b,a+1,b,b+1,a+1)}return geo(p,n,u,ix)}
function surfaceTex(kind){const c=document.createElement("canvas");c.width=512;c.height=512;const q=c.getContext("2d");if(kind==="solar"){q.fillStyle="#06162b";q.fillRect(0,0,512,512);const cols=8,rows=6,gap=5,cw=58,ch=79;for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){const px=12+x*(cw+gap),py=12+y*(ch+gap),g=q.createLinearGradient(px,py,px+cw,py+ch);g.addColorStop(0,"#286493");g.addColorStop(.5,"#164873");g.addColorStop(1,"#0b2c52");q.fillStyle=g;q.fillRect(px,py,cw,ch);q.strokeStyle="#b3dcf09b";q.lineWidth=2;q.strokeRect(px+1,py+1,cw-2,ch-2);q.fillStyle="#e5f4ff27";q.fillRect(px+3,py+3,cw-6,2)}q.strokeStyle="#8fb4cb";q.lineWidth=3;q.strokeRect(4,4,504,504)}else{const g=q.createLinearGradient(0,0,512,0);g.addColorStop(0,"#8f7749");g.addColorStop(.18,"#d1b77d");g.addColorStop(.35,"#a48c5c");g.addColorStop(.58,"#d6c18a");g.addColorStop(.78,"#978052");g.addColorStop(1,"#c5ac70");q.fillStyle=g;q.fillRect(0,0,512,512);q.strokeStyle="#f4dfae80";q.lineWidth=2;for(let x=0;x<=512;x+=64){q.beginPath();q.moveTo(x,0);q.lineTo(x,512);q.stroke()}q.strokeStyle="#64503170";for(let y=0;y<=512;y+=64){q.beginPath();q.moveTo(0,y);q.lineTo(512,y);q.stroke()}}const t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);return t}
const bodyTextureCache=new Map();
function bodySurfaceTexture(id){
 if(bodyTextureCache.has(id))return bodyTextureCache.get(id);
 const width=deviceProfile.tier==="high"?256:deviceProfile.tier==="balanced"?192:128,height=width/2;
 const canvas=document.createElement("canvas");canvas.width=width;canvas.height=height;
 const context=canvas.getContext("2d"),image=context.createImageData(width,height);
 const palette={
  mercury:[[55,49,44],[139,123,104],[202,182,151]],venus:[[147,103,55],[205,162,91],[242,215,160]],
  mars:[[67,43,33],[158,79,49],[226,153,102]],moon:[[52,53,57],[128,128,125],[190,185,174]],
  phobos:[[37,35,34],[83,73,66],[135,116,96]],deimos:[[42,39,36],[97,86,75],[151,132,111]],
  jupiter:[[104,60,42],[194,130,82],[232,194,143]],saturn:[[112,93,65],[196,173,126],[231,216,179]],
  uranus:[[53,137,142],[109,198,194],[180,231,220]],neptune:[[31,52,128],[52,94,190],[104,164,232]],
  io:[[102,66,31],[204,156,65],[240,215,133]],europa:[[117,133,142],[194,205,203],[235,230,214]],
  ganymede:[[67,70,70],[126,125,116],[180,164,139]],callisto:[[40,42,44],[91,90,86],[144,136,122]],
  mimas:[[79,82,86],[159,164,168],[225,228,228]],enceladus:[[125,151,167],[202,218,226],[248,251,252]],
  tethys:[[85,94,101],[157,169,178],[222,226,226]],dione:[[70,78,85],[148,157,163],[212,216,214]],
  rhea:[[78,84,89],[152,159,161],[222,221,216]],titan:[[109,72,35],[183,124,53],[224,181,106]],
  iapetus:[[34,32,30],[109,103,92],[203,196,178]],miranda:[[55,71,78],[124,149,154],[207,214,212]],
  ariel:[[93,111,118],[168,188,190],[224,228,222]],umbriel:[[43,48,57],[103,111,121],[178,179,173]],
  titania:[[72,86,93],[145,158,162],[214,218,215]],oberon:[[54,64,75],[126,136,144],[198,203,202]],
  triton:[[93,103,119],[173,187,200],[225,215,207]]
 };
 const colors=palette[id]||palette.moon,gas=["jupiter","saturn","uranus","neptune"].includes(id);
 let seed=2166136261;for(const ch of id)seed=Math.imul(seed^ch.charCodeAt(0),16777619);seed>>>=0;
 const hash=(x,y)=>{let h=Math.imul((x+seed)|0,0x45d9f3b);h=Math.imul(h^((y+seed*3)|0),0x45d9f3b);return((h^h>>>16)>>>0)/4294967295;};
 const smooth=x=>x*x*(3-2*x),mix=(a,b,t)=>a+(b-a)*t;
 const noise=(u,v,nx,ny)=>{const x=u*nx,y=v*ny,x0=Math.floor(x),y0=Math.floor(y),tx=smooth(x-x0),ty=smooth(y-y0),a=hash((x0%nx+nx)%nx,(y0%ny+ny)%ny),b=hash(((x0+1)%nx+nx)%nx,(y0%ny+ny)%ny),c=hash((x0%nx+nx)%nx,((y0+1)%ny+ny)%ny),d=hash(((x0+1)%nx+nx)%nx,((y0+1)%ny+ny)%ny);return mix(mix(a,b,tx),mix(c,d,tx),ty);};
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const u=x/width,v=y/height,large=noise(u,v,5,3),medium=noise(u,v,13,8),fine=noise(u,v,31,16);
  let field=.54*large+.31*medium+.15*fine;
  if(gas){const wave=v+.018*Math.sin(u*13+large*5)+.007*Math.sin(u*31+medium*7),bands=.5+.5*Math.sin(wave*(id==="jupiter"?58:id==="saturn"?46:34)*Math.PI);field=.34+.44*bands+.22*field;if(id==="jupiter"&&((u-.72)*width)**2/1150+((v-.58)*height)**2/300<1)field=.83+.12*medium;if(id==="neptune"&&Math.abs(u-.67)<.065&&Math.abs(v-.44)<.07)field*=.48;}
  else if(id==="io")field=.48*field+.28*Math.sin(u*85+v*7)*Math.sin(v*63-u*9)+.24*medium;
  else if(id==="europa")field=.42*field+.58*(.5+.5*Math.sin(u*79+Math.sin(v*19)*3+medium*2));
  else if(id==="titan"||id==="venus")field=.62*field+.38*(.5+.5*Math.sin(v*25+Math.sin(u*9+medium)*2));
  field=Math.max(0,Math.min(.999,field));const band=field<.48?0:field<.77?1:2,t=band===0?field/.48:band===1?(field-.48)/.29:(field-.77)/.23,shade=gas?.88+.12*large:.76+.24*large,i=(y*width+x)*4;
  for(let ch=0;ch<3;ch++)image.data[i+ch]=Math.round(mix(colors[band][ch],colors[Math.min(2,band+1)][ch],t)*shade);
  image.data[i+3]=255;
 }
 context.putImageData(image,0,0);
 if(["mercury","mars","moon","phobos","deimos","ganymede","callisto","mimas","tethys","dione","rhea","iapetus","miranda","ariel","umbriel","titania","oberon"].includes(id)){
  let craterSeed=seed;const random=()=>{craterSeed=(Math.imul(craterSeed,1664525)+1013904223)>>>0;return craterSeed/4294967296;};
  for(let i=0;i<(width<300?34:58);i++){const cx=random()*width,cy=random()*height,r=1.1+random()*(width/64);context.beginPath();context.arc(cx,cy,r,0,Math.PI*2);const shade=20+Math.floor(random()*45);context.fillStyle=`rgba(${shade},${shade},${shade},.24)`;context.fill();context.beginPath();context.arc(cx-r*.18,cy-r*.2,r*.84,Math.PI*1.05,Math.PI*1.85);context.strokeStyle="rgba(242,235,217,.25)";context.lineWidth=Math.max(.5,r*.12);context.stroke();}
 }
 const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,canvas);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);bodyTextureCache.set(id,texture);return texture;
}
function atmosphereSkyTexture(){
 const width=deviceProfile.tier==="high"?1024:512,height=width/2;
 const c=document.createElement("canvas");c.width=width;c.height=height;
 const q=c.getContext("2d"),g=q.createLinearGradient(0,0,0,height);
 g.addColorStop(0,"#071a36");g.addColorStop(.16,"#153c70");
 g.addColorStop(.34,"#4e8fbd");g.addColorStop(.46,"#9bc9df");
 g.addColorStop(.5,"#d7e8ef");g.addColorStop(.54,"#9bc9df");
 g.addColorStop(.66,"#4e8fbd");g.addColorStop(.84,"#153c70");g.addColorStop(1,"#071a36");
 q.fillStyle=g;q.fillRect(0,0,width,height);
 const cloudWidth=deviceProfile.tier==="high"?384:deviceProfile.tier==="balanced"?256:160;
 const cloudHeight=cloudWidth/2,cloudCanvas=document.createElement("canvas");
 cloudCanvas.width=cloudWidth;cloudCanvas.height=cloudHeight;
 const cloudContext=cloudCanvas.getContext("2d"),image=cloudContext.createImageData(cloudWidth,cloudHeight);
 const mod=(value,period)=>(value%period+period)%period;
 const hash=(x,y)=>{let h=Math.imul(x^0x51ed270b,0x45d9f3b);h=Math.imul(h^y,0x45d9f3b);return((h^h>>>16)>>>0)/4294967295};
 const smooth=value=>value*value*(3-2*value);
 const noise=(u,v,fx,fy)=>{
  const x=u*fx,y=v*fy,x0=Math.floor(x),y0=Math.floor(y),tx=smooth(x-x0),ty=smooth(y-y0);
  const a=hash(mod(x0,fx),mod(y0,fy)),b=hash(mod(x0+1,fx),mod(y0,fy));
  const d=hash(mod(x0,fx),mod(y0+1,fy)),e=hash(mod(x0+1,fx),mod(y0+1,fy));
  return(a+(b-a)*tx)*(1-ty)+(d+(e-d)*tx)*ty;
 };
 for(let y=0;y<cloudHeight;y++)for(let x=0;x<cloudWidth;x++){
  const u=x/cloudWidth,v=y/cloudHeight;
  const large=noise(u,v,5,3),medium=noise(u,v,11,7),fine=noise(u,v,23,14);
  const field=large*.58+medium*.29+fine*.13;
  const coverage=Math.max(0,Math.min(1,(field-.475)/.16));
  const cloud=coverage*coverage*(3-2*coverage);
  const lower=Math.max(0,Math.min(1,(v-.27)/.12));
  const upper=1-Math.max(0,Math.min(1,(v-.69)/.13));
  const band=lower*lower*(3-2*lower)*upper*upper*(3-2*upper);
  const alpha=Math.max(0,Math.min(.66,cloud*band*(.22+.44*medium)));
  const i=(y*cloudWidth+x)*4,shade=.83+.17*large;
  image.data[i]=Math.round(233+22*shade);image.data[i+1]=Math.round(240+15*shade);
  image.data[i+2]=Math.round(246+9*shade);image.data[i+3]=Math.round(alpha*255);
 }
 cloudContext.putImageData(image,0,0);q.imageSmoothingEnabled=true;
 q.drawImage(cloudCanvas,0,0,width,height);
 const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
 gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);
 gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
 gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);return texture;
}
function softShadowTexture(){
 const c=document.createElement("canvas");c.width=c.height=128;
 const q=c.getContext("2d"),g=q.createRadialGradient(64,64,4,64,64,64);
 g.addColorStop(0,"rgba(12,18,21,.62)");g.addColorStop(.34,"rgba(15,23,25,.40)");
 g.addColorStop(.72,"rgba(18,27,28,.13)");g.addColorStop(1,"rgba(18,27,28,0)");
 q.fillStyle=g;q.fillRect(0,0,128,128);
 const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
 gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);
 gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);return texture;
}
function groundTexture(kind){const size=1024,c=document.createElement("canvas");c.width=c.height=size;const q=c.getContext("2d"),image=q.createImageData(size,size);let seed=kind==="asphalt"?0x52554e57:kind==="terrain-drone"?0x44524f4e:0x41535452;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296},clamp=v=>Math.max(0,Math.min(255,v));for(let y=0;y<size;y++)for(let x=0;x<size;x++){const i=(y*size+x)*4,u=x/size,v=y/size,coarse=Math.sin(x*.010+Math.sin(y*.006)*2.0)*Math.cos(y*.009+x*.003),patch=Math.sin(x*.021+Math.sin(y*.010)*1.6)*Math.cos(y*.015+x*.008),fine=(random()-.5),stripe=.5+.5*Math.sin((u*.85+v*1.6)*Math.PI*2),roadGrid=Math.max(Math.exp(-Math.pow((u-.25)*38,2)),Math.exp(-Math.pow((u-.74)*42,2)),Math.exp(-Math.pow((v-.36)*34,2))),service=Math.max(Math.exp(-Math.pow((u+v-1.05)*18,2)),Math.exp(-Math.pow((u-v-.18)*22,2)));let r,g,b;if(kind==="terrain-aircraft"){const wetland=Math.exp(-Math.pow((v-.10)*10,2))*0.5+Math.exp(-Math.pow((v-.88)*8,2))*0.38,field=.56+.18*coarse+.16*patch+.10*stripe-wetland*.32;r=78+field*55+wetland*8;g=96+field*78+wetland*20;b=64+field*38+wetland*18;if(roadGrid>.40){const t=Math.min(1,(roadGrid-.40)/.60);r=r*(1-t)+112*t;g=g*(1-t)+116*t;b=b*(1-t)+108*t}if(service>.48){const t=Math.min(1,(service-.48)/.52);r=r*(1-t)+134*t;g=g*(1-t)+132*t;b=b*(1-t)+118*t}}else if(kind==="terrain-drone"){const urban=.48+.14*coarse+.18*patch+.08*fine,green=Math.max(0,.55-.9*roadGrid);r=92+urban*45+green*6;g=97+urban*44+green*18;b=96+urban*43+green*7;const blocks=(Math.sin(u*65)*Math.sin(v*57));if(blocks>.68){r+=28;g+=24;b+=20}if(roadGrid>.24){const t=Math.min(1,(roadGrid-.24)/.76);r=r*(1-t)+122*t;g=g*(1-t)+126*t;b=b*(1-t)+124*t}if(service>.34){const t=Math.min(1,(service-.34)/.66);r=r*(1-t)+138*t;g=g*(1-t)+140*t;b=b*(1-t)+136*t}}else{const aggregate=.52+.28*coarse+.14*patch+.10*fine,mark=.5+.5*Math.sin(v*Math.PI*2*14);r=54+aggregate*20;g=56+aggregate*20;b=60+aggregate*22;r-=service*8;g-=service*8;b-=service*8;if(Math.abs(u-.5)<.006&&mark>.45){r=214;g=208;b=146}else if(Math.abs(u-.5)<.016){r+=18;g+=18;b+=12}}image.data[i]=clamp(r);image.data[i+1]=clamp(g);image.data[i+2]=clamp(b);image.data[i+3]=255}q.putImageData(image,0,0);const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT);return tex}
function part(root,x,y,z,sx,sy,sz,color,rot=0,tex=null,mesh=cube){const local=mul(T(x,y,z),mul(RY(rot),S(sx,sy,sz)));drawMesh(mesh,mul(root,local),color,tex,false)}
const orbitalSceneModels={station:{id:"nasa-iss-b",name:"NASA International Space Station (ISS) · model B",url:"assets/vehicles/nasa-iss-b.glb?v=2",source:"NASA 3D Resources · International Space Station (ISS) (B)",source_url:"https://science.nasa.gov/3d-resources/international-space-station-iss-b/",license:"NASA Usage Guidelines",orientation:"y",scale:.2}};
function orbitalSceneAsset(key){const model=orbitalSceneModels[key];if(!model)return null;const asset=state.catalogVehicles[model.id];if(!asset&&!state.catalogVehicleLoads[model.id]&&state.visualModelError!==model.id)loadCatalogVehicle(model,"space").catch(error=>console.warn("ASTRA orbital scene model unavailable:",model.id,error));return asset||null}
function drawSatellite(x,y,z,rot,attitudeQuaternion=null){
 const attitudeFrame=bodyQuaternionSceneFrame(attitudeQuaternion);
 const root=mul(T(x,y,z),attitudeFrame||RY(rot));
 if(state.userVehicles.space){drawImportedVehicle(root,"space");return}
 const model=catalogModelFor("space"),asset=catalogVehicleFor("space");
 if(model?.role==="full"){if(asset)drawVehicleAsset(root,"space",asset,visualScale("space"),[0,0,0],model.orientation);return}
 if(model?.role==="modern-launcher"&&model.orbit_url){
  const orbital={...model,id:model.id+"-orbit",url:model.orbit_url,name:model.name+" · veicolo orbitale"},orbitalAsset=state.catalogVehicles[orbital.id];
  if(!orbitalAsset&&!state.catalogVehicleLoads[orbital.id]&&state.visualModelError!==orbital.id)loadCatalogVehicle(orbital,"space").catch(error=>console.warn("ASTRA orbital vehicle model unavailable:",orbital.id,error));
  if(orbitalAsset)drawVehicleAsset(root,"space",orbitalAsset,model.orbit_scale||.075,[0,0,0],model.orientation);
 }
}
function drawStation(x,y,z,rot){const model=orbitalSceneModels.station,asset=orbitalSceneAsset("station");if(asset)drawVehicleAsset(mul(T(x,y,z),RY(rot)),"space",asset,model.scale,[0,0,0],model.orientation,false,1)}
function alignY(direction){const y=norm(direction),ref=Math.abs(y[2])>.94?[0,1,0]:[0,0,1],x=norm(cross(ref,y)),z=norm(cross(x,y)),m=mat();m[0]=x[0];m[1]=x[1];m[2]=x[2];m[4]=y[0];m[5]=y[1];m[6]=y[2];m[8]=z[0];m[9]=z[1];m[10]=z[2];return m}
function bodyQuaternionSceneFrame(q){if(!Array.isArray(q)||q.length!==4||!q.every(Number.isFinite))return null;let[w,x,y,z]=q;const s=Math.hypot(w,x,y,z);if(s<1e-8)return null;w/=s;x/=s;y/=s;z/=s;const r00=1-2*(y*y+z*z),r01=2*(x*y-z*w),r02=2*(x*z+y*w),r10=2*(x*y+z*w),r11=1-2*(x*x+z*z),r12=2*(y*z-x*w),r20=2*(x*z-y*w),r21=2*(y*z+x*w),r22=1-2*(x*x+y*y),m=mat();[m[0],m[1],m[2],m[4],m[5],m[6],m[8],m[9],m[10]]=[r00,r20,r10,r01,r21,r11,r02,r22,r12];return m}
function drawParachuteLines(root,scale,size,canopyY){const positions=[],normals=[],uvs=[],indices=[],count=12;for(let i=0;i<count;i++){const angle=i/count*Math.PI*2,c=Math.cos(angle),s=Math.sin(angle),index=i*2;positions.push(c*scale*.16,s*scale*.16,scale*1.22,c*size*.94,s*size*.94,canopyY+size*.035);normals.push(0,0,1,0,0,1);uvs.push(0,0,0,0);indices.push(index,index+1)}if(!parachuteLineMesh)parachuteLineMesh=geo(positions,normals,uvs,indices,gl.LINES);else{gl.bindBuffer(gl.ARRAY_BUFFER,parachuteLineMesh.buffers[0]);gl.bufferSubData(gl.ARRAY_BUFFER,0,new Float32Array(positions))}gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);drawMesh(parachuteLineMesh,root,[.86,.78,.61],null,false);gl.depthMask(true);gl.disable(gl.BLEND)}
function drawLauncher(x,y,z,direction,e){
 const phase=e.phase||"READY",attitudeFrame=bodyQuaternionSceneFrame(e.attitude_quaternion_body_to_eci),model=catalogModelFor("space"),catalogSpacecraft=catalogVehicleFor("space");
 if(state.userVehicles.space){drawImportedVehicle(mul(T(x,y,z),attitudeFrame||alignY(direction)),"space",true);return}
 if(!model)return;
 const altitude=Math.max(0,e.altitude_m||0),recoveryPhase=["REENTRY","AEROSHELL","DROGUE","PARACHUTE","LANDED","CRASHED"].includes(phase),padBlend=model.role==="modern-launcher"&&!recoveryPhase?Math.max(0,1-altitude/1000):0,launchOffset=launchSiteVisualOffset(state.seconds,padBlend),frameRoot=mul(T(x+launchOffset[0],y+launchOffset[1],z+launchOffset[2]),attitudeFrame||alignZ(direction));
 if(model.role==="modern-launcher"){
  const recovery=["REENTRY","AEROSHELL","DROGUE","PARACHUTE","LANDED","CRASHED"].includes(phase),orbital=["ORBIT_COAST","STATION_KEEPING","RENDEZVOUS","DEORBIT_ALIGN","DEORBIT_BURN","DEORBIT_COAST"].includes(phase),separations=e.mission_started?(e.stage_events||[]).filter(event=>event.event==="STAGE_SEPARATION"||event.event==="STAGE_JETTISON").length:0;
  let variant=null,scale=model.scale||.3;
  if(recovery){variant=model.recovery_url?{...model,id:model.id+"-recovery",url:model.recovery_url,name:model.name+" · capsula rientro"}:null;scale=model.recovery_scale||scale}
  else if((separations>=2||orbital)&&model.orbit_url){variant={...model,id:model.id+"-orbit",url:model.orbit_url,name:model.name+" · veicolo orbitale"};scale=model.orbit_scale||scale}
  else if(separations>=1&&model.stage_url){variant={...model,id:model.id+"-stage",url:model.stage_url,name:model.name+" · stadio superiore"};scale=model.stage_scale||scale}
  const asset=variant?state.catalogVehicles[variant.id]:catalogSpacecraft;if(asset&&!variant)scale*=asset.visualScaleCorrection||1;
  if(variant&&!asset&&!state.catalogVehicleLoads[variant.id]&&state.visualModelError!==variant.id)loadCatalogVehicle(variant,"space").catch(error=>console.warn("ASTRA launch vehicle variant unavailable:",variant.id,error));
  const modelAxis=recovery?(model.recovery_orientation||model.orientation):model.orientation,grounded=recovery?phase==="LANDED":!variant;
  if(asset)drawVehicleAsset(frameRoot,"space",asset,scale,[0,0,0],modelAxis,grounded,2);
  if(asset&&!recovery&&phase==="ASCENT"&&(e.command?.throttle_pct||0)>0){const pulse=.92+.08*Math.sin(state.seconds*38),flameLength=scale*(.62+.07*pulse),flameWidth=scale*.038,bounds=visualVerticalBounds(asset,"space",modelAxis,2),nozzleZ=grounded?0:-(bounds.maxByAxis[2]-bounds.minByAxis[2])*.5*scale;gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(frameRoot,mul(T(0,0,nozzleZ-flameLength*1.02),S(flameWidth,flameWidth,flameLength))),[1,.36,.07],null,false);drawMesh(globe,mul(frameRoot,mul(T(0,0,nozzleZ-flameLength*.78),S(flameWidth*.5,flameWidth*.5,flameLength*.72))),[.38,.72,1],null,false);gl.disable(gl.BLEND)}
  if(asset&&recovery&&(phase==="PARACHUTE"||phase==="DROGUE")){const open=Math.min(1,(e.phase_time_s||0)/(phase==="DROGUE"?2:5)),size=(phase==="DROGUE"?.35:.75)*scale*8*open,canopyY=scale*1.65+size*.72;gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);drawMesh(dishMesh,mul(frameRoot,mul(T(0,0,canopyY),S(size,size,size*.7))),phase==="DROGUE"?[.75,.77,.73]:[.94,.84,.65],null,false);gl.disable(gl.BLEND);drawParachuteLines(frameRoot,scale,size,canopyY)}
  return;
 }
 if(catalogSpacecraft&&model.role==="full")drawVehicleAsset(frameRoot,"space",catalogSpacecraft,visualScale("space"),[0,0,0],model.orientation,true);
 // No procedural vehicle fallback: a missing GLB stays visibly missing and is reported in the model status.
}
function loadTexture(url,fallback,maxTextureSize=deviceProfile.textureMax,onError=null,onLoad=null){const t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(fallback));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);const img=new Image();const resolvedUrl=new URL(url,location.href);if(resolvedUrl.origin!==location.origin)img.crossOrigin="anonymous";img.onload=()=>{try{const max=Math.min(gl.getParameter(gl.MAX_TEXTURE_SIZE),maxTextureSize);let src=img;if(img.width>max||img.height>max){const c=document.createElement("canvas"),scale=Math.min(max/img.width,max/img.height);c.width=Math.max(1,Math.floor(img.width*scale));c.height=Math.max(1,Math.floor(img.height*scale));c.getContext("2d").drawImage(img,0,0,c.width,c.height);src=c}gl.bindTexture(gl.TEXTURE_2D,t);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,src);gl.generateMipmap(gl.TEXTURE_2D)}catch(error){if(onError)onError(error,t);return}finally{gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false)}if(onLoad)onLoad(t)};img.onerror=error=>{if(onError)onError(error,t)};const textureUrl=resolvedUrl.origin===location.origin?`${url}${url.includes("?")?"&":"?"}v=${TEXTURE_BUILD_ID}`:url;img.src=textureUrl;return t}
function launchGroundTexture(centerLat=state.launchSiteGeo.latitude,centerLon=state.launchSiteGeo.longitude){const epoch=++launchGroundTextureEpoch;for(const texture of [launchGroundTex,launchGroundNearTex])if(texture)gl.deleteTexture(texture);launchGroundTex=launchGroundNearTex=null;const offsetNorth=(centerLat-LAUNCH_SITE_LATITUDE)*EARTH_RADIUS,offsetEast=(centerLon-LAUNCH_SITE_LONGITUDE)*EARTH_RADIUS*Math.cos(LAUNCH_SITE_LATITUDE);if(Math.hypot(offsetNorth,offsetEast)>100)return;const nearLevel=deviceProfile.tier==="low"?"1k":deviceProfile.tier==="balanced"?"2k":"4k",farLevel=deviceProfile.tier==="low"?"1k":"2k",maxTextureSize=deviceProfile.tier==="high"?4096:deviceProfile.textureMax,loadLayer=(url,near)=>loadTexture(url,[10,45,75,255],maxTextureSize,(error,texture)=>{gl.deleteTexture(texture);if(epoch===launchGroundTextureEpoch){if(near)launchGroundNearTex=null;else launchGroundTex=null}},texture=>{if(epoch===launchGroundTextureEpoch){if(near)launchGroundNearTex=texture;else launchGroundTex=texture}else gl.deleteTexture(texture)});loadLayer("assets/earth-cape-wide-"+farLevel+".webp",false);loadLayer("assets/earth-cape-near-"+nearLevel+".webp",true)}
function mapTex(){
 const level=deviceProfile.tier==="low"?"1k":deviceProfile.tier==="balanced"?"2k":"8k";
 const texture=loadTexture(`assets/earth-natural-${level}.webp`,[10,45,75,255],deviceProfile.tier==="high"?8192:deviceProfile.textureMax);
 const anisotropic=gl.getExtension("EXT_texture_filter_anisotropic");
 if(anisotropic){
  const supported=gl.getParameter(anisotropic.MAX_TEXTURE_MAX_ANISOTROPY_EXT)||1;
  const requested=deviceProfile.tier==="high"?8:deviceProfile.tier==="balanced"?4:2;
  gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.texParameterf(gl.TEXTURE_2D,anisotropic.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(supported,requested));
 }
 return texture;
}
function milkyWayTex(){const level=deviceProfile.tier==="low"?"2k":"4k";const maxSize=deviceProfile.tier==="low"?2048:4096;return loadTexture(`assets/space-nebula-${level}.webp`,[0,0,0,255],maxSize)}

function init(){
 const vs=["#version 300 es","in vec3 aPos;in vec3 aNormal;in vec2 aUV;uniform mat4 uViewModel;uniform mat3 uNormalMatrix;uniform mat4 uProj;out vec3 vN;out vec3 vW;out vec2 vUV;","void main(){vec4 eye=uViewModel*vec4(aPos,1.);vW=eye.xyz;vN=normalize(uNormalMatrix*aNormal);vUV=aUV;gl_Position=uProj*eye;}"].join("\n");
  const fs=["#version 300 es","precision highp float;in vec3 vN;in vec3 vW;in vec2 vUV;uniform vec4 uColor;uniform sampler2D uTex;uniform int uTexOn;uniform int uAtmo;uniform int uSky;uniform int uAlphaMode;uniform float uAlphaCutoff;uniform vec3 uLightDir;uniform int uEarthSurface;out vec4 frag;","void main(){if(uSky==1){vec3 sky=pow(texture(uTex,vUV).rgb,vec3(.94))*1.035;frag=vec4(sky,1.);return;}vec3 n=normalize(vN);vec3 viewDirection=normalize(-vW);if(uAtmo==1){float rim=pow(1.-max(dot(n,viewDirection),0.),2.3);frag=vec4(uColor.rgb,rim*.72*uColor.a);return;}vec4 texel=uTexOn==1?texture(uTex,vUV):vec4(1.);if(uEarthSurface==1&&texel.a<.01)discard;vec4 base=texel*uColor;if(uAlphaMode==1&&base.a<uAlphaCutoff)discard;vec3 l=normalize(uLightDir);float d=max(dot(n,l),0.);float sh=.25+.94*d;float sp=pow(max(dot(reflect(-l,n),viewDirection),0.),24.)*.16;if(uEarthSurface==1){vec3 srgb=clamp(base.rgb,vec3(0.),vec3(1.));vec3 albedoLinear=mix(srgb/12.92,pow((srgb+vec3(.055))/1.055,vec3(2.4)),step(vec3(.04045),srgb));vec3 earthLinear=albedoLinear*(.38+.62*d);base.rgb=mix(earthLinear*12.92,1.055*pow(max(earthLinear,vec3(0.)),vec3(1./2.4))-vec3(.055),step(vec3(.0031308),earthLinear));sp=0.;}frag=vec4(base.rgb*(uEarthSurface==1?1.:sh)+sp,uAlphaMode==2?base.a:1.);}"].join("\n");
 p=makeProgram(vs,fs);
 const skyVs=["#version 300 es","out vec2 vUv;void main(){vec2 p[3]=vec2[3](vec2(-1.,-1.),vec2(3.,-1.),vec2(-1.,3.));vec2 q=p[gl_VertexID];vUv=q*.5+.5;gl_Position=vec4(q,1.,1.);}"].join("\n");
 const skyFs=["#version 300 es","precision highp float;in vec2 vUv;uniform sampler2D uAirTex;uniform sampler2D uSpaceTex;uniform mat3 uSkyRotation;uniform vec3 uRight;uniform vec3 uUp;uniform vec3 uForward;uniform vec3 uAtmosphereUp;uniform vec3 uAtmosphereEast;uniform vec3 uAtmosphereNorth;uniform float uAspect;uniform float uTanHalfFov;uniform float uTransition;out vec4 frag;","void main(){vec2 p=vUv*2.-1.;vec3 ray=normalize(uForward+uRight*(p.x*uAspect*uTanHalfFov)+uUp*(p.y*uTanHalfFov));vec3 airRay=normalize(vec3(dot(ray,uAtmosphereEast),dot(ray,uAtmosphereUp),dot(ray,uAtmosphereNorth)));float lat=asin(clamp(airRay.y,-1.,1.));float lon=atan(airRay.x,airRay.z);vec2 airUv=vec2(fract(lon*.1591549431+.5),clamp(.5+lat*.3183098862,.001,.999));vec2 spaceUv=vUv;float texAspect=2.;if(uAspect>texAspect){float scale=texAspect/uAspect;spaceUv.y=(spaceUv.y-.5)*scale+.5;}else{float scale=uAspect/texAspect;spaceUv.x=(spaceUv.x-.5)*scale+.5;}spaceUv=clamp(spaceUv,vec2(.001),vec2(.999));vec3 air=texture(uAirTex,airUv).rgb;vec3 space=texture(uSpaceTex,spaceUv).rgb;float transition=smoothstep(0.,1.,uTransition);vec3 sky=mix(air,space,transition);vec3 sun=normalize(vec3(.62,.82,.68));float mu=max(dot(ray,sun),0.);float haze=exp(-abs(airRay.y)*12.)*(1.-transition);sky=mix(sky,vec3(.68,.81,.87),haze*.10);sky+=vec3(1.,.62,.30)*pow(mu,420.)*.9+vec3(.42,.72,1.)*pow(mu,26.)*.065*(1.-transition);frag=vec4(sky,1.);}"].join("\n");
 skyProgram=makeProgram(skyVs,skyFs);
 const sv=["#version 300 es","in vec3 aPos;uniform mat4 uView;uniform mat4 uProj;void main(){gl_Position=uProj*uView*vec4(aPos,1.);gl_PointSize=1.7;}"].join("\n");
 const sf=["#version 300 es","precision mediump float;uniform float uOpacity;out vec4 frag;void main(){float a=1.-smoothstep(.16,.5,length(gl_PointCoord-.5));frag=vec4(.78,.88,1.,a*.8*uOpacity);}"].join("\n");sp=makeProgram(sv,sf);const detail=deviceProfile.geometry;globe=sphere(Math.max(320,Math.round(384*detail)),Math.max(480,Math.round(576*detail)));launchSurfaceGeo=launchSurfacePatch(256,256,60000,state.launchSiteGeo.latitude,state.launchSiteGeo.longitude,true,.30);launchSurfaceNearGeo=launchSurfacePatch(256,256,3000,state.launchSiteGeo.latitude,state.launchSiteGeo.longitude,true,.32);launchSurfaceFallbackGeo=launchSurfacePatch(256,256,60000,state.launchSiteGeo.latitude,state.launchSiteGeo.longitude,false,.30);terrainDetail=Math.max(24,Math.round(56*detail));cube=boxGeo();terrainGeo=terrain(terrainDetail,terrainTileX,terrainTileZ);runwayMarkingsGeo=runwayMarkingsGeometry();dishMesh=dishGeo();panelMesh=panelGeo();cylinderMesh=cylinderGeo();earthTex=mapTex();launchGroundTexture();skyTex=milkyWayTex();atmosphereSkyTex=atmosphereSkyTexture();shadowTex=softShadowTexture();solarTex=surfaceTex("solar");foilTex=surfaceTex("foil");
 const pts=[];let seed=0x41535452;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};for(let i=0;i<deviceProfile.stars;i++){const a=random()*6.28318530718,y=random()*2-1,r=Math.sqrt(1-y*y);pts.push(Math.cos(a)*r*50,y*r*50,Math.sin(a)*r*50)}stars=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,stars);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(pts),gl.STATIC_DRAW);starCount=pts.length/3;
 canvas.addEventListener("pointerdown",e=>{const altitude=Math.max(0,state.engine?.altitude_m||0),transition=state.kind==="space"&&!state.solarView?Math.max(0,Math.min(1,(altitude-12000)/68000)):0;state.drag={x:e.clientX,y:e.clientY,az:state.az,el:state.spaceCameraManual?state.el:state.el*(1-transition)+.20*transition};canvas.setPointerCapture(e.pointerId)});
 canvas.addEventListener("pointermove",e=>{if(state.drag){const dx=e.clientX-state.drag.x,dy=e.clientY-state.drag.y;if(state.kind==="space"&&(dx||dy))state.spaceCameraManual=true;state.az=state.drag.az-dx*.006;state.el=Math.max(-1.1,Math.min(1.15,state.drag.el+dy*.005))}});
 canvas.addEventListener("pointerup",()=>state.drag=null);canvas.addEventListener("pointercancel",()=>state.drag=null);
  canvas.addEventListener("wheel",e=>{if(state.kind==="space"&&!state.solarView)state.spaceZoom=Math.max(.00005,Math.min(40,state.spaceZoom*Math.exp(e.deltaY*.004)));else state.zoom=Math.max(4.2,Math.min(18,state.zoom+e.deltaY*.012));e.preventDefault()},{passive:false});resize();
}
function resize(){const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight),dpr=Math.min(devicePixelRatio||1,deviceProfile.dprCap),budget=deviceProfile.pixelBudget*renderScale,d=Math.min(dpr,Math.sqrt(budget/(w*h)),3840/w,2160/h);canvas.width=Math.max(1,Math.round(w*d));canvas.height=Math.max(1,Math.round(h*d));if(gl)gl.viewport(0,0,canvas.width,canvas.height);else if(ctx2d)ctx2d.setTransform(canvas.width/w,0,0,canvas.height/h,0,0);const names={low:"LEGGERA",balanced:"BILANCIATA",high:"ALTA"};if($("#renderProfile"))$("#renderProfile").textContent=(canvas.width>=3840&&canvas.height>=2160?"4K":names[deviceProfile.tier])+" · "+deviceProfile.targetFps+" FPS"+(renderScale<.98?" · AUTO SCALA":"")}
function airVisualPosition(){const e=state.engine||{},pos=e.position_ned_m||[0,0,0],scale=.1;return[pos[0]*scale,AIR_RUNWAY_TOP+.001-pos[2]*scale,pos[1]*scale]}
const flightTrace=[];let flightTraceLastTime=-Infinity,flightTraceRevision=0;
function resetFlightTrace(){flightTrace.length=0;flightTraceLastTime=-Infinity;flightTraceRevision++}
function captureFlightTrace(engineState){
 if(!engineState?.mission_started||!['aircraft','drone'].includes(engineState.vehicle)||!Array.isArray(engineState.position_ned_m)||engineState.position_ned_m.length<3||!Number.isFinite(engineState.time_s))return;
 const[north,east,down]=engineState.position_ned_m;if(![north,east,down].every(Number.isFinite))return;
 if(engineState.time_s<flightTraceLastTime)resetFlightTrace();
 const point=[north*.1,AIR_RUNWAY_TOP+.001-down*.1,east*.1];
 if(engineState.time_s===flightTraceLastTime){flightTrace[flightTrace.length-1]=point;flightTraceRevision++;return}
 if(engineState.time_s-flightTraceLastTime<.25)return;
 flightTrace.push(point);flightTraceLastTime=engineState.time_s;
 if(flightTrace.length>600)flightTrace.splice(0,flightTrace.length-600);
 flightTraceRevision++
}
function cameraSet(){
 const rv=state.engine?.position_eci_m||[EARTH_RADIUS,0,0];
 const follow=state.kind==="space"
  ?(()=>{const scale=EARTH_RENDER_RADIUS/EARTH_RADIUS;return[-1.8+rv[0]*scale,-.5+rv[2]*scale,rv[1]*scale]})()
  :airVisualPosition();
 const altitude=Math.max(0,state.engine?.altitude_m||0);
 const spaceSkyTransition=state.kind==="space"&&!state.solarView?Math.max(0,Math.min(1,(altitude-12000)/68000)):0;
 const orbitalScene=state.kind==="space"&&!state.solarView&&state.engine?.scenario==="orbital";
 const cameraElevation=state.kind==="space"&&!state.solarView&&!state.spaceCameraManual
  ?(orbitalScene?0.82:state.el*(1-spaceSkyTransition)+0.20*spaceSkyTransition)
  :state.el;
  let spaceZoom=state.spaceZoom;
  const airZoom=state.kind==="aircraft"
   ?Math.max(2.0,Math.min(4.8,state.zoom*.36))
  :state.kind==="drone"?Math.max(.4,Math.min(.62,state.zoom*.085))
  :Math.max(3.5,Math.min(6,state.zoom*.62));
 let r=state.solarView?Math.min(state.zoom,9):state.kind==="space"?spaceZoom:airZoom;
 const localUp=state.kind==="space"&&!state.solarView?norm([rv[0],rv[2],rv[1]]):[0,1,0];
 const phase=state.engine?.phase||"READY";
 const recovery=["REENTRY","AEROSHELL","DROGUE","PARACHUTE","LANDED","CRASHED"].includes(phase);
 const orbital=["ORBIT_COAST","STATION_KEEPING","RENDEZVOUS","DEORBIT_ALIGN","DEORBIT_BURN","DEORBIT_COAST"].includes(phase),separationCount=state.engine?.mission_started?(state.engine.stage_events||[]).filter(event=>event.event==="STAGE_SEPARATION"||event.event==="STAGE_JETTISON").length:0;
 let anchorLift=0;
 if(state.kind==="space"&&!state.solarView){
  const model=catalogModelFor("space"),userAsset=state.userVehicles.space;
  let asset=userAsset||catalogVehicleFor("space");
  let scale=userAsset?importedVisualScale(userAsset,"space"):model?.role==="modern-launcher"?(model.scale||.3):visualScale("space"),variantKey=null;
  if(model?.role==="modern-launcher"){
   if(recovery){scale=model.recovery_scale||scale;variantKey=model.recovery_url&&phase==="LANDED"?model.id+"-recovery":null}
   else if(orbital||separationCount>=2){scale=model.orbit_scale||scale;variantKey=model.orbit_url?model.id+"-orbit":null}
   else if(separationCount>=1&&model.stage_url){scale=model.stage_scale||scale;variantKey=model.id+"-stage"}
   if(!recovery&&!orbital&&!separationCount)scale*=asset?.visualScaleCorrection||1;
   spaceZoom*=Math.max(.035,Math.min(1,scale/(model.scale||scale)));if(phase==="DROGUE")spaceZoom*=1.6;else if(phase==="PARACHUTE")spaceZoom*=2.1;r=spaceZoom;
  }
  const axis=userAsset?null:recovery?(model?.recovery_orientation||model?.orientation):model?.orientation;
  if(variantKey)asset=state.catalogVehicles[variantKey]||null;
  else if(model?.role==="modern-launcher"&&(recovery||orbital||separationCount>=1))asset=null;
  const grounded=!!userAsset||model?.role==="full"||(model?.role==="modern-launcher"?(recovery?phase==="LANDED":!orbital&&separationCount===0):false);
  if(asset&&grounded){const bounds=visualVerticalBounds(asset,"space",axis,2);anchorLift=(bounds.maxY-bounds.minY)*.5*scale;}
  // While a catalog GLB loads, keep the camera on the physical launch position.
  // A scene-space lift here would move the aim point tens of kilometres above the pad.
 }
 // The camera already rescales against the selected launch, stage, or capsule
 // asset above. Keep that framing through ascent instead of pulling away from
 // the vehicle as altitude increases.
 const target=state.solarView?[0,0,0]:state.kind==="space"
  ?follow.map((value,i)=>value+localUp[i]*anchorLift)
   :[follow[0],follow[1]+(state.kind==="aircraft"?0:state.kind==="drone"?.005:.18),follow[2]];
 let cameraDirection;
 if(state.kind==="space"&&!state.solarView){
  const reference=Math.abs(localUp[1])>.92?[0,0,1]:[0,1,0];
  const tangentA=norm(cross(reference,localUp)),tangentB=norm(cross(localUp,tangentA));
  const horizontal=tangentA.map((value,i)=>value*Math.cos(state.az)+tangentB[i]*Math.sin(state.az));
  cameraDirection=norm(horizontal.map((value,i)=>value*Math.cos(cameraElevation)+localUp[i]*Math.sin(cameraElevation)));
 }else cameraDirection=[Math.sin(state.az)*Math.cos(state.el),Math.sin(state.el),Math.cos(state.az)*Math.cos(state.el)];
  const eye=target.map((value,i)=>value+r*cameraDirection[i]);
  if(state.kind==="space"&&!state.solarView){
   const earthCenter=[-1.8,-.5,0],radialDistance=Math.hypot(...eye.map((value,i)=>value-earthCenter[i])),latitudeStep=.36/192,longitudeStep=.36/256*Math.cos(state.launchSiteGeo.latitude),patchAngularStep=Math.hypot(latitudeStep,longitudeStep),minimumRadius=EARTH_RENDER_RADIUS+EARTH_RENDER_RADIUS*patchAngularStep*patchAngularStep/8*1.5;
   if(radialDistance<minimumRadius)for(let i=0;i<3;i++)eye[i]+=localUp[i]*(minimumRadius-radialDistance);
  }
 view=look(eye,target,localUp);
 celestialView.set(view);celestialView[12]=0;celestialView[13]=0;celestialView[14]=0;
  sceneFovY=state.kind==="space"&&!state.solarView ? 0.76 : state.kind==="aircraft" ? 0.82 : 0.60;const aspect=canvas.width/canvas.height;
  // The Earth scene is scaled to the 3D assets' real dimensions. A short near
  // plane keeps the 100 m launch stack visible while the textured globe remains
  // the distant backdrop.
  projection=persp(sceneFovY,aspect,state.kind==="space"&&!state.solarView ? Math.max(.0000008,Math.min(.00003,r*.015)) : Math.max(.04,Math.min(.2,r*.015)),state.kind==="space"?110:state.kind==="aircraft"?1850:640);cams=eye;
}
function normalMatrix3(m){const a=m[0],b=m[1],c=m[2],d=m[4],e=m[5],f=m[6],g=m[8],h=m[9],i=m[10],c00=e*i-f*h,c01=f*g-d*i,c02=d*h-e*g,c10=c*h-b*i,c11=a*i-c*g,c12=b*g-a*h,c20=b*f-c*e,c21=c*d-a*f,c22=a*e-b*d,det=a*c00+d*c01+g*c02;if(!Number.isFinite(det)||Math.abs(det)<1e-20)return new Float32Array([1,0,0,0,1,0,0,0,1]);const k=1/det;return new Float32Array([c00*k,c10*k,c20*k,c01*k,c11*k,c21*k,c02*k,c12*k,c22*k])}
function drawMesh(g,model,color,tex,atmo,sky,material,lightDir=[.62,.82,.68],earthSurface=false){gl.useProgram(p);gl.bindVertexArray(g.vao);const u=n=>gl.getUniformLocation(p,n),c=color||[1,1,1],viewModel=mul(view,model),normalMatrix=normalMatrix3(viewModel),lightView=norm([view[0]*lightDir[0]+view[4]*lightDir[1]+view[8]*lightDir[2],view[1]*lightDir[0]+view[5]*lightDir[1]+view[9]*lightDir[2],view[2]*lightDir[0]+view[6]*lightDir[1]+view[10]*lightDir[2]]);gl.uniformMatrix4fv(u("uViewModel"),false,viewModel);gl.uniformMatrix3fv(u("uNormalMatrix"),false,normalMatrix);gl.uniformMatrix4fv(u("uProj"),false,projection);gl.uniform4f(u("uColor"),c[0]??1,c[1]??1,c[2]??1,c[3]??1);gl.uniform3fv(u("uLightDir"),lightView);gl.uniform1i(u("uEarthSurface"),earthSurface?1:0);gl.uniform1i(u("uTexOn"),tex?1:0);gl.uniform1i(u("uAtmo"),atmo?1:0);gl.uniform1i(u("uSky"),sky?1:0);const mode=material?.alphaMode==="BLEND"?2:material?.alphaMode==="MASK"?1:0;gl.uniform1i(u("uAlphaMode"),mode);gl.uniform1f(u("uAlphaCutoff"),material?.alphaCutoff??.5);if(tex){gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,tex);gl.uniform1i(u("uTex"),0)}if(mode===2){gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA)}gl.drawElements(g.mode,g.count,gl.UNSIGNED_INT,0);if(mode===2){gl.depthMask(true);gl.disable(gl.BLEND)}gl.bindVertexArray(null)}
function createEmbeddedTexture(blob){return new Promise((resolve,reject)=>{const texture=gl.createTexture(),url=URL.createObjectURL(blob),image=new Image();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([255,255,255,255]));image.onload=()=>{try{const max=Math.min(gl.getParameter(gl.MAX_TEXTURE_SIZE),deviceProfile.textureMax);let source=image;if(image.width>max||image.height>max){const scale=Math.min(max/image.width,max/image.height),c=document.createElement("canvas");c.width=Math.max(1,Math.floor(image.width*scale));c.height=Math.max(1,Math.floor(image.height*scale));c.getContext("2d").drawImage(image,0,0,c.width,c.height);source=c}gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);gl.generateMipmap(gl.TEXTURE_2D);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.REPEAT);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.REPEAT);URL.revokeObjectURL(url);resolve(texture)}catch(error){URL.revokeObjectURL(url);gl.deleteTexture(texture);reject(error)}};image.onerror=()=>{URL.revokeObjectURL(url);gl.deleteTexture(texture);reject(new Error("Una texture incorporata non si riesce a decodificare."))};image.src=url})}
function importLimits(highFidelity=false){return highFidelity&&deviceProfile.tier==="high"?{maxTriangles:1_250_000,maxPrimitives:128,maxVertices:900_000}:deviceProfile.tier==="low"?{maxTriangles:65000,maxPrimitives:48,maxVertices:100000}:deviceProfile.tier==="balanced"?{maxTriangles:140000,maxPrimitives:72,maxVertices:240000}:{maxTriangles:280000,maxPrimitives:96,maxVertices:400000}}
function orientImportedModel(kind,configuredAxis=null){let axis=configuredAxis||state.modelOrientations[kind]||"auto";if(axis==="auto")axis=kind==="aircraft"||kind==="space"?"z":"y";if(axis==="y")return mat();if(axis==="x")return RZ(Math.PI/2);if(axis==="z")return kind==="aircraft"?RX(-Math.PI/2):RX(Math.PI/2);if(kind==="aircraft")return RZ(-Math.PI/2);return mat()}
function visualVerticalBounds(asset,kind,axis=null,upAxis=kind==="space"?2:1){
 const orientationKey=axis||state.modelOrientations[kind]||"auto",key=orientationKey+":"+upAxis;
 asset.visualBounds??={};if(asset.visualBounds[key])return asset.visualBounds[key];
 const orientation=orientImportedModel(kind,orientationKey),min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
 for(const primitive of asset.primitives){
  const positions=primitive.geometry?.positions||primitive.positions;if(!positions)continue;
  for(let i=0;i<positions.length;i+=3)for(let axisIndex=0;axisIndex<3;axisIndex++){
   const value=orientation[axisIndex]*positions[i]+orientation[4+axisIndex]*positions[i+1]+orientation[8+axisIndex]*positions[i+2]+orientation[12+axisIndex];
   min[axisIndex]=Math.min(min[axisIndex],value);max[axisIndex]=Math.max(max[axisIndex],value);
  }
 }
 if(!Number.isFinite(min[0])||!Number.isFinite(min[1])||!Number.isFinite(min[2])){min.fill(-.9);max.fill(.9)}
 return asset.visualBounds[key]={minByAxis:min,maxByAxis:max,minY:min[upAxis],maxY:max[upAxis]};
}
function removeSlsLaunchStand(parsed){
 let removedVertices=0,removedTriangles=0;
 for(const primitive of parsed.primitives){
  const positions=primitive.positions,indices=primitive.indices,count=positions?.length/3|0;
  if(!positions||!indices?.length||count<8)continue;
  const parent=Array.from({length:count},(_,index)=>index),find=index=>{while(parent[index]!==index){parent[index]=parent[parent[index]];index=parent[index]}return index},join=(a,b)=>{a=find(a);b=find(b);if(a!==b)parent[b]=a};
  for(let i=0;i<indices.length;i+=3){join(indices[i],indices[i+1]);join(indices[i],indices[i+2])}
  const components=new Map();for(let index=0;index<count;index++){const root=find(index),vertices=components.get(root)||[];vertices.push(index);components.set(root,vertices)}
  const stand=[];
  for(const vertices of components.values()){
   if(vertices.length>12)continue;
   const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
   for(const index of vertices)for(let axis=0;axis<3;axis++){const value=positions[index*3+axis];min[axis]=Math.min(min[axis],value);max[axis]=Math.max(max[axis],value)}
   if(min[1]<-.84&&max[1]<-.82&&max[1]-min[1]<.07&&max[0]-min[0]>.3&&max[2]-min[2]>.15)stand.push(...vertices);
  }
  if(!stand.length)continue;
  const removed=new Set(stand),remap=new Map(),compactIndices=[];
  for(let i=0;i<indices.length;i+=3){const tri=[indices[i],indices[i+1],indices[i+2]];if(tri.some(index=>removed.has(index))){removedTriangles++;continue}for(const index of tri){if(!remap.has(index))remap.set(index,remap.size);compactIndices.push(remap.get(index))}}
  const compact=(source,width)=>{const target=new Float32Array(remap.size*width);for(const[oldIndex,newIndex]of remap)for(let c=0;c<width;c++)target[newIndex*width+c]=source[oldIndex*width+c];return target};
  primitive.positions=compact(positions,3);primitive.normals=compact(primitive.normals,3);primitive.uvs=compact(primitive.uvs,2);primitive.indices=compactIndices;
  removedVertices+=stand.length;
 }
 parsed.vertices=Math.max(0,parsed.vertices-removedVertices);parsed.triangles=Math.max(0,parsed.triangles-removedTriangles);
 return{removedVertices,removedTriangles};
}
function catalogVehicleFor(kind=state.kind){const model=state.visualCatalog?.[kind]?.find(x=>x.id===state.visualModelPreferences[kind]);return model?state.catalogVehicles[model.id]||null:null}
function catalogModelFor(kind=state.kind){return state.visualCatalog?.[kind]?.find(x=>x.id===state.visualModelPreferences[kind])||null}
function visualScale(kind){return kind==="space"?.62:kind==="drone"?.036:1}
function importedVisualScale(asset,kind,axis=null){
 const bounds=visualVerticalBounds(asset,kind,axis),spans=bounds.maxByAxis.map((value,index)=>value-bounds.minByAxis[index]);
 const modelSpan=Math.max(...spans,1e-6),targetSpan=kind==="space"?1.15:kind==="aircraft"?8.4:1.1;
 return targetSpan/modelSpan;
}
function drawVehicleAsset(root,kind,asset,scale=visualScale(kind),offset=[0,0,0],axis=null,grounded=false,upAxis=kind==="space"?2:1){
 if(!asset)return false;
 const orientation=orientImportedModel(kind,axis),bounds=visualVerticalBounds(asset,kind,axis,upAxis),adjusted=offset.slice();
 for(let axisIndex=0;axisIndex<3;axisIndex++){
  const center=(bounds.minByAxis[axisIndex]+bounds.maxByAxis[axisIndex])*.5;
  adjusted[axisIndex]+=-(grounded&&axisIndex===upAxis?bounds.minByAxis[axisIndex]:center)*scale;
 }
 const base=mul(root,mul(T(...adjusted),mul(orientation,S(scale,scale,scale))));
 const physicalRotors=kind==="drone"?state.engine?.propulsion_actuators:null,rotorAnimation=asset.rotorAnimation;
 const visualAircraftRotor=kind==="aircraft"&&rotorAnimation?.visualController==="throttle"&&rotorAnimation.visualOnly;
 const rotorCount=rotorAnimation?.hubs?.length||0;
 const phases=physicalRotors?.rotor_phase_rad||(visualAircraftRotor?[state.visualPropellerPhase]:null);
 const speeds=physicalRotors?.motor_speed_actual_rad_s||(visualAircraftRotor?[state.visualPropellerRpm*2*Math.PI/60]:null);
 const directions=physicalRotors?.rotor_spin_direction||(visualAircraftRotor?[1]:null);
 const animateRotors=rotorCount>0&&phases?.length===rotorCount&&speeds?.length===rotorCount&&directions?.length===rotorCount&&(visualAircraftRotor||physicalRotors?.rotor_count===rotorCount);
 const predictionDt=kind==="drone"&&animateRotors&&state.running&&Number.isFinite(state.engineReceivedAt)
  ?Math.min(.25,Math.max(0,(performance.now()-state.engineReceivedAt)/1000))*state.speed:0;
 for(const primitive of asset.primitives){
  let model=base;
  if(animateRotors&&Number.isInteger(primitive.rotorIndex)&&primitive.rotorIndex<rotorCount){
   const index=primitive.rotorIndex,hub=rotorAnimation.hubs[index],angle=phases[index]+directions[index]*speeds[index]*predictionDt;
   const rotation=rotorAnimation.axis==="x"?RX(angle):rotorAnimation.axis==="z"?RZ(angle):RY(angle);
   model=mul(base,mul(T(...hub),mul(rotation,T(-hub[0],-hub[1],-hub[2]))));
  }
  drawMesh(primitive.geometry,model,primitive.material.color,primitive.texture,false,false,primitive.material);
 }
 if(animateRotors&&rotorAnimation.bladeRadius>0){
  for(let index=0;index<rotorCount;index++){
   const rpm=Math.abs(speeds[index])*60/(2*Math.PI);
   if(rpm<700)continue;
   const hub=rotorAnimation.hubs[index],alpha=Math.min(.38,.38*Math.min(1,rpm/5000));
   const rotorPlane=rotorAnimation.axis==="x"?RY(Math.PI/2):rotorAnimation.axis==="y"?RX(Math.PI/2):mat();
   const blur=mul(base,mul(T(hub[0],hub[1]+.002,hub[2]),mul(rotorPlane,S(rotorAnimation.bladeRadius,rotorAnimation.bladeRadius,rotorAnimation.bladeRadius*.025))));
   drawMesh(dishMesh,blur,[.88,.94,.96,alpha],null,false,false,{alphaMode:"BLEND"});
  }
 }
 return true;
}
function drawImportedVehicle(root,kind,grounded=false){const asset=state.userVehicles[kind];if(!asset)return false;return drawVehicleAsset(root,kind,asset,importedVisualScale(asset,kind),[0,0,0],null,grounded)}
function setVisualModelSummary(){
 const output=$("#visualModelSummary");if(!output)return;
 output.replaceChildren();const model=catalogModelFor();
 if(!model){output.textContent="Modelli pre-realizzati non disponibili; controlla la connessione.";return}
 const orbital=state.kind==="space"&&state.missionProfile==="orbital";
 const label=document.createElement("span");
 label.textContent=(orbital
  ?`Variante orbitale di ${model.name}. Il bersaglio ISS è mostrato separatamente; la dinamica usa il veicolo di servizio ASTRA selezionato.`
  :model.summary)+" ";output.append(label);
 const source=document.createElement("a");source.href=model.source_url;source.target="_blank";source.rel="noopener noreferrer";
 source.textContent=model.source+" · "+model.license;output.append(source);
 if(state.kind==="space"&&!orbital){
  const pad=document.createElement("a");pad.href=launchSiteModel.source_url;pad.target="_blank";pad.rel="noopener noreferrer";
  pad.textContent=" · RAMPA · NASA Mobile Launcher";output.append(pad);
  const padState=document.createElement("span");padState.className="visual-load-status";
  const padModel=state.catalogVehicles[launchSiteModel.id];
  padState.textContent=padModel?` · RAMPA GLB pronta · ${padModel.triangles.toLocaleString("it-IT")} triangoli`:state.catalogVehicleLoads[launchSiteModel.id]?" · caricamento GLB rampa…":state.visualModelError===launchSiteModel.id?` · errore GLB rampa: ${state.visualModelErrorMessage||"lettura non riuscita"}`:" · modello rampa locale";
  output.append(padState)
 }
 const note=document.createElement("span");note.className="visual-load-status";
 const asset=state.catalogVehicles[model.id];
 note.textContent=asset?` · GLB pronto · ${asset.triangles.toLocaleString("it-IT")} triangoli`:state.catalogVehicleLoads[model.id]?" · caricamento modello 3D…":state.visualModelError===model.id?` · GLB non caricato: ${state.visualModelErrorMessage||"errore di lettura"}`:" · si carica al primo utilizzo e resta nella cache del browser";
 output.append(note)
}
const setVisualModelSummaryBase=setVisualModelSummary;
setVisualModelSummary=function(){
 setVisualModelSummaryBase();
 const output=$("#visualModelSummary");
 if(!output||state.kind!=="space"||state.engine?.scenario!=="orbital")return;
 const model=orbitalSceneModels.station,asset=state.catalogVehicles[model.id],status=document.createElement("span");
 status.className="visual-load-status";
 status.textContent=asset?` · TARGET ORBITALE · NASA ISS GLB pronta · ${asset.triangles.toLocaleString("it-IT")} triangoli · scala di presentazione; dinamica SI`:state.catalogVehicleLoads[model.id]?" · TARGET ORBITALE · caricamento NASA ISS GLB…":state.visualModelError===model.id?` · TARGET ORBITALE · NASA ISS non caricata: ${state.visualModelErrorMessage||"errore GLB"}`:" · TARGET ORBITALE · NASA ISS in attesa del primo frame";
 output.append(status);
};
const setVisualModelSummaryWithOrbital=setVisualModelSummary;
setVisualModelSummary=function(){
 setVisualModelSummaryWithOrbital();
 if(state.kind!=="drone"&&state.kind!=="aircraft")return;
 const model=catalogModelFor(state.kind),asset=model&&state.catalogVehicles[model.id],output=$("#visualModelSummary");
 if(!output||!asset?.rotorAnimation)return;
 const status=document.createElement("span");status.className="visual-load-status";
 if(asset.rotorAnimation.visualOnly)status.textContent=" · ELICA ANIMATA VISIVAMENTE DAL COMANDO MOTORE · RPM INDICATIVI";
 else{const physicalRotorCount=state.engine?.propulsion_actuators?.rotor_count;status.textContent=physicalRotorCount&&physicalRotorCount!==asset.rotorAnimation.hubs.length
  ?` · MODELLO VISIVO ${asset.rotorAnimation.hubs.length} ROTORI; DINAMICA SELEZIONATA ${physicalRotorCount} ROTORI`
  :` · ${asset.rotorAnimation.hubs.length} ELICHE COLLEGATE A RPM E FASE DEL MODELLO FISICO`}
 output.append(status);
};
function populateVisualModelOptions(){const select=$("#visualVehicleModel");if(!select)return;const options=state.visualCatalog?.[state.kind]||[],key=state.kind+":"+options.map(x=>x.id).join("|");if(select.dataset.catalogKey!==key){select.replaceChildren();for(const model of options){const option=document.createElement("option");option.value=model.id;option.textContent=model.name;select.append(option)}select.dataset.catalogKey=key}if(options.length){if(!options.some(x=>x.id===state.visualModelPreferences[state.kind]))state.visualModelPreferences[state.kind]=defaultVisualModels[state.kind];state.visualModelId=state.visualModelPreferences[state.kind];select.value=state.visualModelId;setVisualModelSummary()}else{$("#visualModelSummary").textContent="Caricamento del catalogo modelli…"}}
function splitCatalogRotorMeshes(parsed,descriptor){
 if(!descriptor)return{primitives:parsed.primitives,rotorAnimation:null};
 const normalization=parsed.normalization,fit=normalization?.fitScale,center=normalization?.center,hubsSource=descriptor.hubs_source_m;
 if(!Number.isFinite(fit)||fit<=0||!Array.isArray(center)||!Array.isArray(hubsSource)||hubsSource.length<1||hubsSource.some(hub=>!Array.isArray(hub)||hub.length!==3||!hub.every(Number.isFinite)))return{primitives:parsed.primitives,rotorAnimation:null};
 const hubs=hubsSource.map(hub=>hub.map((value,axis)=>(value-center[axis])*fit));
 const radiusMin=(descriptor.blade_radius_range_m?.[0]||0)*fit,radiusMax=(descriptor.blade_radius_range_m?.[1]||0)*fit;
 if(!(radiusMin>0&&radiusMax>radiusMin))return{primitives:parsed.primitives,rotorAnimation:null};
 if(Array.isArray(descriptor.node_name_groups)){
  const groups=descriptor.node_name_groups,triangleCounts=Array(hubs.length).fill(0),parts=parsed.primitives.map(primitive=>{
   const index=groups.findIndex(group=>Array.isArray(group)&&group.some(prefix=>typeof prefix==="string"&&primitive.nodeName?.startsWith(prefix)));
   if(index<0||index>=hubs.length)return primitive;
   triangleCounts[index]+=primitive.indices.length/3;
   return{...primitive,rotorIndex:index};
  });
  if(triangleCounts.some(count=>count<(descriptor.minimum_triangles_per_rotor||1)))return{primitives:parsed.primitives,rotorAnimation:null};
  return{primitives:parts,rotorAnimation:{axis:descriptor.axis,hubs,triangleCounts,bladeRadius:radiusMax,
   visualController:descriptor.visual_controller||null,visualIdleRpm:descriptor.visual_idle_rpm||0,
   visualMaxRpm:descriptor.visual_max_rpm||0,visualOnly:descriptor.visual_only===true}};
 }
 const regions=(descriptor.blade_regions||[]).map(region=>({...region,minY:(region.min_height_m-center[1])*fit,maxY:(region.max_height_m-center[1])*fit}));
 const parts=[],triangleCounts=Array(hubs.length).fill(0);
 for(const primitive of parsed.primitives){
  const staticIndices=[],rotorIndices=Array.from({length:hubs.length},()=>[]),indices=primitive.indices,positions=primitive.positions;
  for(let offset=0;offset+2<indices.length;offset+=3){
   const triangle=[indices[offset],indices[offset+1],indices[offset+2]],a=triangle[0]*3,b=triangle[1]*3,c=triangle[2]*3;
   const x=(positions[a]+positions[b]+positions[c])/3,y=(positions[a+1]+positions[b+1]+positions[c+1])/3,z=(positions[a+2]+positions[b+2]+positions[c+2])/3;
   let selected=-1,nearest=Infinity;
   for(const region of regions){
    if(primitive.materialIndex!==region.material_index||y<region.minY||y>region.maxY)continue;
    for(const rotorIndex of region.rotor_indices||[]){
     const hub=hubs[rotorIndex];if(!hub)continue;
     const radius=Math.hypot(x-hub[0],z-hub[2]);
     if(radius>=radiusMin&&radius<=radiusMax&&radius<nearest){selected=rotorIndex;nearest=radius}
    }
   }
   if(selected<0)staticIndices.push(...triangle);else{rotorIndices[selected].push(...triangle);triangleCounts[selected]++}
  }
  if(!rotorIndices.some(indices=>indices.length))parts.push(primitive);
  else{
   if(staticIndices.length)parts.push({...primitive,indices:staticIndices});
   rotorIndices.forEach((indices,rotorIndex)=>{if(indices.length)parts.push({...primitive,indices,rotorIndex})});
  }
 }
 const minimum=descriptor.minimum_triangles_per_rotor||1;
 if(triangleCounts.some(count=>count<minimum))return{primitives:parsed.primitives,rotorAnimation:null};
 return{primitives:parts,rotorAnimation:{axis:descriptor.axis,hubs,triangleCounts,bladeRadius:radiusMax}};
}
async function loadCatalogVehicle(model,kind){if(state.catalogVehicles[model.id])return state.catalogVehicles[model.id];if(state.catalogVehicleLoads[model.id])return state.catalogVehicleLoads[model.id];const useHighFidelity=deviceProfile.tier==="high"&&!!model.high_url&&!/(?:-orbit|-stage|-recovery)$/.test(model.id),modelUrl=useHighFidelity?model.high_url:model.url;const task=(async()=>{let geometries=[],textures=[];try{if(!gl)throw new Error("Il rendering 3D non è disponibile");let response=null;if("caches"in window){try{const cache=await caches.open("astra-visual-models-v1");response=await cache.match(modelUrl);if(!response){response=await fetch(modelUrl,{mode:"cors",credentials:"omit",cache:"force-cache"});if(!response.ok)throw new Error(`download HTTP ${response.status}`);await cache.put(modelUrl,response.clone()).catch(()=>{})}}catch(error){if(!response)throw error}}else{response=await fetch(modelUrl,{mode:"cors",credentials:"omit",cache:"force-cache"});if(!response.ok)throw new Error(`download HTTP ${response.status}`)}const data=await response.arrayBuffer();if(data.byteLength>40*1024*1024)throw new Error("GLB oltre 40 MB");const parsed=parseGlb(data,importLimits(useHighFidelity)),sourceBounds=model.id==="nasa-sls-block1"?visualVerticalBounds({primitives:parsed.primitives,visualBounds:{}},kind,model.orientation,2):null;if(model.id==="nasa-sls-block1")removeSlsLaunchStand(parsed);const split=splitCatalogRotorMeshes(parsed,model.rotor_animation),boundsProbe={primitives:parsed.primitives,visualBounds:{}};visualVerticalBounds(boundsProbe,kind,model.orientation);const cleanedBounds=boundsProbe.visualBounds[(model.orientation||"auto")+":2"],sourceSpan=sourceBounds?sourceBounds.maxByAxis[2]-sourceBounds.minByAxis[2]:0,cleanedSpan=sourceBounds?cleanedBounds.maxByAxis[2]-cleanedBounds.minByAxis[2]:0,visualScaleCorrection=sourceSpan>0&&cleanedSpan>0?sourceSpan/cleanedSpan:1;for(const image of parsed.images)textures.push(await createEmbeddedTexture(image));const primitives=split.primitives.map(primitive=>{const geometry=geo(primitive.positions,primitive.normals,primitive.uvs,primitive.indices);geometries.push(geometry);return{geometry,material:primitive.material,texture:primitive.material.textureIndex===null?null:textures[primitive.material.textureIndex],rotorIndex:primitive.rotorIndex}});if(primitives.some(x=>x.material.textureIndex!==null&&!x.texture))throw new Error("texture GLB non valida");const asset={name:model.name,kind,triangles:parsed.triangles,primitives,textures,model,visualBounds:boundsProbe.visualBounds,visualScaleCorrection,rotorAnimation:split.rotorAnimation};state.catalogVehicles[model.id]=asset;return asset}catch(error){geometries.forEach(disposeGeometry);textures.forEach(texture=>gl.deleteTexture(texture));state.visualModelError=model.id;state.visualModelErrorMessage=error.message||String(error);throw error}finally{delete state.catalogVehicleLoads[model.id];setVisualModelSummary()}})();state.catalogVehicleLoads[model.id]=task;setVisualModelSummary();return task}
function selectVisualModel(){const model=catalogModelFor();state.visualModelError=null;state.visualModelErrorMessage=null;setVisualModelSummary();if(!model)return;loadCatalogVehicle(model,state.kind).catch(error=>{console.warn("ASTRA visual model unavailable:",model.id,error);setVisualModelSummary()});if(state.kind==="space"){for(const [suffix,url,name] of [["orbit",model.orbit_url,"veicolo orbitale"],["recovery",model.recovery_url,"capsula rientro"]])if(url){const variant={...model,id:model.id+"-"+suffix,url,name:model.name+" · "+name};loadCatalogVehicle(variant,"space").catch(error=>{console.warn("ASTRA visual variant unavailable:",variant.id,error);setVisualModelSummary()})}}}
function updateImportUI(){const kind=$("#vehicleImportKind")?.value||state.kind,asset=state.userVehicles[kind];if(!$("#vehicleImportStatus"))return;$("#vehicleImportStatus").textContent=asset?`${asset.name} · ${kind==="drone"?"DRONE":kind==="aircraft"?"AEREO":"VEICOLO SPAZIALE"} · ${asset.triangles.toLocaleString("it-IT")} triangoli · SOLO GRAFICA`:`Nessun modello personale per ${kind==="drone"?"questo drone":kind==="aircraft"?"questo aereo":"questo veicolo spaziale"}. Il file resta sul dispositivo.`;$("#removeVehicle3d").hidden=!asset;$("#modelOrientationLabel").hidden=!asset;$("#vehicleModelOrientation").hidden=!asset;$("#vehicleModelOrientation").value=state.modelOrientations[kind]||"auto"}
async function importVehicleFile(file,kind){if(!file)return;if(!gl){toast("Il caricamento 3D richiede WebGL 2");return}if(!file.name.toLowerCase().endsWith(".glb")){toast("Carica un GLB 2.0 autonomo con texture incorporate");return}if(file.size>40*1024*1024){toast("File oltre 40 MB: riduci mesh o texture per questo dispositivo");return}$("#vehicleImportStatus").textContent="Lettura locale del modello…";let geometries=[],textures=[];try{const parsed=parseGlb(await file.arrayBuffer(),importLimits()),boundsProbe={primitives:parsed.primitives,visualBounds:{}};visualVerticalBounds(boundsProbe,kind,"auto");for(const image of parsed.images)textures.push(await createEmbeddedTexture(image));const primitives=parsed.primitives.map(primitive=>{const geometry=geo(primitive.positions,primitive.normals,primitive.uvs,primitive.indices);geometries.push(geometry);return{geometry,material:primitive.material,texture:primitive.material.textureIndex===null?null:textures[primitive.material.textureIndex]}});if(primitives.some(x=>x.material.textureIndex!==null&&!x.texture))throw new Error("Indice immagine texture non valido.");const next={name:file.name,kind,triangles:parsed.triangles,primitives,visualBounds:boundsProbe.visualBounds};const old=state.userVehicles[kind];if(old){old.primitives.forEach(x=>disposeGeometry(x.geometry));(old.textures||[]).forEach(t=>gl.deleteTexture(t))}next.textures=textures;state.userVehicles[kind]=next;state.kind=kind;$("#vehicleImportKind").value=kind;$(".domain[data-kind='"+kind+"']")?.click();updateImportUI();populateModelOptions();toast(`Modello caricato nell’ambiente ${kind==="drone"?"DRONE":kind==="aircraft"?"AEREO":"SPAZIO"}`)}catch(error){geometries.forEach(disposeGeometry);textures.forEach(gl.deleteTexture.bind(gl));updateImportUI();toast("Importazione non riuscita: "+(error.message||"GLB non leggibile"))}finally{$("#vehicleModelFile").value=""}}
function drawStars(){if(spaceSkyBlend<.015)return;gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);gl.depthMask(false);gl.useProgram(sp);gl.bindBuffer(gl.ARRAY_BUFFER,stars);let a=gl.getAttribLocation(sp,"aPos");gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,3,gl.FLOAT,false,0,0);gl.uniformMatrix4fv(gl.getUniformLocation(sp,"uView"),false,celestialView);gl.uniformMatrix4fv(gl.getUniformLocation(sp,"uProj"),false,projection);gl.uniform1f(gl.getUniformLocation(sp,"uOpacity"),spaceSkyBlend*.14);gl.drawArrays(gl.POINTS,0,starCount);gl.depthMask(true);gl.disable(gl.BLEND)}
function solid(x,y,z,sx,sy,sz,color,rot){drawMesh(cube,mul(T(x,y,z),mul(RY(rot||0),S(sx,sy,sz))),color,null,false)}
function line(points,color,opacity,key,revision=null){key=key||JSON.stringify(points);const signature=revision===null?JSON.stringify(points):String(revision);let g=lineCache.get(key);if(!g||g.signature!==signature){if(g){gl.deleteVertexArray(g.vao);gl.deleteBuffer(g.ib)}const pos=[],nor=[],uv=[],idx=[];points.forEach((v,i)=>{pos.push(...v);nor.push(0,1,0);uv.push(0,0);if(i)idx.push(i-1,i)});g=geo(pos,nor,uv,idx,gl.LINES);g.signature=signature;lineCache.set(key,g)}const alpha=Math.max(0,Math.min(1,Number.isFinite(opacity)?opacity:1)),rgba=color.length>3?[color[0],color[1],color[2],color[3]*alpha]:[color[0],color[1],color[2],alpha];gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(g,mat(),rgba,null,false,false,{alphaMode:"BLEND"});gl.disable(gl.BLEND);return opacity}
const GALACTIC_INVERSE_FRAME=new Float32Array([GALACTIC_FRAME[0],GALACTIC_FRAME[4],GALACTIC_FRAME[8],GALACTIC_FRAME[1],GALACTIC_FRAME[5],GALACTIC_FRAME[9],GALACTIC_FRAME[2],GALACTIC_FRAME[6],GALACTIC_FRAME[10]]);
function drawSky(transition=0){if(!skyProgram)return;const aspect=canvas.width/canvas.height,tan=Math.tan(sceneFovY*.5),right=[view[0],view[4],view[8]],up=[view[1],view[5],view[9]],forward=[-view[2],-view[6],-view[10]],rv=state.engine?.position_eci_m||[EARTH_RADIUS,0,0],atmosphereUp=state.kind==="space"&&!state.solarView?norm([rv[0],rv[2],rv[1]]):[0,1,0],reference=Math.abs(atmosphereUp[1])>.94?[0,0,1]:[0,1,0],atmosphereEast=norm(cross(reference,atmosphereUp)),atmosphereNorth=norm(cross(atmosphereUp,atmosphereEast));gl.disable(gl.DEPTH_TEST);gl.disable(gl.BLEND);gl.depthMask(false);gl.useProgram(skyProgram);const u=n=>gl.getUniformLocation(skyProgram,n);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,atmosphereSkyTex);gl.uniform1i(u("uAirTex"),0);gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,skyTex);gl.uniform1i(u("uSpaceTex"),1);gl.uniformMatrix3fv(u("uSkyRotation"),false,GALACTIC_INVERSE_FRAME);gl.uniform3fv(u("uRight"),right);gl.uniform3fv(u("uUp"),up);gl.uniform3fv(u("uForward"),forward);gl.uniform3fv(u("uAtmosphereUp"),atmosphereUp);gl.uniform3fv(u("uAtmosphereEast"),atmosphereEast);gl.uniform3fv(u("uAtmosphereNorth"),atmosphereNorth);gl.uniform1f(u("uAspect"),aspect);gl.uniform1f(u("uTanHalfFov"),tan);gl.uniform1f(u("uTransition"),transition);gl.bindVertexArray(null);gl.drawArrays(gl.TRIANGLES,0,3);gl.activeTexture(gl.TEXTURE0);gl.depthMask(true);gl.enable(gl.DEPTH_TEST)}
function hexRgb(value){const m=/^#([0-9a-f]{6})$/i.exec(value||"");if(!m)return[.7,.72,.78];const n=parseInt(m[1],16);return[(n>>16&255)/255,(n>>8&255)/255,(n&255)/255]}
function solarRadius(au){return .62+.88*Math.log10(1+au*4)}
function solarPosition(position){const r=Math.hypot(...position)||1,scale=solarRadius(r/AU)/r;return[position[0]*scale,position[2]*scale,position[1]*scale]}
function solarMoonPosition(body,parent){const pp=solarPosition(parent.position_heliocentric_m),rel=body.position_parent_relative_m||[body.semi_major_axis_m,0,0],a=body.semi_major_axis_m||Math.hypot(...rel),radius=.065+.018*Math.log10(1+a/1000),scale=radius/a;return[pp[0]+rel[0]*scale,pp[1]+rel[2]*scale,pp[2]+rel[1]*scale]}
function transferVehicleAsset(){const uploaded=state.userVehicles.space;if(uploaded)return{asset:uploaded,axis:null};const model=catalogModelFor("space");if(!model)return null;if(model.role==="modern-launcher"&&model.orbit_url){const orbital={...model,id:model.id+"-orbit",url:model.orbit_url,name:model.name+" · veicolo orbitale"};let asset=state.catalogVehicles[orbital.id];if(!asset&&!state.catalogVehicleLoads[orbital.id]&&state.visualModelError!==orbital.id)loadCatalogVehicle(orbital,"space").catch(()=>{});return asset?{asset,axis:model.orientation}:null}const asset=state.catalogVehicles[model.id];return asset?{asset,axis:model.orientation}:null}
function drawTransferSpacecraft(position,velocity){const visual=transferVehicleAsset();if(!visual)return false;const direction=velocity&&velocity.length===3&&velocity.every(Number.isFinite)?[velocity[0],velocity[2],velocity[1]]:[1,0,0],root=mul(T(...position),alignZ(direction));drawVehicleAsset(root,"space",visual.asset,.095,[0,0,0],visual.axis);return true}
function transferSample(progress){if(state.transferPosition)return state.transferPosition;const path=state.transferPlan?.trajectory_heliocentric_m;if(!path||path.length<2)return null;const f=Math.max(0,Math.min(1,progress))*(path.length-1),i=Math.min(path.length-2,Math.floor(f)),w=f-i;return path[i].map((v,k)=>v+(path[i+1][k]-v)*w)}
function transferVelocitySample(progress){if(state.transferVelocity)return state.transferVelocity;const path=state.transferPlan?.trajectory_velocity_heliocentric_m_s;if(!path||path.length<2)return null;const f=Math.max(0,Math.min(1,progress))*(path.length-1),i=Math.min(path.length-2,Math.floor(f)),w=f-i;return path[i].map((v,k)=>v+(path[i+1][k]-v)*w)}
function alignZ(direction){const z=norm(direction),reference=Math.abs(z[1])>.94?[0,0,1]:[0,1,0],x=norm(cross(reference,z)),y=norm(cross(z,x)),m=mat();m[0]=x[0];m[1]=x[1];m[2]=x[2];m[4]=y[0];m[5]=y[1];m[6]=y[2];m[8]=z[0];m[9]=z[1];m[10]=z[2];return m}
function renderSolarSystem(){spaceSkyBlend=1;drawSky(1);drawStars();const objects=state.celestial?.objects||[],lookup=Object.fromEntries(objects.map(o=>[o.id,o]));
 const orbitColor=[.35,.63,.82];
 for(const body of objects.filter(o=>o.class==="planet")){const semi=body.semi_major_axis_m/AU,rad=solarRadius(semi),path=[];for(let i=0;i<=180;i++){const a=i/180*Math.PI*2;path.push([rad*Math.cos(a),0,rad*Math.sin(a)])}line(path,orbitColor,.45,"solar-orbit-"+body.id)}
 const sun=lookup.sun;drawMesh(globe,mul(T(0,0,0),S(.24,.24,.24)),[1,.72,.35],null,false);gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(T(0,0,0),S(.34,.34,.34)),[1,.45,.14],null,true);gl.disable(gl.BLEND);gl.depthMask(true);
 for(const body of objects.filter(o=>o.class==="planet")){const pos=solarPosition(body.position_heliocentric_m),radius=Math.min(.15,Math.max(.065,.055+.023*Math.log10(body.radius_m/1e6))),surface=body.id==="earth"?earthTex:bodySurfaceTexture(body.id);drawMesh(globe,mul(T(...pos),mul(RY(state.seconds*.05),S(radius,radius,radius))),[1,1,1],surface,false);const airColor={venus:[.98,.62,.31],jupiter:[.93,.58,.34],saturn:[.94,.78,.55],uranus:[.36,.79,.77],neptune:[.31,.48,1]}[body.id];if(airColor){gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(T(...pos),S(radius*1.12,radius*1.12,radius*1.12)),[...airColor,.78],null,true);gl.disable(gl.BLEND);gl.depthMask(true)}if(body.id==="saturn"){const ring=[];for(let i=0;i<=120;i++){const a=i/120*Math.PI*2;ring.push([pos[0]+.23*Math.cos(a),pos[1]+.01,pos[2]+.23*Math.sin(a)])}line(ring,[.83,.72,.52],.8,"saturn-ring")}}
 for(const body of objects.filter(o=>o.class==="moon")){const parent=lookup[body.parent_id];if(!parent)continue;const pos=solarMoonPosition(body,parent),size=Math.min(.052,Math.max(.022,.018+.012*Math.log10(body.radius_m/1000)));drawMesh(globe,mul(T(...pos),S(size,size,size)),[1,1,1],bodySurfaceTexture(body.id),false)}
 const trajectory=state.transferPlan?.trajectory_heliocentric_m;if(trajectory?.length>1){const path=trajectory.map(solarPosition);line(path,[.23,.92,1],1,"planned-transfer-arc");for(const end of [path[0],path[path.length-1]]){gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(T(...end),S(.045,.045,.045)),[.34,.96,1],null,true);gl.disable(gl.BLEND);gl.depthMask(true)}}
 const transferPosition=transferSample(state.transferProgress);if(transferPosition){const craft=solarPosition(transferPosition),velocity=transferVelocitySample(state.transferProgress),path=state.transferPlan.trajectory_heliocentric_m,segment=Math.floor(state.transferProgress*(path.length-1)),flown=path.slice(0,segment+1);if(segment<path.length-1)flown.push(transferPosition);if(flown.length>1)line(flown.map(solarPosition),[.28,1,.72],1,"planned-transfer-progress");if(!drawTransferSpacecraft(craft,velocity)){gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(T(...craft),S(.035,.035,.035)),[.55,.97,1],null,true);drawMesh(globe,mul(T(...craft),S(.07,.07,.07)),[.18,.66,1,.38],null,true);gl.disable(gl.BLEND);gl.depthMask(true)}}const selected=lookup[state.selectedBodyId];if(selected){const pos=selected.class==="moon"?solarMoonPosition(selected,lookup[selected.parent_id]):solarPosition(selected.position_heliocentric_m);const r=selected.class==="moon"?.075:.20;gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);drawMesh(globe,mul(T(...pos),S(r,r,r)),[.39,.88,1],null,true);gl.disable(gl.BLEND);gl.depthMask(true)}
}
let leoOrbitTime=-1,leoOrbitPoints=null;
function osculatingOrbitPath(engine,center,scale){if(!engine||engine.time_s===leoOrbitTime)return leoOrbitPoints;leoOrbitTime=engine.time_s;leoOrbitPoints=null;const r=engine.position_eci_m,v=engine.velocity_eci_m_s;if(!r||!v)return null;const rn=Math.hypot(...r),h=cross(r,v),hn=Math.hypot(...h),energy=.5*v.reduce((sum,value)=>sum+value*value,0)-3.986004418e14/rn;if(energy>=0||hn===0)return null;const evec=cross(v,h).map((value,i)=>value/3.986004418e14-r[i]/rn),ecc=Math.hypot(...evec);if(ecc>=1)return null;const a=-3.986004418e14/(2*energy),p=a*(1-ecc*ecc),ehat=ecc>1e-8?norm(evec):norm(r),hhat=norm(h),qhat=norm(cross(hhat,ehat)),points=[];for(let i=0;i<=120;i++){const nu=2*Math.PI*i/120,rad=p/(1+ecc*Math.cos(nu)),x=rad*(Math.cos(nu)*ehat[0]+Math.sin(nu)*qhat[0]),y=rad*(Math.cos(nu)*ehat[1]+Math.sin(nu)*qhat[1]),z=rad*(Math.cos(nu)*ehat[2]+Math.sin(nu)*qhat[2]);points.push([center[0]+x*scale,center[1]+z*scale,center[2]+y*scale])}leoOrbitPoints=points;return points}
// The stack sits on the deck beside the mobile tower, with its base 14.3 m above grade.
const launchSiteModel={id:"nasa-mobile-launcher",name:"NASA Artemis Mobile Launcher",url:"assets/vehicles/nasa-mobile-launcher.glb?v=2",source:"NASA 3D Resources · Mobile Launcher",source_url:"https://www.nasa.gov/humans-in-space/exploration-ground-systems/mobile-launcher/",license:"NASA Usage Guidelines",orientation:"y",scale:115.8*EARTH_RENDER_SCALE/1.8,padOffset_m:[0,.35,0],vehicleOffset_m:[-14,14.65,0],initialVehicleAltitude_m:1.5};
function launchSiteSceneFrame(seconds=0){const lat=state.launchSiteGeo.latitude,lon=state.launchSiteGeo.longitude+seconds*EARTH_ROTATION_RATE,radial=[Math.cos(lat)*Math.cos(lon),Math.sin(lat),Math.cos(lat)*Math.sin(lon)],frame=alignY(radial),position=[-1.8+EARTH_RENDER_RADIUS*radial[0],-.5+EARTH_RENDER_RADIUS*radial[1],EARTH_RENDER_RADIUS*radial[2]];return{radial,frame,position}}
function launchSiteVisualOffset(seconds,blend=1){const {radial,frame}=launchSiteSceneFrame(seconds),scale=EARTH_RENDER_SCALE*blend,[x,y,z]=launchSiteModel.vehicleOffset_m,local=[x,y-launchSiteModel.initialVehicleAltitude_m,z].map(value=>value*scale);return[frame[0]*local[0]+frame[4]*local[1]+frame[8]*local[2],frame[1]*local[0]+frame[5]*local[1]+frame[9]*local[2],frame[2]*local[0]+frame[6]*local[1]+frame[10]*local[2]]}
function drawLaunchSite(seconds,lightDir){
 const {frame,position:sitePosition}=launchSiteSceneFrame(seconds),site=mul(T(...sitePosition),frame);
 const earthSurface=mul(T(-1.8,-.5,0),mul(RY(-seconds*EARTH_ROTATION_RATE),S(EARTH_RENDER_RADIUS,EARTH_RENDER_RADIUS,EARTH_RENDER_RADIUS)));
 const groundGeometry=launchGroundTex?launchSurfaceGeo:launchSurfaceFallbackGeo,groundTexture=launchGroundTex||earthTex;if(groundGeometry)drawMesh(groundGeometry,earthSurface,[1,1,1],groundTexture,false,false,launchGroundTex?{alphaMode:"BLEND"}:null,lightDir,true);if(launchGroundNearTex&&launchSurfaceNearGeo){gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(-1,-1);drawMesh(launchSurfaceNearGeo,earthSurface,[1,1,1],launchGroundNearTex,false,false,{alphaMode:"BLEND"},lightDir,true);gl.disable(gl.POLYGON_OFFSET_FILL)}
 // A concrete pad and crawlerway make the spherical Earth surface read at launch scale.
 const earthScale=EARTH_RENDER_SCALE,padY=launchSiteModel.padOffset_m[1]*earthScale;
 drawMesh(panelMesh,mul(site,mul(T(0,padY,0),S(68*earthScale,1,70*earthScale))),[.30,.32,.33],null,false,false,null,lightDir);
 drawMesh(panelMesh,mul(site,mul(T(0,padY+.002*earthScale,190*earthScale),S(19*earthScale,1,145*earthScale))),[.23,.26,.27],null,false,false,null,lightDir);
 for(const side of [-1,1])drawMesh(cube,mul(site,mul(T(side*11*earthScale,padY+.004*earthScale,190*earthScale),S(.16*earthScale,.002*earthScale,145*earthScale))),[.72,.69,.54],null,false,false,null,lightDir);
 for(const side of [-1,1]){
  const edge=61*earthScale,markY=padY+.012*earthScale;
  drawMesh(cube,mul(site,mul(T(0,markY,side*edge),S(61*earthScale,.003*earthScale,.14*earthScale))),[.82,.76,.58],null,false,false,null,lightDir);
  drawMesh(cube,mul(site,mul(T(side*edge,markY,0),S(.14*earthScale,.003*earthScale,61*earthScale))),[.82,.76,.58],null,false,false,null,lightDir);
 }
 // The pre-made SLS stack sits on the Mobile Launcher deck at its authored vehicle position.
  const padOffset=launchSiteModel.padOffset_m.map(value=>value*EARTH_RENDER_SCALE),launcher=mul(site,T(...padOffset));
 let asset=state.catalogVehicles[launchSiteModel.id];
 if(!asset&&!state.catalogVehicleLoads[launchSiteModel.id]&&state.visualModelError!==launchSiteModel.id)loadCatalogVehicle(launchSiteModel,"space").catch(error=>console.warn("ASTRA launch-site model unavailable:",error));
 if(asset)drawVehicleAsset(launcher,"space",asset,launchSiteModel.scale,[0,0,0],launchSiteModel.orientation,true,1);
}
function renderSpace(t){if(state.solarView){renderSolarSystem();return}const altitude=Math.max(0,state.engine?.altitude_m||0);spaceSkyBlend=Math.max(0,Math.min(1,(altitude-12000)/68000));drawSky(spaceSkyBlend);drawStars();const center=[-1.8,-.5,0],earthScale=EARTH_RENDER_RADIUS/EARTH_RADIUS,orbitRadius=(EARTH_RADIUS+420000)*earthScale,rv=state.engine?.position_eci_m||[EARTH_RADIUS,0,0];const earthTransform=mul(T(...center),mul(RY(-state.seconds*EARTH_ROTATION_RATE),S(EARTH_RENDER_RADIUS,EARTH_RENDER_RADIUS,EARTH_RENDER_RADIUS))),orbitalScene=state.engine?.scenario==="orbital",sunLat=orbitalScene?0:state.launchSiteGeo.latitude,sunLon=orbitalScene?0:state.launchSiteGeo.longitude,earthLight=[Math.cos(sunLat)*Math.cos(sunLon),Math.sin(sunLat),Math.cos(sunLat)*Math.sin(sunLon)];
 // Sunlight stays fixed in the inertial scene frame; the rotating Earth moves
 // its day/night terminator over the full global texture instead of lighting
 // only the vehicle's current subpoint.
 // Keep the complete global globe visible at every altitude. The close-range
 // mesh adds tessellation detail around the tracked subpoint; it must never
 // replace the sphere, or its limited geographic footprint looks like a tiny
 // texture pasted onto an otherwise bare Earth.
 drawMesh(globe,earthTransform,[1,1,1],earthTex,false,false,null,earthLight,true);
 
 // Keep the atmospheric limb optically thin. A wide, opaque shell sits in
 // front of the globe and makes the mapped surface look like a small inset.
 gl.depthMask(false);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);const atmosphereRadius=EARTH_RENDER_RADIUS+45000*earthScale;drawMesh(globe,mul(T(...center),S(atmosphereRadius,atmosphereRadius,atmosphereRadius)),[.25,.65,1,.28],null,true);gl.disable(gl.BLEND);gl.depthMask(true);if(state.engine?.scenario!=="orbital"&&altitude<40000)drawLaunchSite(state.seconds,earthLight);
 if(state.engine?.scenario==="orbital") {const path=[];for(let i=0;i<=360;i++){const a=i*Math.PI/180;path.push([center[0]+orbitRadius*Math.cos(a),center[1],center[2]+orbitRadius*Math.sin(a)])}line(path,[.27,.67,.59],.7,"orbit-path")}else if(state.engine?.scenario==="leo-return"){const path=osculatingOrbitPath(state.engine,center,earthScale);if(path)line(path,[.31,.88,.72],.72,"leo-osculating-orbit");}
 const x=center[0]+rv[0]*earthScale,y=center[1]+rv[2]*earthScale,z=center[2]+rv[1]*earthScale,longitude=Math.atan2(rv[1],rv[0]);
 if(state.engine?.scenario==="orbital") {drawSatellite(x,y,z,-longitude,state.engine.attitude_quaternion_body_to_eci);const target=state.engine.target_position_eci_m||[EARTH_RADIUS+420000,0,0],tx=center[0]+target[0]*earthScale,ty=center[1]+target[2]*earthScale,tz=center[2]+target[1]*earthScale,targetLongitude=Math.atan2(target[1],target[0]);drawStation(tx,ty,tz,-targetLongitude)}
 else{const e=state.engine||{},radial=norm([rv[0],rv[1],rv[2]]),v=e.velocity_eci_m_s||[0,0,0],speed=Math.hypot(...v),velocity=speed>1?norm(v):radial,tangent=norm(v.map((value,i)=>value-radial[i]*v.reduce((sum,item,j)=>sum+item*radial[j],0))),pitch=(e.attitude_guidance_command_deg?.[0]??90)*Math.PI/180,crossrange=(e.attitude_guidance_command_deg?.[1]??0)*Math.PI/180,commandDirection=norm(radial.map((value,i)=>value*Math.sin(pitch)+tangent[i]*Math.cos(pitch))),fallbackDirection=norm(commandDirection.map((value,i)=>value*Math.cos(crossrange)+(i===2?Math.sin(crossrange):0)));drawLauncher(x,y,z,[fallbackDirection[0],fallbackDirection[2],fallbackDirection[1]],e)}
}
function drawAirportDetails(t){
 // Apron, taxiway and low airport buildings stay anchored to the threshold.
 solid(5.9,.008,-1.85,2.6,.008,.68,[.29,.34,.35],0);
 for(let i=0;i<7;i++)solid(4.9+i*.32,.019,-1.85,.11,.002,.018,[.72,.71,.58],0);
 // Low airport hangars, glass-front operations room, apron and windsock.
 solid(-12,.025,-16.0,2.55,.025,1.55,[.23,.29,.31],0);
 solid(12,.025,-16.2,2.55,.025,1.65,[.23,.29,.31],0);
 solid(-12,.62,-16.05,2.0,.58,1.22,[.47,.53,.54],0);
 solid(12,.64,-16.25,2.05,.60,1.3,[.42,.49,.52],0);
 solid(-12,1.215,-16.05,2.10,.055,1.34,[.24,.30,.33],0);
 solid(12,1.235,-16.25,2.16,.055,1.42,[.22,.29,.33],0);
 for(const x of [-12,12]){
  const z=x<0?-14.81:-14.89;
  for(let bay=-1;bay<=1;bay++)solid(x+bay*.61,.55,z,.48,.36,.014,[.19,.37,.43],0);
  solid(x,1.305,z,.36,.018,.024,[.72,.77,.76],0);
 }
 solid(-14,.22,-4.0,.012,.22,.012,[.65,.68,.63],0);
 drawMesh(globe,mul(T(-14,.48,-4.0),mul(RZ(-.25),S(.15,.04,.04))),[.96,.43,.23],null,false);
 // Low wetland scrub sits beyond the approach area; no oversized trees intrude
 // into the runway sightline. The small clusters keep the flat coastal horizon legible.
 for(let i=0;i<10;i++)for(const side of [-1,1]){
  const x=terrainTileX-80+i*(160/9),z=terrainTileZ+side*(34+(i%3)*2.5),ground=terrainHeight(x,z)+2.07;
  const color=side>0?[.25,.36,.25]:[.29,.39,.27];
  drawMesh(globe,mul(T(x,ground+.14,z),S(.34,.16,.29)),color,null,false);
  if(i%2===0)drawMesh(globe,mul(T(x+.35,ground+.12,z+.22),S(.24,.13,.23)),[.33,.40,.28],null,false);
 }
}
function renderAir(t){spaceSkyBlend=0;const terrainKey=state.kind==="aircraft"?"terrain-aircraft":"terrain-drone";terrainTextureCache[terrainKey]??=groundTexture(terrainKey);const activeTerrainTex=terrainTextureCache[terrainKey];asphaltTex??=groundTexture("asphalt");drawSky(0);const terrainFocus=airVisualPosition();updateTerrainTile(terrainFocus[0],terrainFocus[2]);for(const tile of terrainOuterTiles)drawMesh(tile.mesh,T(tile.x,2.07,tile.z),[.82,.91,.87],activeTerrainTex,false);drawMesh(terrainGeo,T(terrainTileX,2.07,terrainTileZ),[.84,.93,.88],activeTerrainTex,false);
 const e=state.engine||{},att=e.attitude_deg||[0,0,0],visual=airVisualPosition(),x=visual[0],y=visual[1],z=visual[2],phi=att[0]*Math.PI/180,theta=att[1]*Math.PI/180,psi=att[2]*Math.PI/180,poseRoot=mul(T(x,y,z),aircraftPoseMatrix(phi,theta,psi));
 // The aircraft uses a 3 km runway; the multirotor starts from its own VTOL pad.
 if(state.kind==="aircraft"){
  const runwayCenter=AIRFIELD_RUNWAY_START_WORLD+AIRFIELD_RUNWAY_LENGTH_WORLD*.5;
  drawMesh(cube,mul(T(runwayCenter,AIR_RUNWAY_HALF_THICKNESS,0),S(AIRFIELD_RUNWAY_LENGTH_WORLD*.5,AIR_RUNWAY_HALF_THICKNESS,AIRFIELD_RUNWAY_WIDTH_WORLD*.5)),[.42,.47,.49],asphaltTex,false);
  drawMesh(runwayMarkingsGeo,mat(),[.88,.87,.77],null,false);
 }else drawDronePad();
 drawAirportDetails(t);
 solid(10,.025,-4.8,.72,.025,.54,[.19,.23,.22],.32);solid(10,.16,-4.8,.18,.16,.16,[.72,.74,.68],.32);
 const altitude=Math.max(0,e.altitude_m||0),shadowOpacity=.58*Math.max(0,1-altitude/18);
 if(shadowOpacity>.01){const aircraft=state.kind==="aircraft",sx=aircraft?1.25:.62,sz=aircraft?.62:.48;
  const shadow=mul(T(x,AIR_RUNWAY_TOP+.002,z),mul(RY(psi),S(sx,1,sz)));
  drawMesh(panelMesh,shadow,[1,1,1,shadowOpacity],shadowTex,false,false,{alphaMode:"BLEND"});}
 if(flightTrace.length>=2)line(flightTrace,[.18,.86,.95],.82,"air-flight-path",flightTraceRevision);
  const grounded=altitude<.35;
  if(state.userVehicles[state.kind])drawImportedVehicle(poseRoot,state.kind,grounded);
  else{const asset=catalogVehicleFor(state.kind),model=catalogModelFor(state.kind);if(asset&&model)drawVehicleAsset(poseRoot,state.kind,asset,model.scale??visualScale(state.kind),[0,0,0],model.orientation,grounded,1)}
}
function renderCompat(t){if(!ctx2d)return;const c=ctx2d,w=host.clientWidth,h=host.clientHeight,e=state.engine||{},time=t*.001;c.clearRect(0,0,w,h);const sky=c.createLinearGradient(0,0,0,h);sky.addColorStop(0,"#030a14");sky.addColorStop(.62,"#102336");sky.addColorStop(1,"#101d24");c.fillStyle=sky;c.fillRect(0,0,w,h);for(let i=0;i<72;i++){const x=(i*7919%997)/997*w,y=(i*3571%613)/613*h*.58;c.fillStyle=`rgba(210,235,255,${.25+(i%5)*.12})`;c.fillRect(x,y,1.4,1.4)}
 if(state.kind==="space"){const r=Math.max(w*.44,h*.66),cx=w*.48,cy=h*1.08;c.beginPath();c.arc(cx,cy,r,Math.PI*1.12,Math.PI*1.88);c.closePath();const earth=c.createLinearGradient(0,cy-r,0,h);earth.addColorStop(0,"#3984a0");earth.addColorStop(.25,"#174c68");earth.addColorStop(1,"#071d33");c.fillStyle=earth;c.fill();c.beginPath();c.arc(cx,cy,r,Math.PI*1.12,Math.PI*1.88);c.strokeStyle="#83d6f3";c.lineWidth=3;c.stroke();c.fillStyle="#bce8ff";c.font="11px ui-monospace,monospace";c.fillText("TERRA · RIENTRO SUBORBITALE",20,h-24);const altitude=e.altitude_m||0,vy=Math.max(50,h*.24-Math.min(h*.14,altitude/30000));const axis=e.body_axis_z_eci||[0,0,1],rv=e.position_eci_m||[1,0,0],vel=e.velocity_eci_m_s||[0,1,0],radial=rv.map(v=>v/(Math.hypot(...rv)||1)),radialSpeed=vel.reduce((sum,v,i)=>sum+v*radial[i],0),tangent=norm(vel.map((v,i)=>v-radialSpeed*radial[i])),pitch=Math.atan2(axis.reduce((sum,v,i)=>sum+v*tangent[i],0),axis.reduce((sum,v,i)=>sum+v*radial[i],0));c.save();c.translate(w*.55,vy);c.rotate(pitch);c.fillStyle="#d9e3df";c.beginPath();c.moveTo(0,-18);c.lineTo(8,12);c.lineTo(0,9);c.lineTo(-8,12);c.closePath();c.fill();if(e.phase==="ASCENT"){c.fillStyle="#ff9c54";c.beginPath();c.moveTo(-4,10);c.lineTo(0,26+Math.sin(time*20)*4);c.lineTo(4,10);c.fill()}if(e.phase==="PARACHUTE"||e.phase==="DROGUE"){c.strokeStyle="#f1d9a7";c.beginPath();c.arc(0,-34,e.phase==="DROGUE"?18:32,Math.PI,Math.PI*2);c.stroke();c.beginPath();c.moveTo(-32,-34);c.lineTo(-5,-6);c.moveTo(32,-34);c.lineTo(5,-6);c.stroke()}c.restore()}
 else{c.fillStyle="#233a31";c.beginPath();c.moveTo(0,h*.59);for(let x=0;x<=w;x+=8)c.lineTo(x,h*.59+Math.sin(x*.009)*16+Math.sin(x*.025)*7);c.lineTo(w,h);c.lineTo(0,h);c.fill();c.fillStyle="#303d40";c.beginPath();c.moveTo(w*.39,h);c.lineTo(w*.47,h*.61);c.lineTo(w*.53,h*.61);c.lineTo(w*.62,h);c.fill();c.strokeStyle="#d3d3b8";c.setLineDash([15,12]);c.beginPath();c.moveTo(w*.5,h);c.lineTo(w*.5,h*.62);c.stroke();c.setLineDash([]);const alt=e.altitude_m||0,x=w*.5+(e.position_ned_m?.[0]||0)*.015,y=Math.max(h*.36,h*.62-Math.min(h*.24,alt*.025));c.save();c.translate(x,y);c.rotate(-(e.attitude_deg?.[1]||0)*Math.PI/180);c.fillStyle=state.kind==="aircraft"?"#a8c5c4":"#a4d5c6";if(state.kind==="aircraft"){c.beginPath();c.moveTo(25,0);c.lineTo(-18,-5);c.lineTo(-7,0);c.lineTo(-18,5);c.closePath();c.fill();c.fillRect(-4,-13,8,26)}else{c.strokeStyle="#a9c1ba";c.lineWidth=4;for(const a of [[-18,-14],[18,-14],[-18,14],[18,14]]){c.beginPath();c.moveTo(0,0);c.lineTo(...a);c.stroke();c.beginPath();c.arc(a[0],a[1],5,0,time*8);c.stroke()}c.fillStyle="#d4e7dd";c.fillRect(-7,-6,14,12)}c.restore()}
 c.fillStyle="#c3ddd8";c.font="10px ui-monospace,monospace";c.fillText("RENDERER COMPATIBILE · 2D",w-205,h-18);c.fillStyle="#90a6af";c.fillText(`${deviceProfile.tier.toUpperCase()} · ${Math.round(deviceProfile.targetFps)} FPS · ALT ${(e.altitude_m||0).toFixed(0)} m`,20,28)}
async function api(path,payload){return browserApi(path,payload)}
function updateMissionBadge(){const e=state.engine||{},label=e.phase==="LANDED"?"MISSIONE COMPLETATA":e.phase==="CRASHED"?"MISSIONE TERMINATA":e.phase==="ABORTED"?"SIMULAZIONE ARRESTATA":state.running?"MISSIONE IN CORSO":e.mission_started?"MISSIONE IN PAUSA":"MISSIONE PRONTA";const el=$("#missionStatusLabel");if(el&&el.textContent!==label)el.textContent=label}
const phaseText={READY:"PRONTO AL LANCIO",RENDEZVOUS:"AVVICINAMENTO ALLA STAZIONE",STATION_KEEPING:"MANTENIMENTO A 20 M",ASCENT:"SALITA PROPULSA",COAST:"FASE COAST",COAST_TO_APOGEE:"COAST VERSO L’APOGEO",CIRCULARIZE:"CIRCOLARIZZAZIONE LEO",ORBIT_COAST:"ORBITA LEO · UN GIRO",DEORBIT_ALIGN:"ALLINEAMENTO RETROGRADO",DEORBIT_BURN:"MANOVRA DI DEORBITA",DEORBIT_COAST:"TRASFERIMENTO DI RIENTRO",REENTRY:"RIENTRO ATMOSFERICO",AEROSHELL:"SCUDO FRENANTE",DROGUE:"PARACADUTE GUIDA",PARACHUTE:"PARACADUTE PRINCIPALE",TAKEOFF:"DECOLLO",CLIMB:"SALITA",CRUISE:"CIRCUITO E RIENTRO",EMERGENCY_GLIDE:"PLANATA DI EMERGENZA",APPROACH:"AVVICINAMENTO ALLA PISTA",LANDING:"ATTERRAGGIO",ROLLOUT:"CORSA DI ARRESTO",INSPECT:"ISPEZIONE",RETURN:"RIENTRO",LANDED:"MISSIONE COMPLETATA",CRASHED:"IMPATTO NON SICURO",ABORTED:"SIMULAZIONE ARRESTATA"};
function calculateVehicleDesign(stages){
 const p=state.vehicleParts?.parts,c=state.vehicleParts?.configuration;
 if(!p||!c||!Array.isArray(stages)||!stages.length)return null;
 const stageSpecs=stages.map((stage,index)=>{
  const tanks=Number(stage.tank_count),engines=Number(stage.engine_count);
  if(!Number.isInteger(tanks)||tanks<(c.min_tanks??1)||tanks>(c.max_tanks??3)||!Number.isInteger(engines)||engines<(c.min_engines??1)||engines>(c.max_engines??8))return null;
  const dry=tanks*p.tank.dry_mass_kg+engines*p.engine.dry_mass_kg,fuel=tanks*p.tank.propellant_capacity_kg;
  const thrust=engines*p.engine.thrust_vacuum_N,area=engines*p.engine.nozzle_exit_area_m2;
  return{stage:index+1,tank_count:tanks,engine_count:engines,dry_mass_kg:dry,propellant_capacity_kg:fuel,thrust_vacuum_N:thrust,nozzle_exit_area_m2:area,isp_vacuum_s:p.engine.isp_vacuum_s,thrust_sea_level_N:engines*Math.max(0,p.engine.thrust_vacuum_N-c.sea_level_pressure_Pa*p.engine.nozzle_exit_area_m2)}
 });
 if(stageSpecs.some(stage=>!stage))return null;
 const dry=p.capsule.dry_mass_kg+stageSpecs.reduce((sum,x)=>sum+x.dry_mass_kg,0),fuel=stageSpecs.reduce((sum,x)=>sum+x.propellant_capacity_kg,0),acs=fuel*(c.acs_propellant_fraction_of_main_propellant??0),wet=dry+fuel+acs;
 let mass=wet,deltaV=0;
 for(const stage of stageSpecs){stage.wet_mass_at_ignition_kg=mass;stage.twr_at_sea_level=stage.thrust_sea_level_N/(mass*c.standard_gravity_m_s2);const afterBurn=mass-stage.propellant_capacity_kg;if(afterBurn<=stage.dry_mass_kg)return null;deltaV+=stage.isp_vacuum_s*c.standard_gravity_m_s2*Math.log(mass/afterBurn);mass=afterBurn-stage.dry_mass_kg}
 return{dry,fuel,acs,wet,thrust:stageSpecs[0].thrust_vacuum_N,thrustAtSeaLevel:stageSpecs[0].thrust_sea_level_N,twr:stageSpecs[0].twr_at_sea_level,stageTwr:stageSpecs.map(x=>x.twr_at_sea_level),deltaV,stages:stageSpecs}
}
function leoReturnAvailable(stages=state.customDesign.stages){const design=calculateVehicleDesign(stages);return !!design&&design.deltaV>=9200&&Math.min(...design.stageTwr)>=1.1}
function updateMissionProfileUI(){
 const select=$("#missionProfile");if(!select)return;
 const leo=select.querySelector('[value="leo-return"]'),orbital=select.querySelector('[value="orbital"]'),available=state.kind==="space"&&state.modelId==="astra-custom-stack"&&leoReturnAvailable();
 leo.disabled=!available;leo.textContent=available?"ORBITA LEO · UN GIRO · RIENTRO":"ORBITA LEO · STACK ≥ 9,2 KM/S";
 orbital.disabled=state.kind!=="space";
 if(state.missionProfile==="orbital"&&state.modelId==="astra-custom-stack"){
  state.modelId=defaultModels.space;state.modelPreferences.space=state.modelId;
  localStorage.setItem("astra-model-selection-v1",JSON.stringify(state.modelPreferences));
  populateModelOptions();
 }
 if(state.missionProfile==="leo-return"&&!available){state.missionProfile="mission";localStorage.setItem("astra-mission-profile-v1","mission");}
 select.value=state.missionProfile;select.hidden=state.kind!=="space";
 $("#missionProfileHelp").textContent=state.missionProfile==="orbital"
  ?"Rendezvous automatico in ECI/LVLH con guida Clohessy–Wiltshire, assetto quaternion e ruote di reazione; punto di mantenimento a 20 m."
  :available?(state.missionProfile==="leo-return"?"Lancio, circolarizzazione all’apogeo, un’orbita completa, manovra di deorbita e recupero. Il riscaldamento aerotermico non è modellato.":"Il profilo completo LEO è disponibile; le perdite, le manovre e la riserva vengono calcolate durante il volo."):"Per sbloccare la missione LEO, assembla uno stack con Δv ideale ≥ 9,2 km/s e T/W ≥ 1,1 su ogni stadio.";
}
function updateMissionPresentation(scenario=state.kind==="space"?state.missionProfile:"mission"){
 const leo=scenario==="leo-return",orbital=scenario==="orbital",a=info[state.kind];
 const scenarioLabel=leo?"LANCIO · ORBITA LEO · RIENTRO":orbital?"RENDEZVOUS · AVVICINAMENTO LVLH":state.kind==="space"?"LANCIO · RIENTRO SUBORBITALE":a[7];
 const missionLabel=leo?"ORBITA · DEORBITA · ATTERRAGGIO":orbital?"STAZIONE · HOLD 20 M":state.kind==="space"?"LANCIO E RECUPERO":a[3];
 if($("#scenario")?.firstChild)$("#scenario").firstChild.textContent=scenarioLabel+" ";
 if($("#mission")?.firstChild)$("#mission").firstChild.textContent=missionLabel+" ";
 if($("#heroTitle"))$("#heroTitle").textContent=leo?"Missione LEO completa":orbital?"Rendezvous in orbita bassa":a[0];
 if($("#heroSub"))$("#heroSub").textContent=leo?"LANCIO · INSERZIONE · UN’ORBITA · DEORBITA · ATTERRAGGIO":orbital?"NAVIGAZIONE RELATIVA · CORRIDOIO · HOLD 20 M":a[1];
 updateMissionProfileUI();
}
function populateModelOptions(){
 const select=$("#vehicleModel");if(!select)return;
 $("#openVehicleLab").hidden=state.kind!=="space"||state.missionProfile==="orbital";
 const catalogOptions={...(state.catalog?.[state.kind]||fallbackModels[state.kind])};
 const options=state.kind==="space"?(state.missionProfile==="orbital"
  ?{"astra-leo-servicer":catalogOptions["astra-leo-servicer"]||fallbackModels.space["astra-leo-servicer"]}
  :Object.fromEntries(Object.entries(catalogOptions).filter(([id])=>id!=="astra-leo-servicer"))):catalogOptions;
 const design=state.kind==="space"&&state.missionProfile!=="orbital"?calculateVehicleDesign(state.customDesign.stages):null;
 if(state.kind==="space"&&state.missionProfile!=="orbital"&&state.customDesign){const stages=state.customDesign.stages||[],tanks=stages.reduce((sum,x)=>sum+x.tank_count,0),engines=stages.reduce((sum,x)=>sum+x.engine_count,0);options["astra-custom-stack"]={name:state.customDesign.name+` · ASTRA ${stages.length} stadi`,summary:`Vehicle Lab · ${stages.length} stadi · ${tanks} serbatoi · ${engines} motori · separazione automatica.`}}
 const key=state.kind+":"+Object.keys(options).join("|")+":"+(state.kind==="space"?state.customDesign.name+"/"+JSON.stringify(state.customDesign.stages):"");
 if(select.dataset.catalogKey!==key){select.replaceChildren();Object.entries(options).forEach(([id,model])=>{const option=document.createElement("option");option.value=id;option.textContent=model.name;select.append(option)});select.dataset.catalogKey=key}
 if(!options[state.modelId])state.modelId=defaultModels[state.kind];if(select.value!==state.modelId)select.value=state.modelId;
 const personal=state.userVehicles[state.kind],designSummary=design?` · Δv ideale ${(design.deltaV/1000).toFixed(2)} km/s · ACS ${design.acs.toFixed(0)} kg`:"";
 const stageButton=$("#stageNow"),flight=state.engine||{},stageCount=flight.stage_count||0,activeStage=flight.active_stage||0;
 if(stageButton){stageButton.hidden=state.kind!=="space"||state.modelId!=="astra-custom-stack"||stageCount<2;stageButton.disabled=!(flight.mission_started&&flight.phase==="ASCENT"&&activeStage>0&&activeStage<stageCount)}
 $("#modelSummary").textContent=(options[state.modelId]?.summary||"Modello 3D e parametri fisici selezionati.")+designSummary+(personal?` · Grafica personale: ${personal.name}. Parametri e dinamica restano quelli del modello ASTRA selezionato.`:"");updateMissionProfileUI()
}
function updateLesson(){const phase=state.engine?.phase||"READY",entry=lessons[state.kind]?.[phase]||lessons[state.kind]?.READY;if(!entry)return;$("#lessonTitle").textContent=entry[0];$("#lessonText").textContent=entry[1];$("#lessonWhy").textContent=entry[2]}
function persistCareer(){try{localStorage.setItem("astra-career-v1",JSON.stringify(campaign))}catch{}}
function rankFor(track){const ladder=rankLadders[track],xp=campaign.xp[track]||0;let index=0;for(let i=0;i<ladder.length;i++)if(xp>=ladder[i][0])index=i;return{current:ladder[index],next:ladder[index+1]||null}}
function careerMetrics(){return state.engine?.mission_metrics||{max_altitude_m:0,max_dynamic_pressure_Pa:0,touchdown_speed_m_s:null}}
function careerObjectives(){const e=state.engine||{},m=careerMetrics(),g=careerGoals[state.kind],launched=!!e.mission_started,target=(m.max_altitude_m||0)>=g.altitude,landed=e.phase==="LANDED",touch=m.touchdown_speed_m_s,soft=touch!==null&&touch!==undefined&&touch<=g.touchdown,loads=(m.max_dynamic_pressure_Pa||0)<=g.qbar,obsPhases=new Set(state.careerObservations.map(x=>x.phase)).size;
 const common=[{done:launched,label:"Avvia il veicolo dalla piazzola"},{done:target,label:`Raggiungi ${state.kind==="space"?`${(g.altitude/1000).toFixed(0)} km`:`${g.altitude} m`} di quota`}];
 if(state.careerTrack==="pilot")common.push({done:landed,label:"Completa il rientro e atterra"},{done:soft,label:`Contatto morbido · ≤ ${g.touchdown} m/s`});
 if(state.careerTrack==="engineer")common.push({done:loads,label:`Rispetta il limite di pressione dinamica · ${g.qbar>=1000?`${(g.qbar/1000).toFixed(0)} kPa`:`${g.qbar} Pa`}`},{done:landed,label:"Verifica un recupero completo"});
 if(state.careerTrack==="scientist")common.push({done:obsPhases>=3,label:"Registra dati in 3 fasi diverse"},{done:landed,label:"Conserva la telemetria fino al recupero"});return{items:common,target,landed,soft,loads,obsPhases,m};}
function renderCareer(){
 if(!$("#careerCard"))return;
 const track=state.careerTrack,{current,next}=rankFor(track),xp=campaign.xp[track]||0;
 const range=next?next[0]-current[0]:1,progress=next?Math.min(100,(xp-current[0])/range*100):100;
 const metrics=careerObjectives();
 $("#careerRank").textContent=current[1];$("#careerMedal").textContent=current[1].toUpperCase();
 $("#careerXp").textContent=xp.toLocaleString("it-IT");$("#careerCopy").textContent=careerCopy[track];
 $("#careerXpBar").style.width=progress+"%";
 $("#careerNext").textContent=next?`PROSSIMO GRADO · ${next[1].toUpperCase()} · ${next[0]-xp} XP`:`GRADO MASSIMO · ${campaign.missions[track]} MISSIONI`;
 $("#careerScore").textContent=state.careerAwarded?`+${state.lastCareerScore||0} XP · MISSIONE`:state.engine?.phase==="LANDED"?"MISSIONE COMPLETATA":"PUNTEGGIO —";
 $("#careerObjectives").replaceChildren(...metrics.items.map(item=>{const row=document.createElement("div");row.className="career-objective"+(item.done?" done":"");row.innerHTML=`<i>${item.done?"✓":"·"}</i><span>${item.label}</span>`;return row}));
 $("#careerObserve").disabled=!state.engine;
 $("#careerObserve").textContent=`＋ REGISTRA OSSERVAZIONE${state.careerObservations.length?` · ${state.careerObservations.length}`:""}`;
 $$(".career-track-btn").forEach(b=>b.classList.toggle("active",b.dataset.track===track));
}
function awardCareer(data){
 if(!state.careerActive||state.careerAwarded||!["LANDED","CRASHED","ABORTED"].includes(data.phase))return;
 state.careerAwarded=true;const {target,landed,soft,loads,obsPhases,m}=careerObjectives();let score=0;
 if(state.careerTrack==="pilot")score=(landed?80:0)+(target?60:0)+(landed?(soft?60:Math.max(0,Math.round(60*Math.max(0,1-(m.touchdown_speed_m_s||0)/(careerGoals[state.kind].touchdown*2))))):0);
 else if(state.careerTrack==="engineer")score=(landed?80:0)+(target?60:0)+(loads?60:Math.max(0,Math.round(60*Math.max(0,1-(m.max_dynamic_pressure_Pa||0)/(careerGoals[state.kind].qbar*2)))));
 else score=(landed?70:0)+(target?40:0)+Math.min(90,obsPhases*30);
 state.lastCareerScore=score;campaign.xp[state.careerTrack]+=score;if(landed)campaign.missions[state.careerTrack]++;
 persistCareer();renderCareer();toast(landed?`MISSIONE COMPLETATA · +${score} XP · ${rankFor(state.careerTrack).current[1]}`:"MISSIONE TERMINATA · rivedi i dati e riprova");
}
async function loadModelCatalog(){try{[state.catalog,state.vehicleParts]=await Promise.all([api("/models"),api("/vehicle-parts")]);populateModelOptions();updateVehicleDesignPreview();updateMissionProfileUI()}catch{populateModelOptions()}}
async function loadVisualCatalog(){try{const response=await fetch("assets/vehicle-models.json",{cache:"no-cache"});if(!response.ok)throw new Error(`catalog HTTP ${response.status}`);state.visualCatalog=await response.json();populateVisualModelOptions();selectVisualModel()}catch(error){console.warn("ASTRA visual catalog unavailable:",error);$("#visualModelSummary").textContent="Catalogo 3D non raggiungibile; ASTRA usa il modello locale."}}
async function loadCelestialCatalog(epochText){
 const epoch=epochText||new Date().toISOString().slice(0,10);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(epoch))throw new Error("Scegli una data valida in formato UTC.");
 state.celestialDate=`${epoch}T00:00:00Z`;
 $("#celestialEpoch").value=epoch;
 state.celestial=await api("/celestial?date="+encodeURIComponent(state.celestialDate));
 $("#ephemerisDate").textContent="JPL · "+epoch+" UTC";
 const select=$("#celestialTarget");select.replaceChildren();
 for(const [label,klass] of [["PIANETI","planet"],["LUNE · SATELLITI NATURALI","moon"]]){
  const group=document.createElement("optgroup");group.label=label;
  state.celestial.objects.filter(o=>o.class===klass&&o.id!=="earth").forEach(body=>{
   const option=document.createElement("option");option.value=body.id;
   option.textContent=body.class==="moon"?`${body.name} · ${state.celestial.objects.find(p=>p.id===body.parent_id)?.name}`:body.name;group.append(option)
  });select.append(group)
 }
 if(!state.celestial.objects.some(o=>o.id===state.selectedBodyId))state.selectedBodyId="moon";
 select.value=state.selectedBodyId;updateCelestialBody()
}
function updateCelestialBody(){if(!state.celestial)return;const body=state.celestial.objects.find(o=>o.id===state.selectedBodyId);if(!body)return;const parent=state.celestial.objects.find(o=>o.id===body.parent_id);$("#bodyName").textContent=body.name;$("#bodyClass").textContent=body.class==="moon"?`SATELLITE NATURALE · SISTEMA ${parent?.name?.toUpperCase()||""}`:"PIANETA · ORBITA ELLITTICA ELICOCENTRICA";$("#bodyRadius").textContent=(body.radius_m/1000).toLocaleString("it-IT",{maximumFractionDigits:1})+" km";if(body.class==="moon"){const modelAxis=(body.semi_major_axis_m/1000).toLocaleString("it-IT",{maximumFractionDigits:0}),meanAxis=body.reference_mean_semi_major_axis_m;if(Number.isFinite(meanAxis)){$("#bodyOrbit").textContent=`${modelAxis} km · JPL media ${(meanAxis/1000).toLocaleString("it-IT",{maximumFractionDigits:0})} km`}else $("#bodyOrbit").textContent=modelAxis+" km dal pianeta ospite"}else $("#bodyOrbit").textContent=(body.semi_major_axis_m/AU).toFixed(3)+" AU";$("#bodyModel").textContent=body.ephemeris_model;state.selectedBodyId=body.id;requestTransfer();}
function requestTransferPlaybackState(){const plan=state.transferPlan;if(!plan||state.transferPositionPending)return;const progress=state.transferProgress,token=++state.transferPositionToken,elapsed_s=progress*plan.transfer_time_s;state.transferPositionPending=true;const status=$("#transferPropagationStatus");if(!state.transferPosition){status.textContent="API ASTRA · PROPAGAZIONE IN CORSO";status.dataset.state="pending"}const q=`/transfer/state?target=${encodeURIComponent(plan.target_id)}&date=${encodeURIComponent(state.celestialDate)}&elapsed_s=${elapsed_s.toFixed(3)}`;api(q).then(current=>{if(token===state.transferPositionToken&&state.transferPlan===plan&&Math.abs(state.transferProgress-progress)<.003){state.transferPosition=current.position_heliocentric_m;state.transferVelocity=current.velocity_heliocentric_m_s||null;status.textContent=current.propagator.includes("Cowell")?"API ASTRA · STATO COWELL N-CORPI · INTERPOLAZIONE HERMITE":"API ASTRA · STATO GEOCENTRICO · VARIABILI UNIVERSALI";status.dataset.state="ready"}}).catch(()=>{if(token===state.transferPositionToken&&state.transferPlan===plan){state.transferPosition=null;state.transferVelocity=null;status.textContent="API NON RAGGIUNGIBILE · CAMPIONI VISIVI DI RISERVA";status.dataset.state="offline"}}).finally(()=>{state.transferPositionPending=false;if(state.transferPlan&&(state.transferPlan!==plan||Math.abs(state.transferProgress-progress)>=.003))requestTransferPlaybackState()})}
function updateTransferPlayback(){const plan=state.transferPlan;if(!plan)return;$("#transferClock").textContent=`T+ ${(state.transferProgress*plan.transfer_time_days).toLocaleString("it-IT",{minimumFractionDigits:1,maximumFractionDigits:1})} / ${plan.transfer_time_days.toLocaleString("it-IT",{minimumFractionDigits:1,maximumFractionDigits:1})} giorni`;$("#transferSeek").value=String(Math.round(state.transferProgress*1000));$("#transferPlay").textContent=state.transferPlaying?"Ⅱ PAUSA ANTEPRIMA":"▶ RIPRODUCI TRAIETTORIA";$("#transferPlay").setAttribute("aria-pressed",String(state.transferPlaying));requestTransferPlaybackState()}
async function requestTransfer(){if(!state.celestial||!state.selectedBodyId)return;state.transferPlaying=false;$("#transferPlayback").hidden=true;try{const q=`/transfer?target=${encodeURIComponent(state.selectedBodyId)}&date=${encodeURIComponent(state.celestialDate)}`,plan=await api(q);state.transferPlan=plan;state.transferProgress=0;state.transferPlaying=false;state.transferPosition=null;state.transferVelocity=null;state.transferPositionToken++;$("#transferPropagationStatus").textContent="API ASTRA · IN ATTESA DELLO STATO PROPAGATO";$("#transferPropagationStatus").dataset.state="pending";$("#transferPlayback").hidden=false;$("#transferSeek").value="0";updateTransferPlayback();$("#transferDv").textContent=(plan.total_delta_v_m_s/1000).toFixed(2)+" km/s";$("#transferTime").textContent=plan.transfer_time_days.toFixed(1)+" giorni";$("#transferWindow").textContent=plan.next_ideal_window_days.toFixed(1)+" giorni";$("#transferMethod").textContent=`SOI ${plan.soi_patch_iterations} iter · ε=${plan.soi_patch_residual_m.toPrecision(2)} m · Lambert ${plan.lambert_iterations} iter · εt=${plan.lambert_time_residual_s.toExponential(1)} s${plan.targeting_iterations?` · COWELL ${plan.targeting_iterations} iter · εr=${plan.targeting_position_residual_m.toPrecision(2)} m · SOI ${plan.targeting_soi_iterations} iter · εb=${(plan.targeting_soi_boundary_residual_m/1000).toPrecision(2)} km`:""}${plan.departure_vector_delta_v_m_s===null?"":` · impulso LEO dallo stato fissato ${(plan.departure_vector_delta_v_m_s/1000).toFixed(2)} km/s`}`;$("#transferDates").textContent=`PARTENZA ${new Date(plan.departure_date_utc).toLocaleDateString("it-IT",{timeZone:"UTC"})} UTC · ARRIVO ${new Date(plan.arrival_date_utc).toLocaleDateString("it-IT",{timeZone:"UTC"})} UTC`;$("#transferFrames").textContent=`POSIZIONI · ${plan.position_frame} · VELOCITÀ · ${plan.velocity_frame}`;$("#transferPlaybackNote").textContent=plan.targeting_iterations?"Arco integrato con RK4 Cowell, gravità puntiforme del Sole e degli otto pianeti; rotta visuale interpolata con Hermite. Niente motori o GNC interplanetario.":"Tratta Terra–Luna a due corpi geocentrica, propagata con variabili universali. Niente motori o GNC interplanetario.";$(`#transferLimit`).textContent=plan.limitation+" L’arco Lambert termina alle sfere d’influenza; il Δv da orbita di parcheggio è una stima impulsiva ideale e non simula l’ascesa."}catch(e){state.transferPlan=null;state.transferPlaying=false;state.transferPosition=null;state.transferVelocity=null;state.transferPositionToken++;$("#transferPlayback").hidden=true;$("#transferDv").textContent="—";$("#transferTime").textContent="—";$("#transferWindow").textContent="—";$("#transferMethod").textContent=e.message;$("#transferDates").textContent="";$("#transferFrames").textContent=""}}
async function openCelestialExplorer(){if(state.kind!=="space"){toast("Seleziona prima il dominio SPAZIO");return}try{if(!state.celestial)await loadCelestialCatalog();state.celestialCamera={az:state.az,el:state.el,zoom:state.zoom};state.solarView=true;state.zoom=5.8;state.az=.36;state.el=.34;document.body.classList.add("celestial-open");$("#celestialDialog").showModal();$("#systemExplorer").classList.add("rail-active")}catch(e){toast("Catalogo celeste non raggiungibile: "+e.message)}}
let activeDisciplineFilter="all";
function disciplineEvidence(item){const e=state.engine;if(!e||!item.vehicles.includes(state.kind))return"";if(item.id==="orbital-mechanics"&&state.kind==="space")return`Stato corrente · t=${e.time_s.toFixed(1)} s · altitudine ${Math.round(e.altitude_m)} m · ECI.`;if(item.id==="flight-dynamics"&&state.kind!=="space")return`Fase ${phaseText[e.phase]||e.phase} · quota ${Math.round(e.altitude_m)} m · velocità ${e.speed_m_s.toFixed(1)} m/s.`;if(item.id==="gnc")return state.kind==="space"?"La navigazione spaziale espone lo stato ECI del propagatore.":e.navigation_estimate?`Kalman verticale · quota ${e.navigation_estimate.altitude_m.toFixed(1)} m · σ ${e.navigation_estimate.altitude_sigma_m.toFixed(2)} m.`:"Filtro verticale IMU + barometro disponibile per questa missione.";if(item.id==="propulsion")return state.kind==="drone"?`Batteria ${Math.round(e.battery_pct)}% · ${e.battery?.energy_remaining_Wh?.toFixed(1)||"—"} Wh · assorbimento ${e.battery?.power_draw_W?.toFixed(0)||0} W · energia missione ${e.battery?.energy_used_Wh?.toFixed(2)||"—"} Wh.`:state.kind==="aircraft"?(()=>{const p=e.propulsion;return p?`${p.engine_type} · potenza ${p.actual_power_pct.toFixed(0)}% / comando ${p.commanded_power_pct.toFixed(0)}% · spinta ${p.thrust_N.toFixed(0)} N · albero ${(p.shaft_power_W/1000).toFixed(0)} kW · carburante ${p.fuel_flow_kg_s.toFixed(3)} kg/s.`:`Carburante residuo ${Math.round(e.propellant_pct)}%.`})():`Propellente residuo ${Math.round(e.propellant_pct)}%.`;if(item.id==="atmosphere"||item.id==="aerodynamics"){const env=e.environment;if(env?.density_kg_m3!==undefined)return`${env.atmosphere_model||"COESA76"} · ρ ${formatEnvironmentValue(env.density_kg_m3)} kg/m³ · T ${env.temperature_K.toFixed(1)} K · p ${formatPressure(env.pressure_Pa)}${env.in_model_domain===false?" · FUORI DOMINIO": ""}.`;return"Missione non ancora avviata: i dati ambientali appariranno qui."}if(item.id==="sensors-telemetry")return`Fase ${phaseText[e.phase]||e.phase} · t=${e.time_s.toFixed(1)} s · ${e.mission_metrics?.max_dynamic_pressure_Pa!==undefined?`q max ${Math.round(e.mission_metrics.max_dynamic_pressure_Pa)} Pa`:"metriche pronte"}.`;return""}
function renderDisciplineLibrary(){const grid=$("#disciplineGrid"),items=aerospaceDisciplines.filter(item=>activeDisciplineFilter==="all"||item.status===activeDisciplineFilter),relevant=items.filter(item=>item.vehicles.includes(state.kind));$("#disciplineCount").textContent=`${items.length} DISCIPLINE`;$("#disciplineScope").textContent=`${relevant.length} pertinenti al dominio ${state.kind==="space"?"SPAZIO":state.kind==="aircraft"?"AEREO":"DRONE"}`;grid.replaceChildren(...items.map(item=>{const status=disciplineStatuses[item.status],card=document.createElement("article");card.className="discipline-card";card.dataset.status=item.status;const applicable=item.vehicles.map(v=>v==="space"?"SPAZIO":v==="aircraft"?"AEREO":"DRONE").join(" · ");const evidence=disciplineEvidence(item);card.innerHTML=`<div class="discipline-card-head"><div><h3>${item.name}</h3><div class="discipline-card-domain">${item.domain} · ${applicable}</div></div><span class="discipline-status" title="${status.explanation}">${status.label}</span></div><p><b>IN ASTRA · </b>${item.covers}</p><p class="discipline-limit"><b>LIMITE ATTUALE · </b>${item.limit}</p>${evidence?`<p class="discipline-evidence"><b>TELEMETRIA · </b>${evidence}</p>`:""}`;return card}))}
function openDisciplineExplorer(){activeDisciplineFilter="all";$$('[data-discipline-filter]').forEach(button=>button.classList.toggle("active",button.dataset.disciplineFilter===activeDisciplineFilter));renderDisciplineLibrary();$("#disciplineDialog").showModal();$("#disciplineExplorer").classList.add("rail-active")}
function consumeEngine(data){const priorScenario=state.engine?.scenario,priorStageEvents=state.engine?.stage_events?.length||0;state.engine=data;captureFlightTrace(data);missionRecorderUi.updateFaultManagement(data);if(data.vehicle==="space"&&data.scenario!=="orbital"&&data.time_s===0)setLaunchSiteReference(data.position_eci_m);state.engineReceivedAt=performance.now();if(priorScenario!==data.scenario)setVisualModelSummary();if(missionRecorder.capture(data)&&document.querySelector("#missionDataDialog")?.open)missionRecorderUi.render();if(data.vehicle==="space"&&["mission","leo-return","orbital"].includes(data.scenario))state.missionProfile=data.scenario;if(data.time_s===0&&!data.mission_started)state.stageEventCount=data.stage_events?.length||0;else if((data.stage_events?.length||0)>Math.max(priorStageEvents,state.stageEventCount)){const events=data.stage_events||[],fresh=events[events.length-1];state.stageEventCount=data.stage_events.length;if(fresh?.event==="STAGE_SEPARATION")toast(`STADIO ${fresh.stage} SEPARATO · ${Math.round(fresh.jettisoned_mass_kg)} kg di massa secca scaricati`);else if(fresh?.event==="STAGE_JETTISON")toast(`STADIO ${fresh.stage} SCARTATO · ${Math.round(fresh.jettisoned_mass_kg)} kg totali, inclusi ${Math.round(fresh.jettisoned_propellant_kg)} kg di propellente`)}if(data.vehicle_design){state.customDesign={name:data.vehicle_design.name,stages:data.vehicle_design.stages.map(({tank_count,engine_count})=>({tank_count,engine_count}))};localStorage.setItem("astra-vehicle-design-v1",JSON.stringify(state.customDesign))}state.seconds=data.time_s||0;state.fuel=data.battery_pct??data.propellant_pct??0;if(state.careerActive&&data.phase)state.careerPhases.add(data.phase);if(data.model_id){state.modelId=data.model_id;state.modelPreferences[state.kind]=data.model_id;localStorage.setItem("astra-model-selection-v1",JSON.stringify(state.modelPreferences))}if(data.command){if(state.mode!=="manual"){state.roll=data.command.roll_deg??state.roll;state.pitch=data.command.pitch_deg??state.pitch;state.thrust=data.command.throttle_pct??state.thrust;state.yaw=data.command.yaw_deg??state.yaw;state.brakes=data.command.brakes_pct??state.brakes;}if(Array.isArray(data.command.attitude_target_deg)){state.attitudeTarget=data.command.attitude_target_deg.slice(0,3);[["attRoll","attRollOut",0],["attPitch","attPitchOut",1],["attYaw","attYawOut",2]].forEach(([input,output,index])=>{if($("#"+input))$("#"+input).value=state.attitudeTarget[index];if($("#"+output))$("#"+output).value=state.attitudeTarget[index].toFixed(0)+"°"})}$("#brakes").value=state.brakes;$("#brakesOut").value=Math.round(state.brakes)+"%"}if($("#model"))$("#model").textContent=data.model||"ASTRA PHYSICS";populateModelOptions();if(state.kind==="space"&&state.modelId==="astra-custom-stack")$("#vehicle").textContent=state.customDesign.name.toUpperCase();else if(data.vehicle_name)$("#vehicle").textContent=data.scenario==="orbital"?"LEO SPACECRAFT":data.vehicle_name.toUpperCase();updateMissionPresentation(data.scenario);if(data.phase){$("#currentEvent").textContent=phaseText[data.phase]||data.phase;$("#simState").textContent=data.phase==="LANDED"?"LANDED":data.mission_started?"MISSION ACTIVE":"READY";$("#nextEvent").textContent=data.phase==="LANDED"?"COMPLETE":data.scenario==="orbital"?(data.phase==="STATION_KEEPING"?"STATION KEEPING · 20 M":"CW APPROACH · RCS") :data.scenario==="leo-return"?({ASCENT:"APOGEE INSERTION",COAST_TO_APOGEE:"CIRCULARIZE LEO",CIRCULARIZE:"ORBIT · ONE REVOLUTION",ORBIT_COAST:"DEORBIT ALIGN",DEORBIT_ALIGN:"DEORBIT BURN",DEORBIT_BURN:"ENTRY INTERFACE",DEORBIT_COAST:"ATMOSPHERIC ENTRY",REENTRY:"AEROSHELL",AEROSHELL:"DROGUE CHUTE",DROGUE:"MAIN CHUTE",PARACHUTE:"TOUCHDOWN"}[data.phase]||"RECOVERY"):data.vehicle==="space"?"COAST / RETURN":data.vehicle==="drone"?"INSPECT / LAND":"CRUISE / LAND";if(["LANDED","CRASHED","ABORTED"].includes(data.phase)&&state.running){state.running=false;$("#statusText").textContent=data.phase==="LANDED"?"LANDED":"CHECK MISSION";$("#play").classList.remove("running");$("#play").innerHTML=data.phase==="LANDED"?"<b>✓</b><span>MISSIONE COMPLETATA</span>":"<b>↻</b><span>RIAVVIA MISSIONE</span>"}}$("#crosshair").style.display=data.scenario==="orbital"?"flex":"none";updateLesson();update();awardCareer(data);renderCareer()}
async function connectEngine(){const epoch=state.requestEpoch;try{const data=await api("/state");if(epoch!==state.requestEpoch)return;consumeEngine(data);$("#simState").textContent=data.mission_started?"MISSION ACTIVE":"READY";$("#statusText").textContent="CONNECTED"}catch(e){if(epoch!==state.requestEpoch)return;$("#simState").textContent="ENGINE OFFLINE";$("#statusText").textContent="API REQUIRED";$("#currentEvent").textContent="NO ENGINE";toast("Avvia ASTRA 1.0 con python3 -m astra")}}
function startMissionRecording(data){missionRecorder.start({vehicle:data.vehicle_name||(info[state.kind][4]+" "+info[state.kind][5]),vehicle_name:data.vehicle_name||null,vehicle_type:data.vehicle||state.kind,scenario:data.scenario||state.missionProfile,mission_profile:data.mission_profile||null,physics_model_id:data.model_id||state.modelId,physics_model:data.model||null,visual_model_id:state.visualModelId,wind_ned_m_s:data.environment?.wind_ned_m_s||null,wind_profile_ned_m_s:data.environment?.wind_profile_ned_m_s||null,position_frame:data.frame||(state.kind==="space"?"ECI":"NED"),initial_vehicle_state:data})}function isCurrentReset(result){return result?.ok===true&&result.epoch===state.requestEpoch}
// Serialize reset requests so an older server mutation cannot overtake the selected configuration.
let engineResetQueue=Promise.resolve();
async function resetEngine({startRecording=true}={}){
 const epoch=++state.requestEpoch,payload={vehicle:state.kind,scenario:state.kind==="space"?state.missionProfile:"mission",model_id:state.modelId};
 if(state.kind==="space"&&state.modelId==="astra-custom-stack")payload.custom_design={name:state.customDesign.name,stages:state.customDesign.stages.map(stage=>({...stage}))};
 if(state.kind!=="space"){
  payload.wind_ned_m_s=state.windPreset==="shear"?[0,0,0]:windPresets[state.windPreset];
  const windProfile=windProfilePayload();if(windProfile)payload.wind_profile_ned_m_s=windProfile;
  const turbulence=turbulencePayload();if(turbulence)payload.turbulence=turbulence
 }
 state.running=false;state.resetPending=true;state.engine=null;state.careerActive=false;
 $("#play").disabled=true;$("#step").disabled=true;$("#stageNow").disabled=true;
 $("#play").classList.remove("running");$("#play").innerHTML="<b>↻</b><span>CARICAMENTO MISSIONE</span>";
 $("#statusText").textContent="CONNECTING";$("#simState").textContent="LOADING";$("#currentEvent").textContent="CONFIGURAZIONE IN CORSO";
 const previousReset=engineResetQueue;let releaseReset;engineResetQueue=new Promise(resolve=>{releaseReset=resolve});
 try{
  await previousReset;
  if(epoch!==state.requestEpoch)return{ok:false,stale:true,epoch};
  const data=await api("/reset",payload);
  if(epoch!==state.requestEpoch)return{ok:false,stale:true,epoch};
  resetFlightTrace();if(startRecording)startMissionRecording(data);consumeEngine(data);
  $("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";$("#statusText").textContent="READY";
  return{ok:true,epoch,data}
 }catch(error){
  if(epoch!==state.requestEpoch)return{ok:false,stale:true,epoch};
  state.engine=null;state.running=false;
  $("#statusText").textContent="RESET FAILED";$("#simState").textContent="NOT READY";$("#currentEvent").textContent="CONFIGURAZIONE NON APPLICATA";
  $("#play").innerHTML="<b>↻</b><span>RIPROVA AVVIO</span>";
  toast("Configurazione non applicata: "+error.message);
  return{ok:false,stale:false,epoch,error}
 }finally{
  releaseReset();
  if(epoch===state.requestEpoch){state.resetPending=false;$("#play").disabled=state.launchPending;$("#step").disabled=!state.engine}
 }
}

const drydenPresetValues={light:{sigma:[0.5,0.4,0.3],lengths:[150,150,45]},moderate:{sigma:[1.5,1.0,0.8],lengths:[200,200,60]},severe:{sigma:[3.0,2.0,1.5],lengths:[300,300,90]}};
function syncDrydenControls(){const preset=state.drydenPreset,active=state.kind!=="space"&&preset!=="none",custom=preset==="custom",values=drydenPresetValues[preset];if(values){state.drydenSigma=[...values.sigma];state.drydenLengths=[...values.lengths]}$("#drydenParams").hidden=!active;$("#drydenSeed").value=String(state.drydenSeed);$("#drydenSeed").disabled=!active;const ids=["drydenSigmaU","drydenSigmaV","drydenSigmaW"],lengthIds=["drydenLengthU","drydenLengthV","drydenLengthW"];ids.forEach((id,index)=>{$("#"+id).value=String(state.drydenSigma[index]);$("#"+id).disabled=!custom});lengthIds.forEach((id,index)=>{$("#"+id).value=String(state.drydenLengths[index]);$("#"+id).disabled=!custom})}
function turbulencePayload(){if(state.kind==="space"||state.drydenPreset==="none")return null;return{model:"dryden",seed:state.drydenSeed,sigma_uvw_m_s:[...state.drydenSigma],length_uvw_m:[...state.drydenLengths]}}
function saveDrydenControls(){const preset=$("#drydenPreset").value;state.drydenPreset=preset;state.drydenSeed=Number($("#drydenSeed").value);if(preset==="custom"){state.drydenSigma=["drydenSigmaU","drydenSigmaV","drydenSigmaW"].map(id=>Number($("#"+id).value));state.drydenLengths=["drydenLengthU","drydenLengthV","drydenLengthW"].map(id=>Number($("#"+id).value))}localStorage.setItem("astra-dryden-environment-v1",JSON.stringify({preset:state.drydenPreset,seed:state.drydenSeed,sigma:state.drydenSigma,lengths:state.drydenLengths}))}
function applyDrydenControls(){saveDrydenControls();syncDrydenControls();saveDrydenControls();$("#windPreset").dispatchEvent(new Event("change",{bubbles:true}))}
$("#drydenPreset").addEventListener("change",applyDrydenControls);
["drydenSeed","drydenSigmaU","drydenSigmaV","drydenSigmaW","drydenLengthU","drydenLengthV","drydenLengthW"].forEach(id=>$("#"+id).addEventListener("change",applyDrydenControls));
$("#windPreset").addEventListener("change",async event=>{if(event.target.value!=="shear"&&!Object.prototype.hasOwnProperty.call(windPresets,event.target.value))return;state.windPreset=event.target.value;state.running=false;state.seconds=0;state.careerActive=false;state.careerObservations=[];state.careerPhases.clear();state.careerAwarded=false;state.lastAdvance=performance.now();const result=await resetEngine();if(!isCurrentReset(result))return;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";$("#statusText").textContent="READY";$("#simState").textContent="READY";update();renderCareer();const label=event.target.selectedOptions[0].textContent.trim().toLowerCase();if($("#windModelSummary"))$("#windModelSummary").textContent=state.windPreset==="shear"?"Profilo assoluto NED interpolato linearmente tra quote; tenuto costante oltre i nodi estremi.":"Vento medio NED costante. Le forze dipendono dalla velocità rispetto all’aria.";toast(`Condizioni caricate · ${label} · missione pronta al lancio`)});
async function sendCommand(extra={}){if(state.resetPending||!state.engine)return;const epoch=state.requestEpoch,command={mode:state.mode,throttle_pct:state.thrust,roll_deg:state.roll,pitch_deg:state.pitch,yaw_deg:state.yaw,...(state.kind==="aircraft"?{brakes_pct:state.brakes}:{}),...(state.kind==="space"&&state.engine?.scenario==="orbital"?{attitude_target_deg:state.attitudeTarget}:{}),...extra};try{await api("/command",command)}catch(e){if(epoch===state.requestEpoch)toast("API di controllo non raggiungibile")}}
function advanceVisualAnimations(now){
 const model=state.kind==="aircraft"?catalogModelFor("aircraft"):null,config=model?.rotor_animation;
 if(!config||config.visual_controller!=="throttle")return;
 if(state.visualPropellerModelId!==model.id){state.visualPropellerModelId=model.id;state.visualPropellerPhase=0;state.visualPropellerRpm=0;state.visualAnimationTime=now;return}
 const previous=state.visualAnimationTime;state.visualAnimationTime=now;if(!Number.isFinite(previous)||!state.running)return;
 const dt=Math.min(.12,Math.max(0,(now-previous)/1000))*state.speed;if(dt<=0)return;
 const terminal=["LANDED","CRASHED","ABORTED"].includes(state.engine?.phase),throttle=terminal?0:Math.max(0,Math.min(1,(state.engine?.command?.throttle_pct||0)/100));
 const targetRpm=throttle>.02?(config.visual_idle_rpm||0)+throttle*((config.visual_max_rpm||0)-(config.visual_idle_rpm||0)):0,tau=targetRpm>state.visualPropellerRpm?.22:.42;
 state.visualPropellerRpm+=(targetRpm-state.visualPropellerRpm)*(1-Math.exp(-dt/tau));
 state.visualPropellerPhase=(state.visualPropellerPhase+state.visualPropellerRpm*(2*Math.PI/60)*dt)%(2*Math.PI);
}
function frame(t){requestAnimationFrame(frame);if(document.hidden)return;const target=1000/deviceProfile.targetFps;if(t-(frame.lastRender||0)<target)return;const gap=frame.lastRender?t-frame.lastRender:target;frame.lastRender=t;updatePilotInputs(t);advanceVisualAnimations(t);frame.intervalEMA=frame.intervalEMA?frame.intervalEMA*.88+gap*.12:gap;if(state.transferPlaying){state.transferProgress=Math.min(1,state.transferProgress+gap/24000);const playbackEnded=state.transferProgress>=1;if(playbackEnded)state.transferPlaying=false;if(playbackEnded||t-(frame.lastPlaybackUi||0)>120){updateTransferPlayback();frame.lastPlaybackUi=t}}if(state.running&&!state.pending&&t-state.lastAdvance>=deviceProfile.apiIntervalMs){const wall=Math.min(.25,Math.max(.001,(t-state.lastAdvance)/1000));state.lastAdvance=t;state.pending=true;const epoch=state.requestEpoch;api("/step",{dt_s:wall*state.speed}).then(data=>{if(epoch===state.requestEpoch)consumeEngine(data)}).catch(()=>{if(epoch===state.requestEpoch){state.running=false;$("#statusText").textContent="API LOST";$("#simState").textContent="ENGINE OFFLINE"}}).finally(()=>state.pending=false)}if(gl){gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);cameraSet();if(state.kind==="space")renderSpace(t);else renderAir(t)}else renderCompat(t);if(!frame.qualityCheck)frame.qualityCheck=t;if(t-frame.qualityCheck>3000){const expected=1000/deviceProfile.targetFps;if(frame.intervalEMA>expected*1.35)renderScale=Math.max(.9,renderScale*.9);else if(frame.intervalEMA<expected*1.14)renderScale=Math.min(1,renderScale+.04);resize();frame.qualityCheck=t}}

function updateNavPanel(){
 const nav=state.engine?.horizontal_navigation_estimate,guidance=state.engine?.guidance;
 const orbital=state.kind==="space"&&state.engine?.scenario==="orbital";
 const spaceLaunch=state.kind==="space"&&!orbital&&Boolean(state.engine?.navigation_estimate);
 const spaceNav=spaceLaunch?state.engine?.navigation_estimate:null;
 const relativeNav=state.engine?.relative_navigation_estimate;
 const quality=$("#navQuality");
 const visible=state.kind==="drone"||state.kind==="aircraft"||orbital||spaceLaunch;
 $("#navSolution").hidden=!visible;
 $("#navStackLabel").textContent=orbital?"GNSS SINTETICO · RTN KALMAN":spaceLaunch?"IMU 20 Hz + GNSS ECI 1 Hz · KALMAN":state.kind==="drone"?"IMU + GNSS · PLANAR KALMAN":"IMU + BARO / GNSS ALT · VERTICAL KALMAN";
 $("#navStackType").textContent="FILTER";
 $("#guidanceStackLabel").textContent=orbital?"CW APPROACH · 20 M STATION-KEEPING":state.kind==="aircraft"?"PHASE PROFILE · FILTERED SINK-RATE LOOP":"PHASE SEQUENCER · MISSION PROFILE";
 $("#controlStackLabel").textContent=orbital?"CW PD · KALMAN FEEDBACK · 24 N RCS + REACTION WHEELS":state.kind==="drone"?"ATTITUDE PD · POSITION/ALTITUDE LQR · 6-DOF MODEL":state.kind==="aircraft"?"ATTITUDE PD · 6-DOF AIRFRAME":"QUATERNION PD · 2-AXIS TVC + 3-AXIS COAST RCS";
 $("#gncNote").textContent=orbital?"RENDEZVOUS: ECI + J₂ · CW PD SU STIMA RTN · FIX GNSS SIMULATI 1 Hz · LVLH ATTITUDE HOLD":spaceLaunch?"SPACE: INS ECI · IMU 20 Hz + GNSS 1 Hz · GUIDA SU STIMA · J₂ / QUATERNION / TVC-RCS":state.kind==="drone"?"DRONE: IMU + GNSS · LQR POSITION/ALTITUDE · WIND-AWARE RETURN":"AIRCRAFT: IMU + BARO + GNSS ALT BACKUP · GNSS TRACK · 6-DOF AERODYNAMICS";
 if(!visible)return;
 const signed=value=>(value>=0?"+":"")+value.toFixed(1);
 if(spaceLaunch){
  const position=spaceNav?.position_eci_m||[0,0,0],velocity=spaceNav?.velocity_eci_m_s||[0,0,0];
  const radius=Math.hypot(...position),radialSpeed=radius>0?position.reduce((sum,value,index)=>sum+value*velocity[index],0)/radius:0;
  const altitude=radius-6378137,sigma=Math.max(...(spaceNav?.position_sigma_eci_m||[0,0,0]));
  const updates=spaceNav?.gnss_updates||0,status=spaceNav?.gnss_integrity||"WAITING";
  $("#navSolution").querySelector(".nav-solution-head span").textContent="STIMA INERZIALE · ECI";
  $("#navNorth").textContent="ALT "+signed(altitude)+" m";
  $("#navEast").textContent="vᵣ "+signed(radialSpeed)+" m/s";
  quality.textContent=status==="DROPOUT"?"GNSS · NO FIX · INS ONLY":status==="OUTLIER_REJECTED"?`GNSS · ${spaceNav?.gnss_rejected||0} FIX RESPINTI`:updates?`IMU 20 Hz · GNSS ${updates} FIX`:"IMU + GNSS · IN ATTESA";
  quality.dataset.integrity=status==="DROPOUT"||status==="OUTLIER_REJECTED"?"degraded":updates?"nominal":"waiting";
  $("#navSolutionDetail").textContent=`ECI · J₂ · σpos max ${sigma.toFixed(2)} m · σv max ${Math.max(...(spaceNav?.velocity_sigma_eci_m_s||[0,0,0])).toFixed(3)} m/s · NIS ${spaceNav?.last_gnss_nis?.toFixed(2)??"—"}/${spaceNav?.innovation_gate_nis??"—"} · assetto quaternion ideale`;
  return;
 }
 const position=orbital?(relativeNav?.position_rtn_m||[0,0,0]):(nav?.position_ned_m||[0,0]);
 const sigma=orbital?(relativeNav?.position_sigma_rtn_m||[0,0,0]):(nav?.position_sigma_m||[0,0]);
 $("#navSolution").querySelector(".nav-solution-head span").textContent=orbital?"STIMA RELATIVA · RTN":state.kind==="aircraft"?"NAVIGAZIONE · NED":"POSITION HOLD";
 $("#navNorth").textContent=(orbital?"R ":"N ")+signed(position[0])+" m";
 $("#navEast").textContent=(orbital?"T ":"E ")+signed(position[1])+" m";
 if(orbital){
  const updates=relativeNav?.measurement_updates||0,target=state.engine?.rendezvous_guidance?.target_relative_position_rtn_m||[0,-20,0];
  const velocitySigma=relativeNav?.velocity_sigma_rtn_m_s||[0,0,0];
  const error=Math.hypot(...position.map((value,index)=>value-target[index]));
  quality.textContent=updates?`FILTRO · ${updates} FIX · 1 Hz`:"FILTRO · FIX IN ATTESA";
  quality.dataset.integrity=updates?"nominal":"waiting";
  $("#navSolutionDetail").textContent=`ERRORE STIMATO ${error.toFixed(2)} m · VELOCITÀ ${Math.hypot(...(relativeNav?.velocity_rtn_m_s||[0,0,0])).toFixed(3)} m/s · σpos R/T/N ${sigma.map(value=>value.toFixed(2)).join("/")} m · σvel ${velocitySigma.map(value=>value.toFixed(3)).join("/")} m/s · GNSS SINTETICO · CW PREDICTOR`;
  return;
 }
 const updates=nav?.gnss_updates||0;
 if(state.kind==="aircraft"){
  const vertical=state.engine?.navigation_estimate,verticalSpeed=guidance?.estimated_vertical_speed_up_m_s,sink=guidance?.estimated_sink_rate_down_m_s;
  const baroLost=vertical?.barometer_integrity==="NO_FIX",gnssLost=nav?.gnss_integrity==="NO_FIX";
  const rejected=vertical?.barometer_integrity==="OUTLIER_REJECTED"||nav?.gnss_integrity==="OUTLIER_REJECTED";
  const degraded=baroLost||gnssLost||rejected;
  const altitudeBackup=vertical?.gnss_altitude_integrity==="VALID"&&vertical?.vertical_solution_sources?.includes("GNSS_ALTITUDE");
  quality.textContent=baroLost?(altitudeBackup?"BARO · NO FIX · GNSS ALT BACKUP":"ALT · INS ONLY · NO FIX"):degraded?"INTEGRITÀ · NAV DEGRADED":vertical?.barometer_updates?`IMU + BARO · ${vertical.barometer_updates} FIX`:"IMU + BARO · IN ATTESA";
  quality.dataset.integrity=degraded?"degraded":vertical?.barometer_updates?"nominal":"waiting";
  const gnssNote=nav?.gnss_integrity==="NO_FIX"?" · GNSS: NO FIX · INS ONLY":nav?.gnss_integrity==="OUTLIER_REJECTED"?` · GNSS: ${nav.gnss_rejected} FIX RESPINTI`:"";
  const baroNote=baroLost?(altitudeBackup?" · BARO NO FIX · GNSS ALT BACKUP":" · BARO NO FIX · INS ONLY"):vertical?.barometer_integrity==="OUTLIER_REJECTED"?` · BARO: ${vertical.barometer_rejected} LETTURE RESPINTE`:"";
  const verticalSources=vertical?.vertical_solution_sources?.join("+")||"INS";
  const gnssAltitudeNote=vertical?.gnss_altitude_integrity==="NO_FIX"?" · GNSS ALT NO FIX":vertical?.gnss_altitude_integrity==="VALID"&&baroLost?` · GNSS ALT σsens ${vertical.gnss_altitude_measurement_sigma_m.toFixed(1)} m`:"";
  $("#navSolutionDetail").textContent=vertical?`QUOTA ${vertical.altitude_m.toFixed(1)} m · v↑ ${(verticalSpeed??vertical.vertical_speed_m_s).toFixed(2)} m/s · DISCESA ${(sink??-vertical.vertical_speed_m_s).toFixed(2)} m/s ↓ · σh ${vertical.altitude_sigma_m.toFixed(2)} m · SRC ${verticalSources} · TRACK ${guidance?.estimated_ground_track_deg===null||guidance?.estimated_ground_track_deg===undefined?"—":guidance.estimated_ground_track_deg.toFixed(1)+"°"} · σN/E ${sigma.map(value=>value.toFixed(2)).join("/")} m${baroNote}${gnssAltitudeNote}${gnssNote}${Number.isFinite(guidance?.flare_target_speed_m_s)?` · VFLARE ${guidance.flare_target_speed_m_s.toFixed(1)} m/s`:""}`:"IMU + BARO · STIMA IN ATTESA";
  return;
 }
 const noFix=nav?.gnss_integrity==="NO_FIX",rejected=nav?.gnss_integrity==="OUTLIER_REJECTED";
 quality.textContent=noFix?"GNSS · NO FIX · INS ONLY":rejected?`GNSS · ${nav.gnss_rejected} FIX RESPINTI`:updates?"GNSS FIX · 5 HZ":"GNSS · IN ATTESA";
 quality.dataset.integrity=noFix||rejected?"degraded":updates?"nominal":"waiting";
 $("#navSolutionDetail").textContent=updates
  ?`HOLD ERROR ${(guidance?.horizontal_position_error_m||0).toFixed(2)} m · HOME ${(guidance?.home_distance_m||0).toFixed(2)} m · LQR Kp ${(guidance?.horizontal_lqr_gains?.[0]||0).toFixed(2)} s⁻² / Kv ${(guidance?.horizontal_lqr_gains?.[1]||0).toFixed(2)} s⁻¹ · σ ${Math.max(...sigma).toFixed(2)} m`
  :"IMU + GNSS · POSIZIONE NED · FIX IN ATTESA";
}
function updateExternalControlStatus(){
 const label=$("#externalLinkStatus"),link=state.engine?.external_control;
 if(!label)return;
 if(!link){label.textContent="WATCHDOG API IN ATTESA DEL MOTORE";return}
 const age=Number.isFinite(link.last_command_age_s)
  ?` · ${link.last_command_age_s.toFixed(2)} / ${link.watchdog_timeout_s.toFixed(2)} s`
  :"";
 const messages={
  DISARMED:"WATCHDOG DISARMATO · GNC ASTRA",
  CONNECTED:"LINK CONTROLLER ATTIVO"+age,
  AUTO_TAKEOVER:"LINK PERSO · GNC ASTRA RIPRESO",
  AUTO_RETURN:"LINK PERSO · DRONE IN RIENTRO AUTOMATICO",
  FORCED_LANDING:"LINK PERSO · PLANATA E ATTERRAGGIO AUTOMATICI",
  TAKEOFF_ABORTED:"LINK PERSO · DECOLLO ABORTITO",
  ROLLOUT_STOP:"LINK PERSO · FRENATA AUTOMATICA",
  MANUAL_OVERRIDE:"CONTROLLO MANUALE · WATCHDOG NON INTERVIENE",
  RECOVERY_COMPLETED:"RECUPERO AUTOMATICO COMPLETATO",
  RECOVERY_FAILED:"RECUPERO AUTOMATICO NON SICURO",
 };
 label.textContent=messages[link.state]||"STATO LINK · "+link.state;
}
function updateOrbitTelemetry(){
 const panel=$("#orbitReadout"),engine=state.engine,visible=state.kind==="space"&&!!engine?.mission_started&&engine.phase!=="LANDED";
 panel.hidden=!visible;
 if(!visible)return;
 const relative=engine.scenario==="orbital",elements=(engine.estimated_orbital_elements&&!relative?engine.estimated_orbital_elements:engine.orbital_elements)||{},distance=value=>Number.isFinite(value)?(value/1000).toFixed(1)+" km":"NON LEGATA",period=value=>Number.isFinite(value)?(value/60).toFixed(1)+" min":"—",guidance=engine.rendezvous_guidance||{},attitude=engine.attitude_control||{};
 const periapsis=elements.periapsis_altitude_m,orbitClass=elements.orbit_type||"UNKNOWN";
 $("#orbitPeri").textContent=Number.isFinite(periapsis)&&periapsis<0?"INTERSECA TERRA":distance(periapsis);$("#orbitApo").textContent=distance(elements.apoapsis_altitude_m);$("#orbitSma").textContent=distance(elements.semi_major_axis_m);$("#orbitEcc").textContent=Number.isFinite(elements.eccentricity)?elements.eccentricity.toFixed(5):"—";$("#orbitInc").textContent=Number.isFinite(elements.inclination_deg)?elements.inclination_deg.toFixed(2)+"°":"—";$("#orbitPeriod").textContent=period(elements.period_s);
 const orbitLabels={SUBORBITAL:"TRAIETTORIA SUBORBITALE",LEO:"ORBITA LEO",ELLIPTIC_EARTH_ORBIT:"ORBITA ELLITTICA",ESCAPE:"FUGA",PARABOLIC_ESCAPE:"FUGA PARABOLICA"};
 $("#orbitReadout summary").textContent=relative?"ELEMENTI ORBITALI · GUIDA RELATIVA RTN/ECI":`${orbitLabels[orbitClass]||"CONICA OSCULATORIA"} · ${engine.estimated_orbital_elements?"STIMA ECI":"ECI"}`;
 [["#orbitRelativeRange",relative?engine.relative_range_m:null,value=>value.toFixed(1)+" m"],["#orbitRelativeSpeed",relative?engine.relative_speed_m_s:null,value=>value.toFixed(3)+" m/s"],["#orbitRendezvousState",relative?(guidance.active?guidance.phase+" · AUTO":"MANUAL OVERRIDE"):null,value=>value]].forEach(([selector,value,format])=>{const cell=$(selector).parentElement;cell.hidden=!relative;$(selector).textContent=value===null||value===undefined?"—":format(value)});
 const momentum=engine.wheel_momentum_body_N_m_s,limits=attitude.wheel_momentum_limit_N_m_s,saturated=attitude.wheel_saturated||[];
 const use=Array.isArray(momentum)&&Array.isArray(limits)?Math.max(...momentum.map((value,index)=>Math.abs(value)/Math.max(limits[index]||0,1e-9))):null;
 [["#orbitAttitudeError",relative?engine.attitude_error_deg:null,value=>value.toFixed(2)+"°"],["#orbitWheelMomentum",relative&&use!==null?use:null,value=>(value*100).toFixed(0)+"% capacità"],["#orbitWheelStatus",relative?(saturated.some(Boolean)?"SATURAZIONE":"RUOTE NOMINALI"):null,value=>value]].forEach(([selector,value,format])=>{const cell=$(selector).parentElement;cell.hidden=!relative;$(selector).textContent=value===null||value===undefined?"—":format(value)});
}
function updateFlightPfd(){
 const panel=document.getElementById('flightPfd'),e=state.engine;
 if(!panel)return;
 panel.hidden=state.kind==='space'||!e;
 if(panel.hidden)return;
 const att=e.attitude_deg||[0,0,0];
 const value=(id,v)=>{const node=document.getElementById(id);if(node)node.textContent=v};
 const vs=-(e.velocity_ned_m_s?.[2]??(()=>{
  const vel=e.velocity_body_m_s||[0,0,0],roll=att[0]*Math.PI/180,pitch=att[1]*Math.PI/180;
  return -Math.sin(pitch)*vel[0]+Math.sin(roll)*Math.cos(pitch)*vel[1]+Math.cos(roll)*Math.cos(pitch)*vel[2]
 })());
 const pitch=Math.max(-85,Math.min(85,att[1])),roll=Math.max(-180,Math.min(180,att[0]));
 document.getElementById('pfdHorizonSky').style.transform=`translateY(${pitch*.75}px) rotate(${-roll}deg)`;
 value('pfdMode',state.mode.toUpperCase());value('pfdAirspeed',(e.air_relative_speed_m_s??e.speed_m_s??0).toFixed(1));
 value('pfdAltitude',(e.altitude_m??0).toFixed(1));value('pfdHeading',(((att[2]%360)+360)%360).toFixed(0).padStart(3,'0')+'°');
 value('pfdVs',(vs>=0?'+':'')+vs.toFixed(1));value('pfdG',(e.load_factor_g??0).toFixed(2));
 value('pfdQ',(e.environment?.dynamic_pressure_Pa??0).toFixed(0));
 const takeoffStatus=document.getElementById('pfdTakeoffStatus'),tko=e.takeoff;
 if(takeoffStatus){takeoffStatus.hidden=state.kind!=='aircraft'||e.phase!=='TAKEOFF'||!tko;if(!takeoffStatus.hidden){const speed=e.air_relative_speed_m_s??0;takeoffStatus.textContent=`Vr ${tko.rotation_speed_m_s.toFixed(0)} m/s · ${speed.toFixed(0)} m/s · RUNWAY ${tko.runway_remaining_m.toFixed(0)} m · ${tko.rotation_ready?'ROTATE':'ACCELERATE'}`;}}
 const stalled=state.kind==='aircraft'&&e.aerodynamics?.stall_assessment_valid&&e.aerodynamics?.stall_margin_deg<2;
 const caution=document.getElementById('pfdCaution');caution.hidden=!stalled;caution.textContent=stalled?'STALL MARGIN LOW - LOWER ALPHA':'FLIGHT ENVELOPE WARNING';
}
function update(){updateFlightPfd();syncPilotButton();updateMissionBadge();updateOrbitTelemetry();updateNavPanel();updateExternalControlStatus();const a=info[state.kind];$("#clock").textContent=tc(state.seconds);$("#eventTime").textContent="T+"+pad(Math.floor(state.seconds/60))+":"+pad(Math.floor(state.seconds%60));if(state.engine){$("#position").textContent=(state.engine.altitude_m/(state.kind==="drone"?1:1000)).toFixed(state.kind==="drone"?0:1);const displayedSpeed=state.kind==="aircraft"?(state.engine.air_relative_speed_m_s??state.engine.speed_m_s):state.kind==="drone"?(state.engine.ground_speed_m_s??state.engine.speed_m_s):state.engine.speed_m_s;$("#velocity").textContent=(displayedSpeed/(state.kind==="space"?1000:1)).toFixed(state.kind==="space"?3:1);const orbitalControl=state.kind==="space"&&state.engine.scenario==="orbital",commandOnly=state.kind==="space"&&state.engine.attitude_state_status==="NOT_MODELLED",attitude=state.engine.attitude_deg;$("#spaceAttitudeControl").hidden=!orbitalControl;if(orbitalControl&&attitude){$("#attitudeLabel").textContent="ATTITUDE · R/P/Y";$("#attitudeContext").textContent="BODY → ECI · LVLH · e="+(state.engine.attitude_error_deg||0).toFixed(2)+"°";$("#attitude").textContent=attitude.map(value=>Number(value).toFixed(1)+"°").join(" / ")}else if(orbitalControl){const command=state.engine.command||{};$("#attitudeLabel").textContent="RCS COMMAND · MANUAL";$("#attitudeContext").textContent="THROTTLE · PITCH · ROLL";$("#attitude").textContent=(command.throttle_pct||0).toFixed(0)+"% / "+(command.pitch_deg||0).toFixed(0)+"° / "+(command.roll_deg||0).toFixed(0)+"°"}else if(commandOnly){const command=state.engine.attitude_command_deg||[0,0,0];$("#attitudeLabel").textContent="THRUST CMD · R/P/Y";$("#attitudeContext").textContent="BODY ATTITUDE NOT MODELLED";$("#attitude").textContent=command.map(value=>Number(value).toFixed(1)+"°").join(" / ")}else{$("#attitudeLabel").textContent="ATTITUDE · R/P/Y";$("#attitudeContext").textContent=state.kind==="space"?"BODY → ECI · EULER 3-2-1 · TVC/RCS":"BODY FRAME · 6-DOF";if(attitude)$("#attitude").textContent=attitude.map(value=>Number(value).toFixed(1)+"°").join(" / ")};if($("#rangeValue"))$("#rangeValue").textContent=state.engine.scenario==="orbital"?Math.hypot(...(state.engine.relative_navigation_estimate?.position_rtn_m||state.engine.relative_position_rtn_m||[0,0,0])).toFixed(1)+" m · RTN":"MISSION PROFILE";if($("#environmentReadout")){const env=state.engine.environment||{},name=env.atmosphere_model||"COESA76",eci=state.kind==="space"?"ECI · μ="+(env.mu_earth_m3_s2/1e14).toFixed(4)+"×10¹⁴ m³/s² · J₂="+env.J2.toExponential(3)+" · ":"",drag=state.kind==="space"?" · DRAG "+(env.drag_model_enabled?"ON":"OFF"):"",domain=env.in_model_domain===false?" · ATMOSFERA FUORI DOMINIO":"",battery=state.engine.battery?" · BATTERIA "+state.engine.battery.energy_remaining_Wh.toFixed(1)+" Wh · "+state.engine.battery.power_draw_W.toFixed(0)+" W":"",acs=state.kind==="space"&&state.engine.acs_propellant_capacity_kg>0?" · ACS "+state.engine.acs_propellant_kg.toFixed(1)+" kg ("+state.engine.acs_propellant_pct.toFixed(0)+"%)":"",wind=state.kind!=="space"&&env.wind_speed_m_s>0?" · "+(env.wind_profile_model==="LINEAR_ALTITUDE_NED_WITH_ENDPOINT_CLAMP"?"VENTO A QUOTA ":"VENTO ")+env.wind_speed_m_s.toFixed(1)+" m/s"+(env.wind_profile_endpoint_clamped?" · PROFILO SATURATO AL NODO ESTREMO":"")+" · VERSO "+env.wind_direction_to_deg.toFixed(0)+"°":"",gust=state.kind!=="space"&&env.turbulence?.model==="DRYDEN_FROZEN_FIELD_SPECTRAL"?" · DRYDEN · RAFFICA "+Math.hypot(...(env.turbulence_gust_velocity_ned_m_s||[0,0,0])).toFixed(2)+" m/s · σw "+env.turbulence.sigma_uvw_m_s[2].toFixed(2)+" m/s":"",qbar=" · q="+formatPressure(env.dynamic_pressure_Pa),load=Number.isFinite(state.engine.load_factor_g)?" · CARICO "+state.engine.load_factor_g.toFixed(2)+" g":"",aerodynamic=state.kind==="aircraft"&&state.engine.aerodynamics?(()=>{const a=state.engine.aerodynamics;if(a.stall_assessment_valid===false)return " · AERO LOW-q · STALLO N/A";return ` · α ${a.angle_of_attack_deg.toFixed(1)}° · β ${a.angle_of_sideslip_deg.toFixed(1)}° · CL ${a.lift_coefficient.toFixed(2)} · CD ${a.drag_coefficient.toFixed(3)} · margine stallo ${a.stall_margin_deg.toFixed(1)}°`})():"",aircraftPropulsion=state.kind==="aircraft"&&state.engine.propulsion?(()=>{const p=state.engine.propulsion;return ` · P ${p.actual_power_pct.toFixed(0)}%/${p.commanded_power_pct.toFixed(0)}% · T ${p.thrust_N.toFixed(0)} N · Pₛ ${(p.shaft_power_W/1000).toFixed(0)} kW · ṁ ${p.fuel_flow_kg_s.toFixed(3)} kg/s`})():"",controlSurfaces=state.kind==="aircraft"&&state.engine.control_surfaces?" · δa/e/r "+state.engine.control_surfaces.actual_deflection_deg.map(value=>value.toFixed(1)).join("/")+"°":"",rotorTelemetry=state.kind==="drone"&&state.engine.propulsion_actuators?(()=>{const p=state.engine.propulsion_actuators,rpm=p.motor_speed_actual_rpm.reduce((sum,value)=>sum+value,0)/p.rotor_count;return ` · ΣT ${p.total_thrust_actual_N.toFixed(1)}/${p.total_thrust_command_N.toFixed(1)} N · RPM ${rpm.toFixed(0)}`})():"",heat=env.stagnation_heating_active?` · q̇stag ${Math.round(env.stagnation_point_convective_heat_flux_W_m2).toLocaleString("it-IT")} W/m² · Qconv ${((state.engine.mission_metrics?.stagnation_point_convective_heat_load_J_m2??0)/1e6).toFixed(2)} MJ/m²`:"";$("#environmentReadout").textContent=eci+name+" · ρ="+formatEnvironmentValue(env.density_kg_m3)+" kg/m³ · T="+env.temperature_K.toFixed(1)+" K · p="+formatPressure(env.pressure_Pa)+wind+gust+qbar+load+aerodynamic+aircraftPropulsion+controlSurfaces+rotorTelemetry+drag+domain+battery+heat+acs}}else{$("#position").textContent=a[9];$("#velocity").textContent=a[13]}$("#resource").textContent=Math.round(state.fuel);$("#resourceBar").style.width=state.fuel+"%";const duration=state.kind==="space"?(state.engine?.scenario==="leo-return"?12000:state.engine?.scenario==="orbital"?700:2400):state.kind==="drone"?60:360;$("#progress").style.width=Math.min(100,state.seconds/duration*100)+"%"}

function applyKind(){const a=info[state.kind],savedMissionProfile=localStorage.getItem("astra-mission-profile-v1"),leoStack=state.modelPreferences.space==="astra-custom-stack"&&leoReturnAvailable(state.customDesign.stages);state.missionProfile=state.kind==="space"&&savedMissionProfile==="orbital"?"orbital":state.kind==="space"&&(savedMissionProfile==="leo-return"||(savedMissionProfile===null&&leoStack))?"leo-return":"mission";state.pendingDesignProfile=null;host.dataset.kind=state.kind;state.az=state.kind==="space"?2.66:.16;state.el=state.kind==="space"?.42:.22;state.zoom=state.kind==="space"?8.2:8.5;state.modelId=state.modelPreferences[state.kind]||defaultModels[state.kind];state.visualModelId=state.visualModelPreferences[state.kind]||defaultVisualModels[state.kind];$("#openVehicleLab").hidden=state.kind!=="space";$("#brakeControl").hidden=state.kind!=="aircraft";$("#windControl").hidden=state.kind==="space";$("#windPreset").value=state.windPreset;if($("#windModelSummary"))$("#windModelSummary").textContent=state.windPreset==="shear"?"Profilo assoluto NED interpolato linearmente tra quote; tenuto costante oltre i nodi estremi.":"Vento medio NED costante. Le forze dipendono dalla velocità rispetto all’aria.";$("#drydenPreset").value=state.drydenPreset;syncDrydenControls();$("#vehicleImportKind").value=state.kind;populateModelOptions();populateVisualModelOptions();selectVisualModel();updateImportUI();if($("#disciplineDialog")?.open)renderDisciplineLibrary();$$(".domain").forEach(button=>button.classList.toggle("active",button.dataset.kind===state.kind));[["heroTitle",a[0]],["heroSub",a[1]],["frame",a[2]],["mission",a[3]],["model",a[6]],["scenario",a[7]],["positionLabel",a[8]],["positionUnit",a[10]],["positionContext",a[11]],["velocityLabel",a[12]],["velocityUnit",a[14]],["velocityContext",a[15]],["resourceLabel",a[16]],["resourceUnit",a[18]],["nextEvent",a[19]]].forEach(x=>$("#"+x[0]).textContent=x[1]);$("#vehicle").textContent=a[4]+" "+a[5];$("#crosshair b").textContent="TARGET · "+(state.kind==="space"?"APOGEO":state.kind==="aircraft"?"PISTA":"WP-01");state.seconds=0;state.running=false;state.engine=null;state.lastAdvance=performance.now();$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";$("#statusText").textContent="CONNECTING";$("#simState").textContent="CONNECTING";$("#currentEvent").textContent="STANDBY";updateMissionPresentation();updateLesson();update();return resetEngine({startRecording:false})}
const applyKindWithoutCamera=applyKind;applyKind=function(){applyKindWithoutCamera();state.az=state.kind==="space"?2.66:state.kind==="aircraft"?.72:.16;state.el=state.kind==="space"?.19:state.kind==="drone"?.45:state.kind==="aircraft"?.24:.14;state.zoom=state.kind==="space"?8.2:state.kind==="drone"?5.8:6.5;if(state.kind==="space"){state.spaceZoom=SPACE_LAUNCH_CAMERA_RANGE;state.spaceCameraManual=false}state.visualPropellerPhase=0;state.visualPropellerRpm=0;state.visualPropellerModelId=null;state.visualAnimationTime=null};

if(!gl&&!ctx2d){host.innerHTML='<div class="webgl-error"><b>RENDERER NON DISPONIBILE</b><span>Il browser non offre WebGL 2 né Canvas 2D. Aggiorna il browser per usare ASTRA.</span></div>';applyKind()}else{try{if(gl)init();else{resize();host.dataset.renderer="compat"}applyKind();requestAnimationFrame(frame)}catch(e){host.innerHTML='<div class="webgl-error"><b>ERRORE RENDERER 3D</b><span>'+String(e.message||e)+'</span></div>';console.error(e)}}
window.addEventListener("resize",resize);if("ResizeObserver"in window)new ResizeObserver(resize).observe(host);document.addEventListener("visibilitychange",()=>{state.lastAdvance=performance.now();frame.lastRender=0});$("#vehicleImportKind").addEventListener("change",updateImportUI);$("#loadVehicle3d").addEventListener("click",()=>$("#vehicleModelFile").click());$("#vehicleModelFile").addEventListener("change",e=>importVehicleFile(e.target.files?.[0],$("#vehicleImportKind").value));$("#vehicleModelOrientation").addEventListener("change",e=>{state.modelOrientations[$("#vehicleImportKind").value]=e.target.value});$("#removeVehicle3d").addEventListener("click",()=>{const kind=$("#vehicleImportKind").value,asset=state.userVehicles[kind];if(!asset)return;asset.primitives.forEach(x=>disposeGeometry(x.geometry));(asset.textures||[]).forEach(t=>gl.deleteTexture(t));state.userVehicles[kind]=null;updateImportUI();populateModelOptions();toast("Modello personale rimosso da questa sessione")});loadModelCatalog();loadVisualCatalog();$("#visualVehicleModel").addEventListener("change",e=>{state.visualModelId=e.target.value;state.visualPropellerPhase=0;state.visualPropellerRpm=0;state.visualPropellerModelId=e.target.value;state.visualAnimationTime=performance.now();state.visualModelPreferences[state.kind]=state.visualModelId;localStorage.setItem("astra-visual-model-selection-v1",JSON.stringify(state.visualModelPreferences));state.running=false;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";state.careerActive=false;selectVisualModel();toast("Modello 3D caricato · fisica ASTRA invariata")});$("#vehicleModel").addEventListener("change",async e=>{state.modelId=e.target.value;if(state.kind==="space"&&state.missionProfile==="orbital"&&state.modelId==="astra-custom-stack"){state.missionProfile="mission";localStorage.setItem("astra-mission-profile-v1","mission");updateMissionPresentation("mission")}state.modelPreferences[state.kind]=state.modelId;localStorage.setItem("astra-model-selection-v1",JSON.stringify(state.modelPreferences));state.running=false;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";state.careerActive=false;state.careerAwarded=false;state.careerObservations=[];state.careerPhases.clear();const result=await resetEngine();if(isCurrentReset(result))toast("Modello fisico e parametri caricati");});$("#learnToggle").addEventListener("click",e=>{const enabled=document.body.classList.toggle("expert-mode");e.currentTarget.setAttribute("aria-pressed",String(!enabled));e.currentTarget.textContent=enabled?"GUIDA OFF":"GUIDA ON";});
function setProduct(mode){
 const game=mode==="game";
 const sticks=$("#pilotJoystickPair");
 const target=game?$("#gameStickMount"):$("#manualPanel");
 if(sticks&&target&&sticks.parentElement!==target){if(!game){const intro=$("#manualPanel .manual-intro");if(intro)intro.after(sticks);else target.prepend(sticks)}else target.append(sticks)}
 $("#gamePilotDock").hidden=!game;
 if(game&&state.mode!=="manual")$('.mode[data-mode="manual"]')?.click();
 if(!game){document.body.classList.remove("game-pilot-active");}else{document.body.classList.add("game-pilot-active");}
 state.product=mode;document.body.classList.toggle("game-mode",mode==="game");$("#careerCard").hidden=mode!=="game";$$(".product-mode").forEach(b=>{const active=b.dataset.product===mode;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active))});state.careerActive=mode==="game"&&!!state.engine?.mission_started&&!state.careerAwarded;renderCareer();syncPilotButton()}
function readDesignStages(){return $$(".design-stage-control").map(row=>({tank_count:Number(row.querySelector("[data-stage-field=tank_count]").value),engine_count:Number(row.querySelector("[data-stage-field=engine_count]").value)}))}
function renderDesignStages(stages){
 const host=$("#designStageControls"),cfg=state.vehicleParts?.configuration||{min_tanks:1,max_tanks:3,min_engines:1,max_engines:8};
 host.replaceChildren(...stages.map((stage,index)=>{
  const row=document.createElement("div");row.className="design-stage-control";
  const title=document.createElement("strong");title.textContent=`STADIO ${index+1} · ${index===0?"BOOSTER":index===stages.length-1?"SUPERIORE":"INTERMEDIO"}`;row.append(title);
  for(const [field,label,min,max] of [["tank_count","SERBATOI",cfg.min_tanks,cfg.max_tanks],["engine_count","MOTORI",cfg.min_engines,cfg.max_engines]]){const wrap=document.createElement("label");wrap.append(document.createTextNode(label));const input=document.createElement("input");input.type="number";input.min=min;input.max=max;input.step="1";input.value=stage[field];input.dataset.stageField=field;wrap.append(input);row.append(wrap)}
  const remove=document.createElement("button");remove.type="button";remove.className="design-stage-remove";remove.dataset.removeStage=String(index);remove.textContent="×";remove.title="Rimuovi stadio";remove.disabled=stages.length<=1;row.append(remove);return row
 }));$("#addDesignStage").disabled=stages.length>=(cfg.max_stages??4)
}
function updateVehicleDesignPreview(){
 const stages=readDesignStages(),name=$("#designName").value.trim(),cfg=state.vehicleParts?.configuration,p=state.vehicleParts?.parts;
 const design=name.length>0&&name.length<=32?calculateVehicleDesign(stages):null;
 if(!design){$("#designDryMass").textContent=$("#designWetMass").textContent=$("#designTwr").textContent=$("#designDeltaV").textContent="—";$("#designStatus").textContent=!name?"Inserisci un nome per il veicolo.":!p?"Catalogo fisico non raggiungibile.":"Correggi il numero di serbatoi o motori nei singoli stadi.";$("#applyVehicleDesign").disabled=true;return}
 $("#designCapsuleModule").textContent=`CAPSULA · ${p.capsule.dry_mass_kg.toLocaleString("it-IT")} kg`;
 $("#designDryMass").textContent=design.dry.toLocaleString("it-IT")+" kg";$("#designWetMass").textContent=design.wet.toLocaleString("it-IT")+" kg";$("#designTwr").textContent=design.stageTwr.map(x=>x.toFixed(2)).join(" / ");$("#designDeltaV").textContent=(design.deltaV/1000).toFixed(2)+" km/s";
 const preview=$("#designStagePreview");preview.replaceChildren(...[...design.stages].reverse().map((stage,position)=>{const index=design.stages.length-position,unit=document.createElement("div");unit.className="stage-preview-unit";const label=document.createElement("small");label.className="stage-preview-label";label.textContent=`STADIO ${index} · ${index===1?"BOOSTER":index===design.stages.length?"SUPERIORE":"INTERMEDIO"} · T/W@SL ${stage.twr_at_sea_level.toFixed(2)}`;const tanks=document.createElement("div");tanks.className="stage-preview-tanks";tanks.append(...Array.from({length:stage.tank_count},()=>document.createElement("i")));const engines=document.createElement("div");engines.className="stage-preview-engines";engines.append(...Array.from({length:stage.engine_count},()=>document.createElement("i")));unit.append(label,tanks,engines);return unit}));
 const threshold=cfg?.minimum_liftoff_twr??1.1,meetsTwr=design.twr>=threshold;$("#designStatus").textContent=meetsTwr?`Booster compatibile · T/W conservativo a livello del mare per stadio. La spinta di volo usa la pressione locale; Δv ideale: ${(design.deltaV/1000).toFixed(2)} km/s.`:`Booster sottodimensionato: T/W al decollo ${design.twr.toFixed(2)}, minimo ${threshold.toFixed(2)}.`;$("#applyVehicleDesign").disabled=!meetsTwr
}
$("#openVehicleLab").addEventListener("click",()=>{$("#designName").value=state.customDesign.name;renderDesignStages(state.customDesign.stages);updateVehicleDesignPreview();$("#vehicleLab").showModal()});
$("#closeVehicleLab").addEventListener("click",()=>$("#vehicleLab").close());
$("#stageNow").addEventListener("click",async()=>{const button=$("#stageNow");if(button.disabled||state.resetPending||!state.engine)return;button.disabled=true;const epoch=state.requestEpoch;try{const data=await api("/stage",{});if(epoch===state.requestEpoch)consumeEngine(data)}catch(error){if(epoch===state.requestEpoch){toast("Staging non disponibile: "+error.message);populateModelOptions()}}});
$("#designStageControls").addEventListener("input",updateVehicleDesignPreview);$("#designName").addEventListener("input",updateVehicleDesignPreview);$("#designStageControls").addEventListener("click",e=>{const index=Number(e.target.dataset.removeStage);if(!Number.isInteger(index))return;const stages=readDesignStages();if(stages.length<=1)return;stages.splice(index,1);renderDesignStages(stages);updateVehicleDesignPreview()});$("#addDesignStage").addEventListener("click",()=>{const stages=readDesignStages(),max=state.vehicleParts?.configuration?.max_stages??4;if(stages.length>=max){toast(`Massimo ${max} stadi`);return}stages.push({tank_count:1,engine_count:1});renderDesignStages(stages);updateVehicleDesignPreview()});$("#loadGuidedStack").addEventListener("click",()=>{state.pendingDesignProfile="mission";$("#designName").value="ASTRA-LAB M2 KESTREL";renderDesignStages([{tank_count:1,engine_count:2},{tank_count:1,engine_count:1}]);updateVehicleDesignPreview();toast("Stack didattico a due stadi caricato · 5,34 km/s di Δv ideale")});
$("#loadLeoReturnStack").addEventListener("click",()=>{state.pendingDesignProfile="leo-return";$("#designName").value="ASTRA LEO KESTREL";renderDesignStages([{tank_count:3,engine_count:8},{tank_count:3,engine_count:5},{tank_count:3,engine_count:3},{tank_count:3,engine_count:2}]);updateVehicleDesignPreview();toast("Stack LEO caricato · 9,26 km/s ideali · circolarizzazione, un’orbita e rientro controllato")});
$("#applyVehicleDesign").addEventListener("click",async()=>{const name=$("#designName").value.trim(),stages=readDesignStages();state.customDesign={name,stages};if(state.pendingDesignProfile){const requested=state.pendingDesignProfile;state.pendingDesignProfile=null;state.missionProfile=requested==="leo-return"&&!leoReturnAvailable(stages)?"mission":requested}else if(state.missionProfile==="leo-return"&&!leoReturnAvailable(stages)||state.missionProfile==="orbital"){state.missionProfile="mission";} localStorage.setItem("astra-mission-profile-v1",state.missionProfile);localStorage.setItem("astra-vehicle-design-v1",JSON.stringify(state.customDesign));state.modelId="astra-custom-stack";state.modelPreferences.space=state.modelId;localStorage.setItem("astra-model-selection-v1",JSON.stringify(state.modelPreferences));state.running=false;state.careerActive=false;state.careerAwarded=false;populateModelOptions();$("#vehicleModel").value=state.modelId;const result=await resetEngine();if(!isCurrentReset(result))return;$("#vehicleLab").close();toast(`Stack da ${stages.length} stadi assemblato · separazione automatica attiva`) });
$$('.product-mode').forEach(b=>b.addEventListener("click",()=>setProduct(b.dataset.product)));
function syncPilotButton(){const btn=$("#gameTakeControl");if(!btn)return;const active=state.mode==="manual";btn.setAttribute("aria-pressed",String(active));btn.textContent=active?"PILOT ACTIVE":"TAKE CONTROL";const takeoff=$("#gameTakeoff");if(takeoff)takeoff.hidden=state.kind!=="aircraft"||!!state.engine?.mission_started&&state.engine?.phase!=="TAKEOFF";}
$("#gameTakeControl").addEventListener("click",()=>$(state.mode==="manual"?'.mode[data-mode="gnc"]':'.mode[data-mode="manual"]')?.click());
$("#gameTakeoff").addEventListener("click",async()=>{
 if(state.kind!=="aircraft"||state.resetPending||state.launchPending)return;
 if(["CRASHED","ABORTED","LANDED"].includes(state.engine?.phase)){
  const result=await resetEngine();if(!isCurrentReset(result))return;
 }
 if(state.mode!=="manual")$('.mode[data-mode="manual"]')?.click();
 state.brakes=0;$("#brakes").value="0";$("#brakesOut").value="0%";
 setManualValues({thrust:100,pitch:0,roll:0},false);
 stickState.left.y=-1;drawStick("left");
 await sendCommand({mode:"manual",throttle_pct:100,pitch_deg:0,roll_deg:0,brakes_pct:0});
 if(!state.running&&!state.launchPending)$("#play")?.click();
 toast("TAKEOFF · MANETTA 100% · ROTAZIONE ASSISTITA A Vr");
});
const techPreferenceKey='astra-tech-visibility-v1';
function setTechnicalVisibility(visible){
 document.body.classList.toggle('tech-hidden',!visible);
 const toggle=$("#techToggle");toggle?.setAttribute('aria-pressed',String(visible));
 if(toggle)toggle.setAttribute('title',visible?'Hide technical telemetry':'Show technical telemetry');
 const caption=$("#techToggleLabel");if(caption)caption.textContent=visible?'HIDE DATA':'SHOW DATA';
 try{localStorage.setItem(techPreferenceKey,visible?'1':'0')}catch{}
}
$("#techToggle").addEventListener('click',()=>setTechnicalVisibility(document.body.classList.contains('tech-hidden')));
setTechnicalVisibility(localStorage.getItem(techPreferenceKey)!=='0');
$$('.career-track-btn').forEach(b=>b.addEventListener("click",()=>{state.careerTrack=b.dataset.track;state.careerAwarded=false;state.lastCareerScore=0;renderCareer()}));
$("#careerObserve").addEventListener("click",()=>{if(!state.engine){toast("Avvia una missione per raccogliere dati");return}const phase=state.engine.phase||"READY";if(state.careerObservations.some(x=>x.phase===phase)){toast("Hai già un’osservazione della fase "+(phaseText[phase]||phase));return}const record={vehicle:state.engine.vehicle_name,model_id:state.engine.model_id,phase,time_s:state.engine.time_s,altitude_m:state.engine.altitude_m,speed_m_s:state.engine.speed_m_s,mission_metrics:state.engine.mission_metrics,environment:state.engine.environment,navigation_estimate:state.engine.navigation_estimate||null,attitude_deg:state.engine.attitude_deg||state.engine.attitude_command_deg||null};state.careerObservations.push(record);campaign.observations.push(record);campaign.observations=campaign.observations.slice(-500);persistCareer();renderCareer();toast("Osservazione salvata localmente · "+(phaseText[phase]||phase))});
$("#missionProfile").addEventListener("change",async event=>{const requested=event.target.value;if(requested==="leo-return"&&!leoReturnAvailable()){event.target.value=state.missionProfile;toast("Stack insufficiente: serve Δv ≥ 9,2 km/s e T/W ≥ 1,1 per stadio");return}if((requested==="orbital"&&state.modelId==="astra-custom-stack")||(requested!=="orbital"&&state.modelId==="astra-leo-servicer")){state.modelId=defaultModels.space;state.modelPreferences.space=state.modelId;localStorage.setItem("astra-model-selection-v1",JSON.stringify(state.modelPreferences))}state.missionProfile=requested;localStorage.setItem("astra-mission-profile-v1",requested);state.running=false;state.careerActive=false;state.careerAwarded=false;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";const result=await resetEngine();if(!isCurrentReset(result))return;toast(requested==="leo-return"?"Missione LEO caricata · un’orbita, deorbita e atterraggio":requested==="orbital"?"Rendezvous ECI/LVLH caricato · RCS automatico verso il punto a 20 m":"Profilo suborbitale di rientro caricato")});
$$(".domain").forEach(b=>b.addEventListener("click",async()=>{state.kind=b.dataset.kind;const result=await applyKind();if(isCurrentReset(result))toast(info[state.kind][7]+" caricato")}));
$$(".mode").forEach(b=>b.addEventListener("click",()=>{state.mode=b.dataset.mode==="gnc"?"auto":b.dataset.mode;if(state.mode==="manual"){state.yaw=state.engine?.attitude_deg?.[2]||0;state.roll=state.engine?.attitude_deg?.[0]||0;state.pitch=state.engine?.attitude_deg?.[1]||0;if(state.kind==="drone"&&state.thrust===0){const parameters=state.engine?.vehicle_parameters||{};const mass=state.engine?.mass_kg||parameters.mass_kg||1;const maxThrust=parameters.max_thrust_N||state.engine?.max_thrust_N||mass*9.80665*2;state.thrust=Math.max(0,Math.min(100,100*mass*9.80665/maxThrust))}setManualValues({yaw:state.yaw,roll:state.roll,pitch:state.pitch,thrust:state.thrust},false)}sendCommand();const py=state.mode==="python",manual=state.mode==="manual";$("#gncPanel").classList.toggle("hidden",py||manual);$("#manualPanel").classList.toggle("hidden",!manual);$("#pythonPanel").classList.toggle("hidden",!py);$("#modeState").textContent=py?"CODE API":manual?"MANUAL OVERRIDE":"GNC AUTO";$$(".mode").forEach(x=>x.classList.toggle("active",x===b));syncPilotButton()}));
$("#play").addEventListener("click",async()=>{
 if(state.resetPending||state.launchPending)return;
 if(state.running){state.running=false;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>RIPRENDI MISSIONE</span>";$("#statusText").textContent="PAUSED";$("#currentEvent").textContent="IN PAUSA";return}
 let epoch=state.requestEpoch;state.launchPending=true;$("#play").disabled=true;
 try{
  if(!state.engine||["LANDED","CRASHED","ABORTED"].includes(state.engine.phase)){
   const result=await resetEngine({startRecording:false});epoch=result.epoch;if(!isCurrentReset(result))return
  }
  if(!state.engine.mission_started){
   startMissionRecording(state.engine);state.careerObservations=[];state.careerPhases.clear();state.careerAwarded=false;state.lastCareerScore=0;
   const launchData=await api("/launch",{});if(epoch!==state.requestEpoch)return;
   state.careerActive=state.product==="game";consumeEngine(launchData)
  }else if(state.product==="game")state.careerActive=true;
  if(epoch!==state.requestEpoch)return;
  state.running=true;$("#play").classList.add("running");$("#play").innerHTML="<b>Ⅱ</b><span>PAUSA MISSIONE</span>";state.lastAdvance=performance.now();$("#statusText").textContent="RUNNING";$("#simState").textContent="MISSION ACTIVE";renderCareer()
 }catch(error){
  if(epoch!==state.requestEpoch)return;
  state.running=false;state.careerActive=false;$("#statusText").textContent="LAUNCH FAILED";$("#play").innerHTML="<b>↻</b><span>RIPROVA AVVIO</span>";
  toast("Avvio missione non riuscito: "+error.message)
 }finally{state.launchPending=false;$("#play").disabled=state.resetPending}
});
$("#reset").addEventListener("click",async()=>{state.spaceCameraManual=false;if(state.kind==="space")state.el=.19;state.running=false;state.seconds=0;state.careerActive=false;state.careerAwarded=false;state.lastCareerScore=0;state.careerObservations=[];state.careerPhases.clear();const result=await resetEngine();if(!isCurrentReset(result))return;$("#play").classList.remove("running");$("#play").innerHTML="<b>▶</b><span>AVVIA MISSIONE</span>";$("#statusText").textContent="READY";$("#simState").textContent="READY";update();renderCareer();toast("Veicolo riportato alla piazzola di lancio")});
$("#step").addEventListener("click",async()=>{if(state.resetPending||state.launchPending||!state.engine)return;const epoch=state.requestEpoch;try{const data=await api("/step",{dt_s:.1*state.speed});if(epoch===state.requestEpoch)consumeEngine(data)}catch{if(epoch===state.requestEpoch)toast("API di simulazione non raggiungibile")}});
$$(".speed").forEach(b=>b.addEventListener("click",()=>{$$(".speed").forEach(x=>x.classList.toggle("selected",x===b));state.speed=Number(b.dataset.speed)}));
let manualCommandBusy=false,manualCommandQueued=false;
function queueManualCommand(){manualCommandQueued=true;if(manualCommandBusy)return;manualCommandBusy=true;const epoch=state.requestEpoch;const pump=async()=>{while(manualCommandQueued&&epoch===state.requestEpoch&&state.mode==="manual"){manualCommandQueued=false;const command={throttle_pct:state.thrust,roll_deg:state.roll,pitch_deg:state.pitch,yaw_deg:state.yaw,...(state.kind==="aircraft"?{brakes_pct:state.brakes}:{}),...(state.kind==="space"&&state.engine?.scenario==="orbital"?{attitude_target_deg:state.attitudeTarget}:{})};await sendCommand(command)}manualCommandBusy=false};pump()}
function setManualValues(values,send=true){for(const [key,value] of Object.entries(values)){const spec={roll:[-45,45,"rollOut"],pitch:[-45,45,"pitchOut"],yaw:[-180,180,"yawOut"],thrust:[0,100,"thrustOut"]}[key];if(!spec)continue;const [min,max,out]=spec;state[key]=Math.max(min,Math.min(max,Number(value)));const input=$("#"+key);input.value=String(state[key]);$("#"+out).value=key==="thrust"?state[key]+"%":state[key].toFixed(0)+"°";const pct=(state[key]-min)/(max-min)*100;input.style.background="linear-gradient(90deg,#70e8c5 "+pct+"%,#3b4b55 "+pct+"%)"}$("#stickYaw").value=state.yaw.toFixed(0)+"°";$("#stickRoll").value=state.roll.toFixed(0)+"°";$("#stickPitch").value=state.pitch.toFixed(0)+"°";$("#stickThrust").value=state.thrust.toFixed(0)+"%";if(send&&state.mode==="manual")queueManualCommand()}
[["roll","roll"],["pitch","pitch"],["yaw","yaw"],["thrust","thrust"]].forEach(([id,key])=>$("#"+id).addEventListener("input",e=>setManualValues({[key]:Number(e.target.value)})));
[["attRoll",0],["attPitch",1],["attYaw",2]].forEach(([id,index])=>$("#"+id).addEventListener("input",event=>{state.attitudeTarget[index]=Number(event.target.value);$("#"+id+"Out").value=state.attitudeTarget[index].toFixed(0)+"°";queueManualCommand()}));$("#brakes").addEventListener("input",e=>{state.brakes=Number(e.target.value);$("#brakesOut").value=state.brakes+"%";const pct=state.brakes;e.target.style.background="linear-gradient(90deg,#70e8c5 "+pct+"%,#3b4b55 "+pct+"%)";queueManualCommand()});
const stickState={left:{x:0,y:1},right:{x:0,y:0}};

const pilotKeys=new Set();let lastPilotInputAt=0;let lastPilotRollKey=false,lastPilotPitchKey=false;
const pilotKeyCodes=new Set(['KeyW','KeyS','KeyA','KeyD','KeyQ','KeyE','KeyR','KeyF','KeyB','Space','KeyC']);
function pilotKeyboardEnabled(){return state.mode==='manual'&&!document.querySelector('dialog[open]')&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!document.activeElement?.isContentEditable}
window.addEventListener('keydown', event=>{
 if(!pilotKeyCodes.has(event.code)||!pilotKeyboardEnabled())return;
 if(event.repeat && (event.code==='Space'||event.code==='KeyC'))return;
 event.preventDefault();
 if(event.code==='Space'){document.querySelector('#play')?.click();return}
 if(event.code==='KeyC'){state.az=state.kind==='space'?2.66:.16;state.el=state.kind==='space'?.2:.22;state.spaceCameraManual=false;return}
 pilotKeys.add(event.code);
});
window.addEventListener('keyup',event=>{if(pilotKeyCodes.has(event.code)){pilotKeys.delete(event.code);if(pilotKeyboardEnabled())event.preventDefault()}});
window.addEventListener('blur',()=>pilotKeys.clear());
document.addEventListener('visibilitychange',()=>{if(document.hidden)pilotKeys.clear()});
function updatePilotInputs(t){
 if(state.mode!=='manual'||state.resetPending||!state.engine)return;
 const dt=lastPilotInputAt?Math.min(.1,Math.max(0,(t-lastPilotInputAt)/1000)):0;
 lastPilotInputAt=t;
 const keys=keyboardAxes(pilotKeyboardEnabled()?pilotKeys:new Set());
 const gamepads=navigator.getGamepads?.()||[];
 const gamepad=[...gamepads].map(gamepadAxes).find(x=>x&&Object.values(x).some(value=>Math.abs(value)>.015));
 const axes=gamepad||keys;
 const rightStick=stickState.right,leftStick=stickState.left;
 if(!gamepad){
  if(Math.abs(rightStick.x)>.02)axes.roll=rightStick.x;
  if(Math.abs(rightStick.y)>.02)axes.pitch=-rightStick.y;
  if(Math.abs(leftStick.x)>.02)axes.yaw=leftStick.x;
 }
 const powered=Object.values(axes).some(value=>Math.abs(value)>.015);
 if(!powered && !pilotKeys.size && !lastPilotRollKey && !lastPilotPitchKey)return;
 const rollHeld=Boolean(gamepad?.roll||keys.roll||Math.abs(rightStick.x)>.02),pitchHeld=Boolean(gamepad?.pitch||keys.pitch||Math.abs(rightStick.y)>.02);
 const releaseRoll=lastPilotRollKey&&!rollHeld,releasePitch=lastPilotPitchKey&&!pitchHeld;
 lastPilotRollKey=rollHeld;lastPilotPitchKey=pitchHeld;
 const next=pilotStep(state,axes,dt,state.kind);
 const update={};
 // Joystick roll/pitch are absolute targets and do not conflict with keyboard.
 for(const key of ['roll','pitch','yaw','thrust']){
  if((key==='roll'&&!rollHeld&&!releaseRoll)||(key==='pitch'&&!pitchHeld&&!releasePitch))continue;
  if(Math.abs(next[key]-state[key])>.04)update[key]=next[key];
 }
 if(state.kind==='aircraft'&&next.brakes!==state.brakes){state.brakes=next.brakes;document.querySelector('#brakes').value=state.brakes;document.querySelector('#brakesOut').value=state.brakes+'%';queueManualCommand()}
 if(Object.keys(update).length)setManualValues(update);
}

function drawStick(name){const pad=$(".stick-pad[data-stick='"+name+"']"),knob=pad?.querySelector(".stick-knob"),v=stickState[name];if(!knob)return;const radius=Math.max(25,pad.clientWidth*.34);knob.style.transform=`translate(calc(-50% + ${v.x*radius}px), calc(-50% + ${v.y*radius}px))`;pad.style.setProperty("--stick-x",v.x);pad.style.setProperty("--stick-y",v.y)}
function commandStick(name){const v=stickState[name];if(name==="left")setManualValues({thrust:(1-v.y)*50});else setManualValues({roll:v.x*35,pitch:-v.y*(state.kind==="aircraft"?14:24)})}
function moveStick(name,x,y){const v=stickState[name];v.x=Math.max(-1,Math.min(1,x));v.y=Math.max(-1,Math.min(1,y));drawStick(name);commandStick(name)}
$$('.stick-pad').forEach(pad=>{const name=pad.dataset.stick;pad.addEventListener("pointerdown",event=>{event.preventDefault();pad.focus();pad.setPointerCapture(event.pointerId);const r=pad.getBoundingClientRect(),radius=Math.max(25,r.width*.34);moveStick(name,(event.clientX-r.left-r.width/2)/radius,(event.clientY-r.top-r.height/2)/radius)});pad.addEventListener("pointermove",event=>{if(!pad.hasPointerCapture(event.pointerId))return;const r=pad.getBoundingClientRect(),radius=Math.max(25,r.width*.34);moveStick(name,(event.clientX-r.left-r.width/2)/radius,(event.clientY-r.top-r.height/2)/radius)});const release=()=>{if(name==="left"){stickState.left.x=0;stickState.left.y=1-2*state.thrust/100;drawStick(name);setManualValues({})}else moveStick(name,0,0)};pad.addEventListener("pointerup",release);pad.addEventListener("pointercancel",release);pad.addEventListener("keydown",event=>{const step=event.shiftKey?.2:.08,v=stickState[name];if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(event.key))return;event.preventDefault();moveStick(name,v.x+(event.key==="ArrowRight"?step:event.key==="ArrowLeft"?-step:0),v.y+(event.key==="ArrowDown"?step:event.key==="ArrowUp"?-step:0))});pad.addEventListener("keyup",event=>{if(!event.key.startsWith("Arrow"))return;if(name==="left"){stickState.left.x=0;drawStick(name);setManualValues({})}else moveStick(name,0,0)})});
$$('.stick-pad').forEach(pad=>drawStick(pad.dataset.stick));
$("#addEvent").addEventListener("click",()=>{state.events++;const e=document.createElement("div");e.className="event";e.innerHTML="<i></i><b>USER "+pad(state.events)+"</b><small>T+"+pad(Math.floor(state.seconds/60))+":"+pad(Math.floor(state.seconds%60))+"</small>";$(".timeline-track").insertBefore(e,$("#addEvent"));toast("Evento aggiunto")});

$("#disciplineExplorer").addEventListener("click",openDisciplineExplorer);$("#closeDisciplines").addEventListener("click",()=>$("#disciplineDialog").close());$$('[data-discipline-filter]').forEach(button=>button.addEventListener("click",()=>{activeDisciplineFilter=button.dataset.disciplineFilter;$$('[data-discipline-filter]').forEach(item=>item.classList.toggle("active",item===button));renderDisciplineLibrary()}));$("#disciplineDialog").addEventListener("close",()=>$("#disciplineExplorer").classList.remove("rail-active"));[$("#systemExplorer"),$("#systemExplorerMobile")].forEach(button=>button.addEventListener("click",openCelestialExplorer));$("#celestialEpoch").addEventListener("change",e=>loadCelestialCatalog(e.target.value).catch(error=>toast("Effemeridi non aggiornate: "+error.message)));$("#celestialTarget").addEventListener("change",e=>{state.selectedBodyId=e.target.value;updateCelestialBody()});$("#planTransfer").addEventListener("click",requestTransfer);$("#transferSeek").addEventListener("input",event=>{state.transferProgress=Number(event.target.value)/1000;state.transferPlaying=false;updateTransferPlayback()});$("#transferPlay").addEventListener("click",()=>{if(!state.transferPlan)return;if(state.transferProgress>=1)state.transferProgress=0;state.transferPlaying=!state.transferPlaying;updateTransferPlayback()});$("#closeCelestial").addEventListener("click",()=>$("#celestialDialog").close());$("#celestialDialog").addEventListener("close",()=>{state.solarView=false;if(state.celestialCamera){state.az=state.celestialCamera.az;state.el=state.celestialCamera.el;state.zoom=state.celestialCamera.zoom;state.celestialCamera=null}document.body.classList.remove("celestial-open");$("#systemExplorer").classList.remove("rail-active");$("#heroTitle").textContent=info[state.kind][0];$("#heroSub").textContent=info[state.kind][1]});
function selectCodeLanguage(language){const sample=codeExamples[language]||codeExamples.python;$("#codeFilename").textContent=sample.file;$("#apiLanguageLabel").textContent=sample.label;$("#apiLanguageNote").textContent=sample.note;$("#codeSample").textContent=sample.code;$(".language-tab.active")?.classList.remove("active");$$(".language-tab").forEach(b=>{const active=b.dataset.language===language;b.classList.toggle("active",active);b.setAttribute("aria-selected",String(active))})}
$$(".language-tab").forEach(b=>b.addEventListener("click",()=>selectCodeLanguage(b.dataset.language)));selectCodeLanguage("python");
$("#copy").addEventListener("click",async()=>{try{await navigator.clipboard.writeText($("#codeSample").textContent);toast("Esempio "+$("#codeFilename").textContent+" copiato")}catch{toast("Seleziona e copia il codice mostrato")}});$("#connect").addEventListener("click",async()=>{try{const s=await api("/status");toast("ASTRA "+s.version+" · "+s.model)}catch{toast("Avvia il servizio locale ASTRA 1.0")}});
$("#help").addEventListener("click",()=>$("#info").showModal());$("#closeInfo").addEventListener("click",()=>$("#info").close());$("#okInfo").addEventListener("click",()=>$("#info").close());$("#info").addEventListener("click",e=>{if(e.target===$("#info"))$("#info").close()});
})();
