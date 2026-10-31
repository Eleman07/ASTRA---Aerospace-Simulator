# ASTRA: rendering, controller e distribuzione Windows offline

Questa consegna implementa un incremento verificato del simulatore esistente.
Non costituisce il completamento di tutti gli obiettivi della specifica iniziale:
i nuovi algoritmi scientifici riguardano **propulsione 1D** e **analisi modale
della trave**. Le etichette MODELLO PARAMETRICO restano invariate.
`README.md` non viene modificato.

## Avvio Windows 11 senza Internet

Estrarre **tutto** `dist/ASTRA-Windows-Offline.zip` e avviare
`ASTRA-Windows/ASTRA.exe`. Il pacchetto contiene CPython, il motore ASTRA,
i modelli 3D, le texture e il frontend. Non richiede Python installato, Pyodide,
un account, servizi cloud o download al primo avvio. Serve un browser WebGL2;
le prove sono state eseguite con Microsoft Edge su Windows 11 x64.

Il browser apre `http://127.0.0.1:8765`. La finestra del motore deve restare
aperta; Ctrl+C termina il server. Se la porta è occupata:

```powershell
.\ASTRA.exe --port 8766
```

La distribuzione è portabile, non è un installer e non è firmata digitalmente.
Conservare l'eseguibile insieme alla directory `_internal`.
I profili controller e i dati missione continuano a essere salvati nel browser,
associati all'origine, quindi anche alla porta locale.

Dal sorgente si può usare `Start-ASTRA.cmd` oppure:

```powershell
python windows_launcher.py
```

In questo caso serve Python già installato; non vengono installati pacchetti.
Per ricostruire il pacchetto su Windows, con PyInstaller 6.22.3 disponibile:

```powershell
python tools/build_windows.py
```

Il build scarica **zero** risorse; tutti gli asset provengono dal repository.
`dist/windows-build.json` registra dimensione, SHA-256 e risultato del self-test.
Il workflow `windows.yml` installa PyInstaller durante il build e produce lo ZIP
come artifact. Internet serve a quel build CI, non all'esecuzione del pacchetto.

`windows_launcher.py` riusa `server.Handler` ma serve un trasporto browser che
esegue davvero `/step` nel Python nativo. Il comportamento di `server.py`, dove
un controller Python esterno possiede il tempo e il viewer interroga lo stato,
resta disponibile. Il server Windows ascolta esclusivamente su loopback e la
Content Security Policy limita fetch, immagini e script alle risorse locali.
La versione statica GitHub Pages conserva worker Pyodide e PWA.

## Audit e integrazione

Il renderer originale aveva già GGX/Smith/Schlick, trasformazione normale
inversa trasposta, tone mapping filmico, COESA76 separata dalla grafica, texture
terrestri e animazioni dei rotori. Il motore aveva già 6-DoF, vento Dryden,
RCS/TVC, stadi, navigazione relativa filtrata e modelli di sottosistemi.
Queste capacità sono riutilizzate. Non vengono attribuite a questa consegna.

Le modifiche seguono questi confini:

- `rendering.js`, `vehicle-glb.js`, `render-settings.js`: materiali e qualità;
- `controller-profiles.js`, `input-device-manager.js`,
  `controller-manager-ui.js`: hardware, calibrazione, condizionamento;
- `pilot-controls.js` e `app.js`: setpoint esistenti e camera;
- `astra/nozzle.py`, `astra/engineering.py`: solutori scientifici indipendenti;
- `astra/engine.py`: telemetria della spinta applicata, senza cambiare le forze;
- `windows_launcher.py`: trasporto nativo per l'esecuzione offline.

## Grafica effettivamente implementata

Il caricatore GLB conserva normal map, fattore di scala normale, occlusione
(canale R), intensità AO e texture emissiva. Base color/emissive sono decodificati
da sRGB, mentre metallic/roughness, normali e AO restano dati lineari. AO agisce
sull'illuminazione indiretta, non sulla luce diretta. La normal map utilizza un
riferimento tangente ricostruito dalle derivate di posizione/UV; le normali sono
corrette anche per facce posteriori. Le texture incorporate glTF non vengono
capovolte verticalmente. Le unità sampler senza materiale hanno texture neutre
complete, evitando dipendenze dallo stato lasciato dal draw precedente.

Il cielo orbitale usa un'approssimazione delle funzioni di fase Rayleigh e
Henyey-Greenstein/Mie sul bordo atmosferico, con attenuazione sul lato notturno.
Non è un'integrazione spettrale dell'atmosfera, né un LUT multiscattering.
La superficie terrestre mantiene il modello di illuminazione direzionale,
con contributo notturno ridotto. Non sono stati aggiunti asset notturni fittizi.

