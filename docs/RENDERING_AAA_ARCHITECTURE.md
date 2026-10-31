# ASTRA — Architettura grafica cinematografica

Documento tecnico e piano di implementazione, 28 ottobre 2026.

L'obiettivo è una direzione visiva coerente: silhouette leggibili, materiali riconoscibili in luce neutra, contrasto spazio/interni, dettaglio stabile in movimento e ottiche credibili. La resa dipende anche da modellazione, scansioni, UV, texture e composizione; nessuno shader rende automaticamente cinematografici asset poveri.

Questo documento specifica un'architettura futura. La nebulosa in `nebula-rendering.js` è invece un aggiornamento locale effettivo del renderer WebGL2. GI, RTR, geometria virtualizzata e gli altri passaggi descritti qui non vengono dichiarati già implementati.

## 1. Audit del renderer attuale

| File | Presente | Intervento necessario |
|---|---|---|
| `rendering.js` | GGX, normal/metal/rough/AO/emissive, ombre PCF | IBL da immagini HDR reali, materiali stratificati, specular AA, illuminazione indiretta separata |
| `cinematic-renderer.js` | RGBA16F quando supportato, shadow map, bloom, AO da profondità, FXAA | Render graph, motion vector, history, riduzione luminanza GPU e gestione esposizione |
| `app.js` | matrici CPU double, più scene, raccolta disegni per ombre | coordinate locali in metri, interpolazione snapshot, lista visibile costruita una sola volta, instancing |
| `render-settings.js` | quattro budget reali | selezione per capability e misure GPU, con fallback espliciti |
| `nebula-rendering.js` | nuova emissione/estinzione sintetica in coordinate galattiche | eventuali volumi locali 3D separati e integrazione con esposizione fisica |

Problemi prioritari da risolvere prima dei nuovi effetti:

1. L'ambiente speculare attuale è un gradiente analitico: non riflette hangar, navi o pianeti.
2. La curva `(x*(2.51*x+.03))/(x*(2.43*x+.59)+.14)` è un fit filmico, non una pipeline ACES completa.
3. L'AO attuale moltiplica il colore finale dopo il tone mapping: scurisce anche luce diretta ed emissione. Va applicato all'indiretto, prima dell'output transform.
4. Il plume attuale esegue una compressione esponenziale con esposizione nello shader; il compositing applica nuovamente l'esposizione. Portarlo a emissione lineare senza tone mapping locale.
5. `antialias:true` del canvas non rende automaticamente multisample il framebuffer HDR. Scegliere MSAA con resolve esplicito oppure TAA con vettori di movimento.
6. La scena viene attraversata per raccogliere le ombre e poi per il colore; creare una render list persistente e liste visibili per vista/luce.
7. Memorizzare location uniform e pipeline state alla creazione; evitare query WebGL e allocazioni JSON nel percorso per frame.
8. Se il framebuffer floating point non è completo, ricreare un percorso LDR coerente; non usare un semplice RGBA8 lineare che taglia gli highlight prima dell'output transform.

## 2. Tre percorsi, con confini verificabili

| Funzione | WebGL2 esistente | WebGPU standard | Windows nativo DX12/Vulkan o UE 5.6 |
|---|---|---|---|
| GI diffusa | irradiance probe SH/lightmap + correzione screen-space | probe aggiornate con compute e tracing software BVH/SDF | DDGI ray traced, Lumen o altra GI ibrida |
| Riflessi | cubemap locali corrette per parallasse + SSR | SSR gerarchico + BVH software selettivo | RTR hardware con BLAS/TLAS e denoising |
| Geometria | LOD precalcolati, instancing, displacement su mesh già suddivise | selezione cluster con compute e draw indirect | Nanite o geometria virtualizzata dedicata |
| Culling | frustum CPU; occlusion query asincrone; estensioni opzionali | compute, HZB, compattazione e indirect draw | GPU-driven, ExecuteIndirect/indirect draw, mesh shader se disponibili |
| Atmosfera | LUT e pass raster | LUT + froxel compute | LUT/froxel compute, RT selettivo per ombre locali |
| Shader | GLSL ES 3.00 | WGSL o TSL compilato in WGSL | HLSL/GLSL nativi secondo backend |

WebGPU non va trattato come un interruttore per DXR: nel percorso web standard qui previsto non si assume un'API portabile per acceleration structure e ray query hardware. Verificare `adapter.features` e i limiti reali; una RTX nel PC non rende automaticamente disponibili quelle API nel browser. Il tracing software resta possibile ma richiede un budget proprio.

Se GI e RTR hardware sono requisiti inderogabili, il percorso Windows nativo è la scelta diretta. Per mantenere ASTRA nel browser, il primo traguardo è un renderer ibrido di qualità, con fallback dichiarati.