Il nuovo plume usa otto vertici in due piani trasparenti incrociati, invece di
due sfere ad alta risoluzione. Accensione/intensità derivano da
`propulsion.applied_thrust_N`; area dell'ugello e pressione ambiente determinano
scala ed espansione. La fase temporale anima soltanto la grafica. Nessuna forza
dipende dal plume: i coefficienti di forma sono un'approssimazione visiva,
non una soluzione fluidodinamica o un modello di shock diamonds validato.

LOW/BALANCED/HIGH/ULTRA controllano budget pixel, DPR, texture, mesh, stelle,
frame rate obiettivo e bordo atmosferico. Risoluzione e atmosfera cambiano subito;
texture, mesh e MSAA vengono scelti all'avvio. Il controllo GRAFICA esplicita
questa distinzione. L'esposizione è persistente. I valori FPS nell'interfaccia
sono etichettati come obiettivi, non misure. Non sono riportati benchmark GPU,
FPS misurati, uso VRAM, HDR framebuffer, bloom, SSAO o shadow mapping aggiuntivi.

Riferimento: [specifica glTF 2.0, materiali e spazi colore](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
Sono supportate mappe su TEXCOORD_0 senza KHR_texture_transform per le nuove
texture; le mappe aggiuntive non implementate sono omesse con avviso nei dettagli
del modello, conservando la geometria. Riferimenti immagine invalidi sono rifiutati.

## Controller: utilizzo e autorità

1. Collegare il controller e premere un pulsante per renderlo visibile al browser.
2. Aprire CONTROLLER e selezionare il dispositivo principale.
3. Scegliere il preset; assegnare eventuali leva e pedali separati.
4. Per HOTAS/joystick usare RILEVA, CENTRO e FISSA su ogni asse, quindi provare
   min/max, inversione, zona morta, esponenziale e filtro.
5. Salvare il profilo, passare a manuale e premere ABILITA CONTROLLER.
6. Centrare gli assi d'assetto per acquisire il controllo. Una leva assoluta
   richiede anche l'allineamento al gas attuale entro 7 punti percentuali.

La connessione da sola non modifica GNC o modalità Python. Il preset standard
usa stick sinistro per rollio/beccheggio, stick destro X per imbardata, trigger
RT/R2 e LT/L2 per incremento/decremento gas, A/Croce per freni dell'aereo,
D-pad orizzontale e stick destro Y per camera, LS/L3 per ricentrarla e
Menu/Options per tornare al GNC. Drone Mode 1/2 e il preset precedente ASTRA
sono disponibili. La compatibilità standard è basata su `mapping=standard`,
non su un nome commerciale. I nomi PlayStation/Xbox sono solo etichette.

Il profilo HOTAS è **provvisorio**: rollio asse 0, beccheggio asse 1,
imbardata asse 2 e leva assoluta asse 3, tutti modificabili. Non rappresenta
una mappatura verificata di Logitech X52/X56 o di uno specifico Thrustmaster.
Ogni binding può usare una delle tre periferiche selezionate. ID e indice
devono entrambi corrispondere; se cambiano alla riconnessione, riselezionare
il dispositivo. Questo evita che un nuovo dispositivo erediti un vecchio indice.

L'arbitraggio, in manuale, dà precedenza a tastiera e interazione touch/mouse
recente, poi al controller abilitato. Le azioni di camera hanno binding separati
e un profilo che condivide un asse analogico camera/volo viene rifiutato.
Il ritorno osservato a modalità automatica/Python revoca l'abilitazione hardware.
Non è un protocollo distribuito di esclusione fra client HTTP concorrenti:
per controller Python esterni usare la modalità Python e il trasporto viewer
esistente di `server.py`.

Disconnessione di una periferica assegnata, assi mancanti/NaN/Inf, perdita di
focus o cambio modalità revocano l'autorità, azzerano gli input momentanei e
richiedono una nuova abilitazione. Il frontend richiede il GNC esistente per
il veicolo; non impone un taglio universale del gas. Non è una garanzia di
recupero o di atterraggio sicuro. I pulsanti di azione usano fronti di salita;
i filtri sono esponenziali con costante di tempo esplicita e dt limitato.

Il manager mostra assi hardware, barre, posizione dello stick calibrato,
pulsanti reali, valori filtrati, setpoint inviati e assetto/rate del veicolo.
I profili JSON sono validati, esportabili, importabili, duplicabili, locali
e separati per categoria. I dati salvati dalle versioni precedenti restano
nelle chiavi originali; il nuovo sistema usa chiavi `astra-controller-*`.
Rumble ordinario è opzionale e rilevato a runtime per decollo/contatto;
non sono implementati trigger adattivi DualSense.

I comandi di rollio/beccheggio/imbardata sono **setpoint di assetto** destinati
ai controllori fisici esistenti. Per la missione orbitale vengono aggiornati
anche gli effettivi setpoint `attitude_target_deg`. Non sono comandi diretti
di coppia, superfici, flap o sei assi RCS. La traslazione RCS indipendente,
WebHID e ponti proprietari non vengono dichiarati disponibili.

| Famiglia | Protocollo implementato | Test sintetici | Hardware fisico |
|---|---|---|---|
| Xbox compatibile standard | Gamepad API | Sì: assi, trigger, freni, pulsanti | Non verificato |
| DualSense compatibile standard | Gamepad API, nomi PlayStation | Sì: schema standard | Non verificato |
| Logitech/Saitek, Thrustmaster | Gamepad API se esposti dal browser, calibrazione | Sì: layout generico, leva/pedali separati | Non verificato |
| VKB, VIRPIL, WINWING, altri HID | Stesso percorso se esposto come Gamepad | Logica generica soltanto | Non verificato |
| Rumble | Feature detection `vibrationActuator` | Assenza dell'attuatore e gestione errori | Non verificato |
| HID non esposto dal browser / trigger adattivi | Nessun protocollo specifico | Non disponibile | Non verificato |

Riferimento di protocollo: [Gamepad API W3C](https://www.w3.org/TR/gamepad/).
Disponibilità dei dispositivi e riconoscimento USB/Bluetooth restano dipendenti
da browser, sistema operativo e driver.

## Equazioni scientifiche e risultati

L'ugello risolve entrambi i rami della relazione area/Mach. La pressione critica
di choking è calcolata all'uscita sul ramo subsonico del diffusore, non
semplicemente confrontando l'ambiente con la pressione sonica in gola.
Nel regime non strozzato la pressione d'uscita uguaglia l'ambiente e la portata
si ricava dal Mach subsonico in gola. Per un urto interno la posizione As/At
è trovata per bisezione, applicando Rankine-Hugoniot, perdita di pressione
totale e successiva diffusione isentropica. Il totale entalpico resta costante.

Le verifiche includono il caso sonico analitico, continuità
`mdot = rho_e A_e V_e`, conservazione `cp T0 = cp Te + Ve²/2`, raccordo fra
regimi, pressione ambiente e perdita entropica all'urto. I tre regimi campione
hanno residuo relativo di portata inferiore a 1e-11. Rimangono esclusi chimica,
strati limite, separazione viscosa, urti obliqui e transienti di accensione.
Riferimenti: [portata comprimibile NASA Glenn](https://www.grc.nasa.gov/www/k-12/airplane/mflchk.html),
[urto normale NASA Glenn](https://www.grc.nasa.gov/www/k-12/airplane/normal.html).

La trave aggiunge una matrice di massa Hermite consistente a quella di rigidezza
e risolve `K phi = omega² M phi` per il primo modo con iterazione inversa e
Cholesky a banda. Nessuna dipendenza NumPy/SciPy è necessaria in Pyodide.
Per la trave uniforme E=70 GPa, rho=2700 kg/m³, L=2 m, b=0,1 m, h=0,08 m:

| Elementi | Frequenza FEM (Hz) | Errore relativo sul riferimento |
|---:|---:|---:|
| 2 | 16,458388060 | 4,8344e-4 |
| 4 | 16,450973367 | 3,2708e-5 |
| 8 | 16,450469571 | 2,0830e-6 |
| 16 | 16,450437456 | 1,3080e-7 |

Il riferimento analitico è 16,450435305 Hz, da beta1=1,875104068711961
e `f1 = beta1² sqrt(EI/(rho A))/(2 pi L²)`.
I residui relativi agli autovalori sono inferiori a 1e-7. Sono verificate
anche flessione statica, reazioni vincolari e scalatura con la densità.
Riferimento: [derivazione della trave a sbalzo, TU Graz](https://lampz.tugraz.at/~hadley/memm/mechanics/cbeam.php).
Non è un FEM 3D o Timoshenko; non calcola torsione, buckling o risposta forzata.

I risultati riproducibili con parametri, metodi, errori e PASS/FAIL sono in
[`validation/next-generation.json`](validation/next-generation.json), generabili
con `python tools/validate_next_generation.py`. Ugello avanzato e modi della
trave sono studi indipendenti/snapshot; non vengono spacciati per nuovi modelli
accoppiati alla missione. Il precedente accoppiamento pressione-spinta del
motore è mantenuto; la nuova telemetria di spinta alimenta solo il renderer.

## Verifiche eseguite e ripetibili

- Suite Python completa: 60 test, inclusi HTTP locale e 10 nuovi test fisici.
- Suite JavaScript: 27 test di controller, profili, glTF e preset grafici.
- Syntax check di tutti i moduli JavaScript di primo livello.
- Edge headless con WebGL2/SwiftShader: avvio, shader, plume, asset locali,
  comandi e risposta fisica su aereo/drone/razzo, ritorno GNC dopo unplug.
- Eseguibile Windows: self-test nativo sulle tre categorie e prova del frontend
  con tutte le richieste esterne bloccate. Zero richieste esterne osservate.
- Screenshot e rapporto JSON del browser prodotti sotto `test-results/`.

SwiftShader è un renderer software: queste prove verificano compilazione e
integrazione, non prestazioni di una GPU fisica. Il collaudo finale usa LOW;
non è un benchmark dei quattro preset. I controller sono sintetici. La versione
Pyodide è coperta dai test manifest/bridge, senza un avvio WebAssembly reale
in questa sessione.
La pipeline GitHub Actions è stata aggiornata, ma non è stata eseguita su
GitHub in questa sessione; non vengono dichiarati pubblicazione o deploy riusciti.

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s tools -p 'test_*.py' -q
node --test tools/controllers.test.mjs tools/rendering.test.mjs
Get-ChildItem -File -Filter *.js | ForEach-Object { node --check $_.FullName }
python tools/validate_next_generation.py
python tools/build_windows.py
$env:ASTRA_BROWSER_CHANNEL='msedge'
$env:ASTRA_TEST_EXE=(Resolve-Path dist/ASTRA-Windows/ASTRA.exe).Path
node tools/browser-smoke.cjs
```

L'ultimo comando di test richiede Playwright nell'ambiente Node del collaudo,
non nella distribuzione. Il runtime Windows/Python non lo usa.

## Limiti e obiettivi ancora aperti

Non sono stati implementati nuovi modelli per le altre undici discipline,
MPC/SCvx, nuovi kernel SPICE, 3D SLAM, docking/contact safety, terrain-relative
navigation, nuovi modelli aerodinamici calibrati o risposta modale accoppiata.
Rimangono i limiti dichiarati dal catalogo esistente, salvo l'aggiornamento
puntuale di propulsione e strutture. Anche camera cinematicamente smorzata,
shadow maps, HDR multi-pass, LUT atmosferici e supporto HID non-Gamepad restano
fuori da questa consegna. Nessun dato sperimentale è stato inventato.

Per una prova fisica: verificare gli assi con il veicolo fermo, salvare il profilo,
avviare una missione e controllare segno, estremi e neutralità per ogni comando;
scollegare prima la periferica principale e poi eventuali leva/pedali, verificando
il ritorno GNC e l'obbligo di riabilitazione. Ripetere su USB/Bluetooth e annotare
browser, sistema operativo, nome/ID esposto e mapping. Queste prove manuali
**non sono state eseguite** con hardware reale in questa sessione.

## Commit e pubblicazione del sorgente

Eseguire dalla radice del repository dopo revisione:

```powershell
git diff --check
git add .github/workflows/pages.yml .github/workflows/windows.yml .gitignore app.js astra/engine.py astra/engineering.py astra/nozzle.py controller-manager-ui.js controller-manager.css controller-profiles.js input-device-manager.js render-settings.js disciplines.js engineering-studio.js index.html pilot-controls.js rendering.js service-worker.js vehicle-glb.js windows_launcher.py Start-ASTRA.cmd tools/build_windows.py tools/browser-smoke.cjs tools/controllers.test.mjs tools/rendering.test.mjs tools/test_next_generation.py tools/test_windows_offline.py tools/validate_next_generation.py docs/NEXT_GENERATION.md docs/validation/next-generation.json
git diff --cached --stat
git commit -m "Improve rendering, calibrated flight controls and offline Windows runtime"
git push origin main
```

Il push su main attiva Pages; per lo ZIP Windows eseguire manualmente il workflow
**Build ASTRA Windows offline** da GitHub Actions. `dist/` e gli artifact di test
sono ignorati e non vengono inclusi nel commit. Nessun commit o push è stato
eseguito automaticamente.