Riferimenti: [WebGPU Explainer](https://gpuweb.github.io/gpuweb/explainer/), [feature WebGPU](https://developer.mozilla.org/en-US/docs/Web/API/GPUSupportedFeatures), [DXR](https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html), [Vulkan RT](https://docs.vulkan.org/spec/latest/chapters/raytracing.html).

## 3. Coordinate, tempo e contratti dei dati

Python mantiene fisica SI, epoca, seed e posizione ECI in double. Il renderer riceve snapshot immutabili, non comandi grafici Python. Il worker/server non deve eseguire calcoli per pixel o trasferire texture a ogni passo.

```ts
type RenderSnapshot = {
  simulationTimeS: number;
  revision: number;                   // reset, cambio veicolo o scenario
  entities: Array<{
    id: number;
    positionECIM: [number,number,number]; // Number JS / double lato fisica
    velocityECIMps: [number,number,number];
    quaternion: [number,number,number,number];
    visualAssetId: string;
    appearance: {
      heatDoseJm2: number;
      uvDoseJm2: number;
      atomicOxygenFluenceM2: number;
      depositedDustKgm2: number;
    };
  }>;
};
```

Separare campi già misurati dal motore da campi futuri: UV, ossigeno atomico e deposito non sono tutti disponibili nella telemetria attuale. Se mancanti, usare zero o uno scenario artistico dichiarato; non dedurli arbitrariamente dal solo tempo.

CPU: `relativeM = positionECIM - originECIM`, poi conversione float32 per GPU. Gli asset vicini usano metri reali; atmosfera/planeta possono avere un dominio in km, con conversioni esplicite. Eliminare costanti di scena che mescolano metri, scala compressa della Terra e dimensioni arbitrarie degli asset.

Conservare trasformazioni e origine del frame precedente. Un rebase gestito correttamente non crea velocità apparente: il clip precedente usa posizione e origine precedenti. Resettare la storia per camera cut, reset missione, cambio asset, risoluzione incompatibile o rebase non compensato. Non azzerare TAA ogni volta che una nave attraversa una cella spaziale.

Interpolare posizione con Hermite quando sono disponibili velocità e timestamp, quaternion con slerp. Il render clock può essere a 60/120 Hz anche con snapshot più lenti. Le raffiche, la navigazione e il consumo restano nel motore fisico.

## 4. Render graph e risorse

```text
Snapshot interpolato → origine locale → istanze/LOD → culling
  ├─ depth + geometric normal + material ID + velocity
  ├─ shadow maps / aggiornamento BLAS-TLAS [solo backend RT]
  ├─ HZB + classificazione tile
  ├─ direct lighting → directDiffuse + directSpecular
  ├─ diffuse GI → history GI → temporal + spatial denoise
  ├─ SSR / RTR → history reflection → temporal + spatial denoise
  └─ compositing opachi lineare
      → atmosfera/aerial perspective: L = T·Lsurface + LinScatter
      → canopy e trasparenti: campionano lo sfondo opaco, mai il target in scrittura
      → particelle locali illuminate e attenuate dal volume
      → TAA/upscale con depth, velocity, reactive mask
      → motion blur e DoF con separazione delle discontinuità
      → ottiche HDR: bloom, ghosts, streak anamorfici
      → esposizione finale + ACES output transform
      → UI nitida nello spazio display
```

Le superfici trasparenti usano la stessa soluzione volumetrica per evitare una seconda foschia intera davanti allo stesso oggetto. Trasparenze e vetro richiedono motion/reactive mask proprie; le stelle lontane richiedono la velocità da rotazione della camera, non da traslazione locale.

Ordine motion blur/DoF è una scelta ottica approssimata: documentarlo e validare le occlusioni. Un insieme di pass post non sostituisce l'integrale spazio-temporale di una vera camera.

Risorse indicative a risoluzione interna 2560×1440, single sample:

| Risorsa | Formato iniziale | Note |
|---|---|---|
| radiance opaca | RGBA16F | circa 28 MiB per buffer, prima di mip/history |
| normal + roughness | RGBA16F o packing validato | oct-normal, roughness, flag |
| base color + metallic | RGBA8 | valori di lavoro lineari dopo decode sorgente |
| velocity | RG16F | UV/frame, clip non jitterato |
| depth | D32F/D24 secondo backend | convenzione esplicita |
| HZB | R32F mip chain | circa 4/3 dei pixel base |
| GI/reflection history | RGBA16F, metà dimensione per asse | depth/normal/momenti separati |

Due buffer RGBA16F a 4K richiedono circa 126.6 MiB: il costo va contato prima di moltiplicare storia, G-buffer e MSAA. Aliasing solo fra risorse con lifetime disgiunti; la storia temporale non è scratch memory.

## 5. GI e riflessi

### GI diffusa

Nel web iniziare con probe SH di ordine 2, nove coefficienti RGB, collocate in volumi locali di hangar/stazioni. Irradianza:

`E(n) ≈ Σ(i=0..8) c_i Y_i(n)`; `Ldiffuse = albedo · E / π`.

La convoluzione coseno va incorporata nei coefficienti o nel lookup una sola volta. Interpolazione trilineare con pesi di visibilità/depth moments; classificare o ricollocare probe dentro i muri. Porte, grandi navi e pareti sottili sono test di leakage obbligatori.

Nel nativo usare DDGI: ray budget distribuito sulle probe vicine, aggiornamenti prioritari dove cambiano luci e geometria, irradiance + momenti di distanza, hysteresis dipendente dalla variazione. DDGI è principalmente illuminazione diffusa: i riflessi lucidi richiedono un percorso distinto. [Integrazione DDGI](https://developer.nvidia.com/blog/an-engineers-guide-to-integrating-ddgi/).

Non utilizzare SSAO come sostituto della GI e non moltiplicare l'intero beauty per AO:

```glsl
vec3 indirect = diffuseGI * diffuseAO + reflectedRadiance * specularOcclusion;
vec3 outgoing = directDiffuse + directSpecular + indirect + emission;
```

### Riflessi ibridi

WebGL2: SSR per hit visibili, cubemap locali con parallax correction per miss, cielo/pianeta per esterni. Cubemap HDR prefiltrate GGX, mip per roughness e BRDF integration LUT. Le cubemap non sono RTR.

SSR: HZB in profondità lineare o una convenzione monotona documentata, stepping gerarchico, raffinamento all'incrocio, thickness dipendente da profondità/pendenza, confidence da bordi e angolo. Combinare fallback con una maschera di confidence, senza sommare due riflessi completi. Geometria fuori schermo e superfici sottili restano limiti strutturali. [AMD SSSR](https://gpuopen.com/manuals/fidelityfx_sdk/samples/stochastic-screen-space-reflections/).

Nativo: un BLAS per mesh unica, TLAS per istanze; refit per trasformazioni/deformazioni compatibili, rebuild se il refit degrada troppo. Materiali alpha-test e mesh deformate richiedono regole dedicate. Scafo e pianeta visibili nei riflessi devono usare geometria coerente con il displacement o un proxy con errore limitato. [Architettura ray query Vulkan](https://docs.vulkan.org/tutorial/latest/Building_a_Simple_Engine/Advanced_Topics/Ray_Query_Rendering.html).

Frammento HLSL DXR 1.1: recupera una hit opaca, non costituisce il pass RTR completo.

```hlsl
RaytracingAccelerationStructure sceneAS : register(t0);

bool closestOpaque(float3 origin, float3 direction, float tMax, out float hitT) {
    RayDesc ray;
    ray.Origin = origin;
    ray.Direction = normalize(direction);
    ray.TMin = 0.001;                  // esempio in metri; bias adattivo richiesto
    ray.TMax = tMax;
    RayQuery<RAY_FLAG_CULL_NON_OPAQUE |
             RAY_FLAG_SKIP_PROCEDURAL_PRIMITIVES> query;
    query.TraceRayInline(sceneAS, RAY_FLAG_NONE, 0xff, ray);
    while (query.Proceed()) {}
    bool hit = query.CommittedStatus() == COMMITTED_TRIANGLE_HIT;
    hitT = hit ? query.CommittedRayT() : tMax;
    return hit;
}
```

Non usare `ACCEPT_FIRST_HIT_AND_END_SEARCH` per il riflesso closest-hit. È appropriato per una semplice occlusione, non per scegliere la superficie visibile più vicina. In produzione aggiungere barycentric, instance/material ID, texture LOD da ray cone, lighting alla hit e miss shader. Il codice esclude trasparenti: canopy e foliage non vengono risolti da questa funzione.

Budget iniziale proposto: riflessi a metà dimensione per asse, 1 sample/pixel selezionato, un rimbalzo; VNDF GGX per superfici ruvide, PDF e throughput corretti. Sopra una soglia di roughness graduale usare radiance cache/probe; evitare uno stacco netto. Non assumere che la gerarchia Nanite sia direttamente la BVH RT.

### Storia temporale

`velocityUV = currentUV_unjittered - previousUV_unjittered`; `historyUV = uv - velocityUV`.

Rigettare storia fuori schermo, dietro un'occlusione, con profondità incompatibile, normale discordante o material/revision ID cambiato. Correggere pre-exposure fra i frame e clampare la storia nel dominio di colore scelto usando neighborhood e varianza. Il peso della storia scende sui cambi luce; non usare un blend costante che lascia scie sulle stelle e sul canopy.

## 6. Atmosfera stratificata e illuminazione stellare

Modello per pianeta, con quote e coefficienti propri:

`ρR(h)=exp(-h/HR)`; `ρM(h)=exp(-h/HM)`; profilo separato per assorbitori, ad esempio ozono.

`βext(h,λ)=βR(λ)ρR(h)+βM,ext(λ)ρM(h)+βabs(λ)ρabs(h)`.

`T(a,b,λ)=exp[-∫a^b βext(s,λ) ds]`.

`pR(μ)=3(1+μ²)/(16π)`.

`pHG(μ,g)=(1-g²)/(4π(1+g²-2gμ)^(3/2))`.

La fase HG è un'approssimazione per l'aerosol, non la soluzione Mie completa per una distribuzione di particelle. Distinguere coefficiente di scattering da estinzione, quindi albedo di scattering singolo; non tutto ciò che assorbe luce deve anche diffonderla.

Con `ray` da camera alla scena e `toSun` dal campione verso la stella, usare una convenzione di fase coerente e provarla sul forward scattering. La radianza di singolo scattering è:

`Lin = ∫ Tcamera(s) · Tstar(s) · [βRρR pR + βM,scaρM pM] · Estar ds`.

Compattare l'implementazione in LUT di transmittance e multiple scattering, sky-view per la camera e aerial perspective volume. In WebGL2 usare pass raster/FBO per il precompute; Python può preparare coefficienti o bake offline, non integrare pixel nel loop del volo. L'orbita richiede il ramo geometrico valido per osservatore fuori atmosfera, non una sky dome soltanto terrestre. [Bruneton, implementazione e test](https://ebruneton.github.io/precomputed_atmospheric_scattering/index.html).

Passare al compositing **radianza e transmittance RGB**, non solo una tinta con alpha:

```glsl
struct MediumSegment { vec3 inScattered; vec3 transmittance; };
vec3 compositeMedium(vec3 behind, MediumSegment medium) {
    return medium.inScattered + medium.transmittance * behind;
}

// Integrazione esatta di una cella a coefficienti costanti.
// sigmaExt: 1/m; source: radianza/(m); ds: m.
void integrateCell(inout vec3 L, inout vec3 T,
                   vec3 sigmaExt, vec3 source, float ds) {
    vec3 stepT = exp(-sigmaExt * ds);
    vec3 weight = (vec3(1.0)-stepT) / max(sigmaExt, vec3(1e-6));
    weight = mix(vec3(ds), weight, step(vec3(1e-6), sigmaExt));
    L += T * source * weight;
    T *= stepT;
}
```

L'integratore va arrestato alla superficie opaca più vicina o al bordo del volume; il pianeta oscura la stella. Per le nuvole: densità 3D, ombre a risoluzione ridotta, reprojection e reactive mask; non confondere la texture di copertura con un campo meteo validato.

Per una stella: spettro efficace, raggio e distanza determinano la luce, non un semplice RGB blu per la classe O/B. Con disco piccolo e spettro blackbody di riferimento:

`Bλ(T)=2hc²/[λ⁵(exp(hc/(λkT))-1)]`;
`Eλ ≈ π Bλ(T) (Rstar/d)²`.

Integrare lo spettro nelle funzioni colorimetriche, applicare adattamento cromatico/white balance controllato e documentare il gamut di lavoro. Un corpo nero resta un'approssimazione dello spettro stellare. Per stelle grandi in angolo usare campioni del disco e ombre morbide; l'approssimazione di luce direzionale puntuale non basta. UV e radianza visibile rimangono canali fisici distinti.

## 7. Materiali e scala del dettaglio

### Contratto di authoring

Mesh in metri, tangenti coerenti con il bake, bevel reali sulle silhouette, UV senza distorsioni e seam gestite. Densità texel determinata dall'inquadratura massima; evitare 8K ovunque. Normal, roughness, metal, height, AO e mask sono dati lineari. Base color ed emissive con encoding dichiarato vengono decodificati una sola volta.

Per ogni asset: mesh alta, mesh runtime/cluster, proxy collisione distinto, texture KTX2/Basis o formati nativi appropriati, mip chain, materiale e scale fisiche del detail. Il displacement usa altezza firmata e ampiezza in metri, non uno slider generico 0–1 senza unità.

| Scala | Tecnica | Esempio |
|---|---|---|
| silhouette e grandi giunzioni | geometria | portelli, bordi, crateri |
| centimetri | displacement/LOD suddivisi | ceramica TPS, roccia, saldature |
| millimetri | detail normal e roughness | porosità, vernice, lavorazione |
| subpixel | distribuzione statistica filtrata | flake e micro-graffi |

Lo scafo metallico è prima di tutto un problema di silhouette, giunzioni, roughness e riflessi; non richiede displacement estremo su ogni pannello.

### Displacement e geometria virtualizzata

`P' = P + Ngeom · heightM`.

Aggiornare normale e bounds. Anche shadow/depth/velocity e geometria RT devono rispettare lo stesso spostamento o un proxy con errore dichiarato. Per cluster con errore geometrico `eM`, distanza conservativa `zNearM` e focale in pixel `fyPx`:

`screenErrorPx ≈ eM · fyPx / max(zNearM, ε)`.

Selezionare LOD con isteresi, cucitura dei bordi e budget di streaming. Un campionamento height nel vertex shader WebGL2 sposta solo vertici esistenti: non genera micropoligoni.

UE 5.6: Nanite è il percorso pertinente, ma la tessellation dinamica è documentata come sperimentale. Richiede normal coerenti e attenzione a seam, bounds e Virtual Shadow Maps. [Documentazione 5.6](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine?application_version=5.6).

Configurazione di prova, da verificare sul branch UE scelto:

```ini
[SystemSettings]
r.Nanite.AllowTessellation=1
r.Nanite.Tessellation=1
```

Attivare la tessellation nel materiale, impostare Magnitude nelle unità dell'asset e fade per dimensione proiettata. Non assumere che la feature sia pronta per qualsiasi contenuto o compatibile con tutti i backend.

### BRDF e stratificazione

`fr = kd · baseColor/π + DGGX · GSmith · F / (4 NoV NoL)`.

Per un dielettrico in aria: `F0=((η-1)/(η+1))²`; per conduttori servono indici complessi `η(λ),k(λ)` oppure un F0 RGB derivato da dati appropriati. Una tintura metallica generica non sostituisce quella calibrazione.

Esempio GLSL di attenuazione di una base sotto coat sottile. Assume BRDF base e coat già valutate, indici coerenti e nessun assorbimento nel coat:

```glsl
float fresnelSchlick(float cosTheta, float f0) {
    float m = 1.0-clamp(cosTheta,0.0,1.0);
    return f0+(1.0-f0)*m*m*m*m*m;
}
vec3 layeredCoat(vec3 baseBRDF, vec3 coatBRDF,
                 float NoV, float NoL, float coatWeight, float coatIOR) {
    float f0 = pow((coatIOR-1.0)/(coatIOR+1.0),2.0);
    float fv = coatWeight*fresnelSchlick(NoV,f0);
    float fl = coatWeight*fresnelSchlick(NoL,f0);
    return baseBRDF*(1.0-fv)*(1.0-fl)+coatWeight*coatBRDF;
}
```

È una stratificazione approssimata: una soluzione completa considera rifrazione fra gli strati, cambiamento dell'IOR relativo, compensazione energetica e scattering multiplo. Usare normali diverse per coat e substrato. Attivare il secondo lobo solo dove necessario. [Materiali Filament](https://google.github.io/filament/main/materials.html).

Flake: distribuzione in object/UV space con seed stabile, densità e orientamento; lobo medio quando i grani diventano subpixel. Non rigenerare random per frame. Micro-graffi modificano roughness e anisotropia, non creano punti bianchi emissivi. Specular AA da varianza delle normali e roughness filtrata per evitare scintillio.

Alternativa Three.js per accelerare authoring, non per ottenere automaticamente GI o RTR:

```js
const paint = new THREE.MeshPhysicalMaterial({
  color: 0x23394d, metalness: 0.0, roughness: 0.28,
  clearcoat: 1.0, clearcoatRoughness: 0.10,
  normalMap: paintNormal, clearcoatNormalMap: coatNormal
});
paint.envMap = prefilteredHangarEnvironment;
// Substrato esposto separato o mascherato: metalness=1 dove è davvero metallo.
```

La versione Three.js va bloccata. Con WebGPURenderer gli shader custom seguono il percorso TSL/WGSL supportato: non si assume che l'attuale stringa GLSL ES sia riutilizzabile senza porting. [MeshPhysicalMaterial](https://threejs.org/docs/pages/MeshPhysicalMaterial.html), [WebGPURenderer](https://threejs.org/docs/pages/WebGPURenderer.html).

## 8. Weathering persistente, guidato dagli eventi

Tenere quattro fenomeni distinti:

| Fenomeno | Ingresso | Risultato visivo |
|---|---|---|
| polvere/regolite/plume | deposito direzionale locale | coat di particelle, cavità e roughness |
| impatti | eventi con direzione/energia/seed | decal di cratere, scheggiatura e normale |
| rientro | flusso, dose e temperatura compatibili col materiale | discoloration, char o materiale ablativo se previsto |
| ambiente spaziale | UV, cicli termici, specie reattive | degrado coating distinto da ossidazione |

Non far comparire ruggine solo perché trascorre tempo al Sole nel vuoto. L'ossigeno atomico LEO è un ambiente specifico; il degrado UV è un altro meccanismo. [NASA-HDBK-6024](https://standards.nasa.gov/standard/nasa/nasa-hdbk-6024).

Evoluzione di deposito areale: `dmDust/dt = Jdeposit - kRemoval·mDust`, con J in kg/(m² s), k in 1/s. Dose termica: `Q = ∫qdot dt` in J/m²; mask visiva `1-exp[-max(Q-Q0,0)/Qscale]`, con Q0/Qscale specifici del materiale e dichiarati come parametri visuali se non calibrati.

```glsl
// Aggiornamento di una texel persistente a coefficiente costante.
float advanceDust(float massArea, float depositFlux, float removalRate, float dt) {
    if (removalRate < 1e-6) return max(0.0,massArea+depositFlux*dt);
    float decay=exp(-removalRate*dt);
    return max(0.0,massArea*decay+depositFlux*(1.0-decay)/removalRate);
}
```

Aggiornare atlas UV ping-pong a 2–10 Hz o sugli eventi; raster pass in WebGL2, compute altrove. Leggere dal target precedente e scrivere nel nuovo, mai feedback sullo stesso attachment. Seam dilation, unità fisiche e mip persistenti; serializzare seed ed eventi o checkpoint compatti. La vista artistica non altera Cd, massa o aerotermodinamica senza un contratto fisico esplicito.

## 9. Particelle e velocità vettoriale

La polvere del sistema solare non giustifica una nebbia fitta uniforme. Definire volumi locali: hangar, plume, ejecta vicino alla superficie, campo di detriti. Nel vuoto pulito usare stelle, occultazioni e moto relativo di oggetti credibili. Una modalità cinematografica può amplificare i traccianti, ma resta separata dalla densità fisica.

Aggiornamento GPU: transform feedback WebGL2; compute + compattazione e indirect draw in WebGPU/nativo. Generare le quad con instancing/vertex ID. Non creare una mesh o una chiamata draw per ogni particella.

Con coordinate UV normalizzate, altezze clip positive e posizione precedente non jitterata:

```glsl
vec2 curUV = 0.5*(currentClip.xy/currentClip.w)+0.5;
vec2 oldUV = 0.5*(previousClip.xy/previousClip.w)+0.5;
vec2 velocityUV = curUV-oldUV;
vec2 blurVector = velocityUV*(shutterSeconds/max(frameSeconds,1e-5));
```

Rigettare i casi dietro near plane/camera cut. Se la shutter supera un frame, il semplice segmento lineare è una stima: scegliere substep o una traiettoria estesa. La direzione deriva da moto di particella, nave e camera, non dall'asse Z dello schermo.

Illuminazione: fase HG o flake BRDF secondo il materiale, shadow visibility e scattering singolo; particella senza luce resta scura. Trasparenze premoltiplicate e soft intersection dalla profondità. Il motion blur usa campioni guidati da depth e velocity per evitare bleeding del canopy sullo sfondo. Limitare overdraw e area in pixel, non solo numero di particelle.

## 10. Esposizione, ACES e ottiche

Lavorare in radiance lineare con primarie dichiarate, ad esempio linear Rec.709 D65 nella prima migrazione. Poi usare una trasformazione OCIO/ACES verificata verso il display scelto. ACES 2 comprende un output transform con gestione cromatica; non è la sola curva a cinque coefficienti attuale. [Output transforms ACES](https://docs.acescentral.com/system-components/output-transforms/), [configurazioni OCIO ACES](https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES).

### Pre-exposure ed eye adaptation

Memorizzare `Cstored = radiance · P`, dove P è pre-exposure; correggere la storia con `Pcurrent/Pprevious`. L'ultima trasformazione usa `Cstored · exposure/P` una sola volta. Coordinate e radianza rimangono concetti separati.

Metering GPU: istogramma log-luminance, percentili e maschera del cockpit; scartare hot pixel isolati, senza ignorare arbitrariamente una stella che riempie lo schermo. WebGL2 può usare riduzioni FBO della log luminanza come fallback; non spacciare una media per un istogramma percentile. Evitare `readPixels` sincrono per l'esposizione.

```glsl
// EV relativo del gain: log2(exposure), non EV100 fotografico.
float adaptExposureEV(float previousEV, float meterLuminance,
                      float middleGrey, float dt) {
    float targetEV=log2(middleGrey/max(meterLuminance,1e-6));
    float tau=targetEV<previousEV ? 0.12 : 1.5;
    float a=1.0-exp(-dt/tau);
    return mix(previousEV,targetEV,a);
}
```

I tempi sono un punto di partenza cinematografico, non una simulazione della fisiologia umana. L'adattamento al buio completo non è istantaneo. Clamp EV configurabile e fusione morbida del metering per evitare pumping; manual exposure lock per review.

### ACES GPU

Bloccare versione di OCIO/config/output transform e target SDR/HDR. Se si usa una LUT GPU, includere shaper e trasformazioni colore esatte, dominio, primarie e encoding di uscita. Validare con il processor CPU su ramp e campioni HDR; niente gamma aggiuntiva dopo una LUT che restituisce già valori display.

Esempio di sampling con signed-log shaper; il bake deve usare l'inversa identica. Questa funzione non contiene da sola l'ACES transform:

```glsl
vec3 sampleBakedOutput(vec3 exposedLinear, sampler3D outputLUT,
                       float linearScale, float logRange, float lutSize) {
    vec3 shaped=0.5+0.5*sign(exposedLinear)*
        log2(1.0+abs(exposedLinear)/linearScale)/logRange;
    vec3 uv=(clamp(shaped,0.0,1.0)*(lutSize-1.0)+0.5)/lutSize;
    return texture(outputLUT,uv).rgb;
}
```

Conservare valori negativi validi finché il color pipeline li gestisce; non tagliare RGB in anticipo solo per entrare in un log positivo. Determinare errore e risoluzione della LUT, tipicamente 33³/65³ come candidati da misurare, non garanzia di accuratezza.

### DoF e flare anamorfici

Thin lens: diametro del circle of confusion sul sensore `c = (f²/N) · |z-zf|/[z(zf-f)]`, con tutte le lunghezze coerenti; convertire in pixel con `imageWidthPx/sensorWidth`. Conservare il segno near/far per compositing e disocclusioni.

Un kernel ellittico è una prima approssimazione del bokeh anamorfico, non un modello completo di lente. Separare foreground/background, dilation del foreground CoC, aperture mask, risoluzione metà e campioni guidati dalla copertura. Non sfocare HUD e reticoli operativi per un effetto estetico involontario.

Lens flare: sorgenti HDR, occlusione del disco, prescrizione ottica e coating. Precalcolare offline ghosts/PSF per combinazioni focal length/aperture; runtime seleziona e interpola. Uno streak orizzontale può approssimare un'ottica anamorfica, ma non va chiamato ray tracing della lente. [Hullin et al., lens flare fisico](https://resources.mpi-inf.mpg.de/lensflareRendering/).

## 11. Canopy e cockpit glass

Due interfacce o thickness affidabile; normali geometriche e del rivestimento, IOR e assorbimento. `Tglass(λ)=exp(-σabs(λ)·thicknessM/|cosθt|)` per lastra localmente parallela, poi Fresnel su ingresso/uscita. Nelle geometrie curve tracing della seconda intersezione; refrazione screen-space non recupera ciò che manca fuori schermo.

Primo percorso: opaque scene copy + SSR/cubemap + refraction UV con depth validation. Percorso RT: riflessione esterna e interna selettive, due superfici, priorità per canopy vicino alla camera, limiti di bounce e fallback.

```glsl
vec3 transmittedDirection = refract(-V, N, 1.0/glassIOR);
bool totalInternalReflection = dot(transmittedDirection,transmittedDirection)<1e-8;
float f0=pow((glassIOR-1.0)/(glassIOR+1.0),2.0);
float F=fresnelSchlick(max(dot(N,V),0.0),f0);
vec3 absorption=exp(-absorptionPerM*pathLengthM);
vec3 result = F*reflectionRadiance +
    (1.0-F)*absorption*refractionRadiance;
```

Il frammento assume una interfaccia in ingresso; uscita e riflessione totale vanno gestite con IOR relativo e normale orientata correttamente. Non usare un offset UV costante come rifrazione fisica.

Sporco volumetrico: inclusioni in un sottile volume o film con spessore; micro-graffi come normali e distribuzione di scattering. La visibilità in controluce emerge da fase della particella, luce incidente, Fresnel ed esposizione. Non accendere lo sporco con un semplice `pow(dot(view,sun),n)` senza visibilità e percorso ottico.

Separare canopy e ottica della camera: lo sporco sul vetro della nave non genera automaticamente gli stessi ghosts delle lenti fotografiche.

## 12. Warp / quantum travel

Effetto dichiaratamente artistico. Il motore fisico continua a distinguere traiettoria simulata, camera e transizione. Non chiamare scientificamente relativistico uno stretching dello schermo.

Componenti: warp mask locale + flusso volumetrico instanziato + distorsione del background + profilo audio/camera + esposizione controllata. Il cockpit va compositato con una maschera separata, non trascinato insieme alle stelle. Una fonte di distortion energy non deve alterare accidentalmente la UI.

```glsl
vec3 sampleWarp(sampler2D sceneColor, vec2 uv, vec2 center,
                vec2 inverseImageSize, float strength, float aberrationPx) {
    vec2 p=uv-center;
    float aspect=inverseImageSize.y/inverseImageSize.x;
    vec2 q=p*vec2(aspect,1.0);
    float r2=dot(q,q);
    vec2 warped=center+p*(1.0+strength*r2);
    vec2 delta=q/max(length(q),1e-5)*aberrationPx*
               inverseImageSize*strength*r2;
    return vec3(texture(sceneColor,clamp(warped+delta,0.0,1.0)).r,
                texture(sceneColor,clamp(warped,0.0,1.0)).g,
                texture(sceneColor,clamp(warped-delta,0.0,1.0)).b);
}
```

Serve overscan o fade sul bordo per evitare texture stirate dal clamp. La modalità operativa riduce blur, aberrazione e movimento camera; screenshot mode può alzare il budget. `strength=0` deve essere identità.

## 13. Nebulosa: upgrade locale e percorso volumetrico

L'aggiornamento reale è separato dal piano futuro:

- decode sRGB corretto della mappa stellare, output scene-linear;
- volume noise 64³ RGBA8 con mip, circa 1 MiB base / 1.14 MiB con mip;
- integrazione front-to-back di emissione e assorbimento con polvere più estinguente nel blu;
- coordinate galattiche continue, senza cuciture procedurali a longitude ±π;
- nessuna animazione rapida o parallasse locale inventata per nubi lontane;
- 0/4/7/10 campioni per LOW/BALANCED/HIGH/ULTRA, salto del volume nell'atmosfera diurna;
- controllo di intensità in GRAFICA e seed deterministico del rumore.

È uno sfondo sintetico cinematografico in unità relative, non una ricostruzione spettrofotometrica o un volume attraversabile. La mappa base può già includere stelle e nubi: il compositing è artistico, non una separazione fisica dei componenti fotografati.

Emissione da gas, riflessione su polvere e assorbimento producono fenomeni diversi; le palette a banda stretta delle immagini astronomiche non vanno presentate automaticamente come visione a occhio nudo. [NASA, tipi di nebulose](https://science.nasa.gov/universe/stories/quick-reads/decoding-nebulae/).

Per una futura nebulosa locale attraversabile: bounds 3D in coordinate galattiche double, trasformazione in volume locale float, brick streaming sparso con occupancy/min-max, empty-space skipping, emissivity/extinction separati, campioni adattivi e storia temporale con disocclusioni. La polvere attorno alla nave rimane un altro sistema e un'altra scala spaziale.

## 14. Prestazioni: culling, batching, streaming e misure

1. Costruire un `RenderWorld` persistente con mesh/material ID e trasformazioni. Scene traversal e visibilità una volta, poi liste per opaque, transparent, shadow e ray tracing.
2. Raggruppare per pipeline, materiale e mesh; usare instance buffer e texture array/atlas. Interni, pareti e portelli restano separabili per culling e GI: un unico megamesh è controproducente.
3. WebGL2: frustum CPU, instancing, UBO; query di occlusione consumate nei frame successivi, mai bloccanti. `WEBGL_multi_draw` è opzionale e non sostituisce il percorso GPU-driven compute.
4. WebGPU/nativo: cluster bounds, frustum + normal-cone per opachi adatti, HZB conservativo, prefix sum/compattazione e draw indirect. Includere displacement nei bounds e mantenere un overflow fallback sicuro.
5. HZB con depth standard `near=0, far=1`: massimo nel tile per rigettare un oggetto solo quando il suo punto più vicino è dietro tutti i campioni conservativi. Con reversed-Z convenzione e confronto si invertono. Gestire sky, mip footprint e camera motion; oggetti appena visibili non vanno eliminati da una HZB vecchia.
6. Decouplare raster visibility e RT visibility: un oggetto fuori schermo può essere visibile nello specchio o generare GI. Culling dei raggi basato sul loro dominio, non sul solo frustum principale.
7. GPU skinning/transform, dirty ranges e aggiornamento BVH selettivo. Evitare rebuild BLAS globale a ogni frame.
8. Compilare e warm-up delle varianti prima della missione; limitare il prodotto combinatorio di clearcoat, transmission, detail e weathering.
9. Streaming prioritario per dimensione proiettata e persistenza: mip coarse garantita, budget VRAM con hysteresis, cache locale/offline e manifest versionato. SSR e probe non devono attendere una texture 8K per mostrare una superficie valida.
10. GPU timestamp asincroni, ring di query, scartare periodi disjoint in WebGL; p50/p95/p99 per pass e frame. La media del RAF misura anche CPU/browser, non il solo costo GPU.

### Budget proposto, non benchmark

Target di pianificazione: 60 Hz, risoluzione interna 1440p scalabile, output 4K opzionale. Hardware ancora da scegliere e misurare. Tempi GPU non vanno presentati come prestazioni ottenute:

| Area | Budget iniziale ms |
|---|---:|
| visibilità, depth e motion | 1.3 |
| ombre e aggiornamenti RT ammortizzati | 1.8 |
| shading opaco e direct lighting | 2.5 |
| GI | 2.0 |
| riflessi e denoising | 2.0 |
| atmosfera, canopy e particelle | 1.8 |
| TAA, ottiche e output | 2.0 |
| margine | 3.27 |
| totale | 16.67 |

Sono tetti di progetto su una GPU target da definire, non previsioni per qualsiasi dispositivo. CPU e GPU devono procedere in pipeline; non si sommano ingenuamente i tempi CPU al totale GPU. VR e stereo richiedono budget e algoritmi propri.

LOD della qualità per costo: prima numero di aggiornamenti probe e raggi riflessi, poi risoluzione dei volumi, shadow coverage e risoluzione interna. Conservare tono, unità, silhouette e stabilità. LOW evita il marching della nebulosa; nessun effetto deve spostare il controllo della missione sul thread GPU.

## 15. Sequenza di produzione e criteri di accettazione

| Fase | Consegna | Gate |
|---|---|---|
| A | unità, snapshot, render list, colore lineare | niente jitter ECI; luce/emissione con una sola esposizione |
| B | asset campione + HDR IBL + materiali stratificati | confronto in light rig neutro e HDR reference |
| C | depth/normal/velocity/history + probe/SSR | camera pan, disocclusioni, specchio fuori schermo, niente trails persistenti |
| D | atmosfera LUT e ottiche | ground→orbit continuo, occultazione del Sole, Beer-Lambert, calibrazione display |
| E | canopy, weathering, particelle e warp | identità a forza zero; persistenza seed; cockpit leggibile |
| F | percorso RT/geometry streaming se scelto | closest hit corretto, proxy coerenti, VRAM e p95 entro budget |

Review obbligatoria in movimento, con esposizione fissa e automatica, e immagini di riferimento offline/path-traced su scene piccole. Debug view: direct/indirect/emission, normal/roughness, reflection hit confidence, probe weights, optical depth, displacement error, velocity, history age, exposure e overdraw.

I gate visivi comprendono interno hangar scuro con porta solare, scafo verniciato e ceramica TPS, orbita con terminatore, attraversamento di foschia locale, canopy controluce, asteroide contro stelle e reset durante quantum travel. Nessuna scena singola dimostra qualità generale o FPS su hardware non provato.

### Profilo UE 5.6 alternativo

Lumen GI/reflections con hardware RT se supportato, Nanite per geometria ammessa, Virtual Shadow Maps, Sky Atmosphere, nuvole volumetriche e Niagara. Verificare configurazione e dipendenze sul branch 5.6, senza copiare cvar da versioni successive. Il modello Lumen è ibrido e ha limiti di superficie/cache: non equivale a path tracing completo. [Lumen technical details 5.6](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine?application_version=5.6).

Per ASTRA la scelta da prendere prima di implementare GI/RTR è il backend di destinazione. Gli shader e i contratti restano riutilizzabili come specifica; una migrazione di motore richiede porting, asset work e profiling espliciti.
