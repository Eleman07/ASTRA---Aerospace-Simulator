# ASTRA Desktop 2.4.1 — guida utente

## Stick e menu separati

Gli stick controllano esclusivamente l'assetto e non spostano il focus, non cambiano missione e non modificano i campi dei menu. La croce direzionale e le frecce della tastiera navigano l'interfaccia; A conferma la voce selezionata e B annulla/torna indietro. **START avvia o mette in pausa il volo**, X richiama GNC/pausa sicura e Y arma/disarma. Le stesse regole valgono per spazio, aereo e UAV e per i pannelli secondari.

## Risposta dei comandi

Il profilo **XBOX · RISPOSTA PRONTA** usa sensibilità 1,8 (+20%), zona morta 0,08 e manetta 140 punti percentuali al secondo. Nel pannello CONTROLLER puoi scegliere curva lineare/esponenziale, filtro, sensibilità, velocità manetta e leggere risposta API. Il rilascio dei grilletti conserva la spinta; il pulsante profilo ripristina la calibrazione standard. Calibra il centro con gli stick rilasciati e arma esplicitamente.

Il controller Xbox va assegnato soltanto a **Primario**. Manetta e pedali separati richiedono dispositivi distinti. La lettura avviene a ogni frame, l'invio arriva fino a 60 Hz senza accodare comandi vecchi. START è riservato al volo e non attiva anche un pulsante dell'interfaccia selezionato. La dinamica resta fisica: il riferimento cambia rapidamente, mentre massa, inerzia, coppie e velocità degli attuatori determinano il movimento del veicolo. Durante il lancio il TVC richiede spinta; i comandi su un razzo fermo sulla rampa non lo ruotano come una camera.

## Assetto orbitale condiviso

La causa del veicolo che tornava alla verticale era nel codice comune: il controllore di assetto ricalcolava a ogni passo un target LVLH solidale alla verticale locale anche in manuale. In orbita la guida di salita era già disattivata fuori da GNC automatico; era il servo d'assetto a ripristinare continuamente il target. Ora in manuale il GNC LVLH viene rilasciato, la coppia arriva dagli input e con stick neutri l'assetto non viene riportato a “su”. GNC automatico conserva il comportamento LVLH.

Nel pannello manuale orbitale seleziona: Manuale/Inerziale, Stability Assist, Prograde, Retrograde, Radiale entrante/uscente, Normale/Anti-normale o Target. Nodo di manovra richiede un vettore `maneuver_direction_eci` definito via API Python. Simulatore e Gioca usano lo stesso codice d'assetto.

## Gioca

Gioca presenta solo tre ingressi: **Spazio**, **Aereo** e **Drone**. La campagna comprende 12 operazioni narrative: tre per ciascuna categoria (Ingegneria, Esplorazione, Pilotaggio e Scienza). Ogni scheda presenta capitolo, briefing di controllo missione, obiettivi e ricompense; la fisica verifica telemetria di quota, tratta, rendezvous, mantenimento quota e atterraggio. Crediti, reputazione, scienza, sblocchi e strutture sono salvati localmente. Spazio accompagna dalla messa in orbita alle operazioni lunari; Aereo propone collaudi e rientro su pista; Drone comprende ispezione e campagne di campionamento.

## Avvio e prestazioni

Installa il nuovo pacchetto Windows, poi apri ASTRA Desktop dal menu Start. Non servono Internet, browser o Python per il simulatore. FPS unlimited e VSync disattivato. Il menu GRAFICA offre Basso/Medio/Alto/Ultra; i preset scalano risoluzione, scattering, ombre, glow, SSAO, SSR e SDFGI. Il tempo fisico resta indipendente dal rendering. Il terreno viene caricato in chunk attorno al veicolo con memoria limitata e culling; oltre l'ortofoto locale la copertura è procedurale, non un database cartografico mondiale.

Il cielo usa scattering Rayleigh e Mie a 4/8/16 passi, stelle HDR multi-magnitudine, Via Lattea procedurale e nebulosa blu a strati. La presentazione interpola assetto e terreno tra snapshot a 30 Hz, fino a 60 Hz durante il pilotaggio locale. Gli FPS effettivi dipendono dall'hardware e dalla scena; nessun preset garantisce la stessa frequenza su tutti i PC.

## Propulsione, audio e cinematografia

I flipbook HDR WispySmoke01 e Flame02 di Unity Labs Paris / Thomas ICHÉ (CC0) sono inclusi offline. Il fumo usa un atlas 8×8 e il getto atmosferico una sequenza 16×4 a 24 fps; le sorgenti e le modifiche sono nei crediti.

Getti e luce dei motori sono guidati dalla spinta applicata dal motore fisico, i rotori/eliche dalla potenza o dal regime effettivo. Fumo atmosferico e bagliore sono effetti di presentazione. Il rientro mostra incandescenza quando il flusso termico calcolato è sufficiente. Da GRAFICA puoi attivare/disattivare gli effetti cinematografici e la vibrazione della camera, e regolare i suoni. I suoni sintetici rappresentano rumore/vibrazioni percepiti a bordo: non propagazione acustica nel vuoto.

Il basamento di stampa 3D presente sotto i motori nel modello NASA SLS/Orion è escluso dal veicolo: vengono rimossi solo i 12 triangoli del supporto, conservando gli ugelli. La rampa NASA resta ancorata al sito terrestre e non accompagna più il veicolo. La versione orbitale elimina anche il piccolo accessorio WH_Box e corregge l'asse dell'ugello. I modelli restano riferimenti visivi, non certificazioni del veicolo reale.

## SDK Python 2.4.1

Scarica `astra_simulator_client-2.4.1-py3-none-any.whl` dalla release GitHub e installalo con **lo stesso interprete Python dell'editor**:
```powershell
python -m pip install --no-index --upgrade --force-reinstall --no-deps .\astra_simulator_client-2.4.1-py3-none-any.whl
```
Poi usa l'import indipendente:
```python
from astra_sdk import AstraClient, CLIENT_VERSION

client = AstraClient()
print(CLIENT_VERSION)
print(client.client_info())  # versione, percorso modulo, interprete
print(client.status())
client.pause()
client.reset('space', 'orbital', advanced_models=True)
client.launch()
for _ in range(100):
    client.command(mode='python', throttle_pct=0, attitude_target_deg=[5, 0, 0])
    state = client.step(0.1)
    print(state['time_s'], state['altitude_m'])
```

Per SAS e carriera: `client.orbital_attitude('prograde')`, `client.game_catalog('space')`, `client.start_game_mission('space_skyward')`, `client.game_state()` e `client.game_career()`.
`astra_sdk` funziona anche in presenza di una vecchia cartella locale `astra` che nasconde il pacchetto aggiornato. Restano disponibili gli import compatibili `astra.client` e `astra_desktop_client`. Il campo `version: 1.5.0` nello stato identifica il motore scientifico conservato; `desktop_version` e `client_version` identificano applicazione e SDK. Se `pause()` manca, controlla `client_info()` e seleziona l'interprete sul quale hai installato il wheel.

# ASTRA Desktop 2.2.0 — novità

Nel menu OPERAZIONI DI VOLO sono disponibili **GIOCA** per lancio, orbita, Luna, aereo e UAV. Scegli il profilo e premi GIOCA / RIPRENDI. La modalità libera mantiene il comando manuale e non segue il circuito o il rendezvous automatico delle missioni. I comandi di tastiera e controller sono gli stessi. G / PAUSA SICURA e la perdita del dispositivo fermano il tempo in modalità libera; nelle missioni torna il GNC. Dal lancio libero il razzo attende sulla rampa una spinta superiore al peso prima di iniziare il volo. Le risorse, lo stallo e gli urti restano fisici. RESET ripristina il veicolo.

Nel pannello VOLO, sotto i valori principali, **DATI ESSENZIALI · DETTAGLI** contiene sei menu espandibili: assetto e rotazione; posizione e velocità; orbita e rendezvous; meccanica del volo; propulsione ed energia; navigazione e comandi. Ogni valore indica unità e riferimento; i dati non applicabili sono contrassegnati N/A o —. I quaternioni usano l'ordine w,x,y,z. Le velocità ECI sono inerziali; le velocità corpo u,v,w e i vettori NED/ENU non sono intercambiabili. I coefficienti e i margini di stallo provengono dal modello attivo. Elementi orbitali osculanti a due corpi, non effemeridi di precisione.

La rotella consente ora di allontanarsi fino a 50.000 km: il terreno locale si raccorda alla sfera analitica, senza contorni rettangolari. Le texture NASA della Luna e le mappe Solar System Scope dei pianeti sono incluse offline; da SISTEMA SOLARE / TRANSFER → OSSERVA CORPO si può ispezionare una superficie. Le dimensioni dei corpi nella mappa generale sono aumentate per la leggibilità. Terra e Luna condividono la scena con la nebulosa azzurra e le stelle: il riferimento visivo delle effemeridi è 2026-10-28 UTC + tempo simulato; il sito lunare è illustrativo e non geolocalizzato. La rampa usa il Mobile Launcher NASA / Samuel H. Neblett, adattato alla scala del veicolo ASTRA: non certifica la compatibilità ingegneristica del veicolo reale.

Client Python 2.2.0, nuove letture e volo libero:
```python
from astra_sdk import AstraClient
c = AstraClient()
c.free_flight('aircraft', advanced_models=True)  # inizialmente in pausa
print(c.flight_details())
c.command(mode='python', throttle_pct=75, pitch_deg=4)
c.launch()
state = c.step(0.1)  # clock esclusivo allo script
```
`play()` restituisce il clock al desktop; `step()` lo acquisisce allo script. La fisica e gli endpoint precedenti restano disponibili.

# ASTRA Desktop 2.1 — Windows 11 x64, offline

ASTRA.exe avvia il motore Python e una finestra Godot nativa. ASTRA-Renderer.exe è il processo grafico, non va avviato separatamente. Python, librerie, texture e modelli sono inclusi. Non occorre una connessione Internet; l'API usa esclusivamente l'indirizzo locale 127.0.0.1. Il renderer non integra le equazioni: legge istantanee del medesimo motore scientifico ASTRA.

## Avvio e qualità

Installa ed avvia ASTRA Desktop dal menu Start. Il collegamento «Grafica leggera» seleziona OpenGL Compatibility, 30 FPS massimi e meno effetti. Il collegamento principale usa Forward+ con Vulkan e fallback OpenGL. Per scegliere esplicitamente un profilo:

    ASTRA.exe --quality low
    ASTRA.exe --quality balanced
    ASTRA.exe --quality high
    ASTRA.exe --quality ultra

High aggiunge SSR; Ultra aggiunge SSIL e, negli ambienti locali supportati, SDFGI. Il limite FPS è configurabile dal pannello GRAFICA. La fisica è la stessa in tutti i profili. OpenGL 3.3 o Vulkan supportato dal driver, Windows x64 e una GPU compatibile sono necessari. Non viene garantita una velocità minima su tutti i PC. Il motore Godot supporta backend differenti, ma ciò non elimina i limiti di hardware, memoria o driver. Un problema grafico va prima verificato con il collegamento leggero.

## Missioni e comandi

Scegli missione e profilo fisico nel pannello sinistro, poi AVVIA MISSIONE. SPAZIO alterna avvio/pausa; G riprende il GNC automatico; M abilita la tastiera manuale. WASD controlla assetto, Q/E imbardata, Shift/Ctrl aumenta/riduce spinta, B frena. Tasto destro e trascinamento ruotano la camera; rotella cambia distanza; F11 alterna schermo intero.

Il controllo manuale cambia i comandi, non disattiva sensori, attuatori, navigazione o modelli scientifici. Nei veicoli che lo prevedono il controllore d'assetto resta responsabile dell'inseguimento dei riferimenti. La scheda MODELLI espone stato, valori e limiti di tutte le 13 discipline avanzate. Il flag avanzato può essere disattivato per confronto con il percorso storico.

CONTROLLER: seleziona il dispositivo primario, lascia gli stick al centro, calibra il centro e premi ARMA. Xbox: stick sinistro roll/pitch; asse destro yaw; RT/LT aumenta/riduce spinta; LB freni; croce direzionale menu; A conferma; B indietro; START avvio/pausa; X GNC; Y arma/disarma. Manetta e pedali separati possono essere assegnati e rimappati. Una manetta assoluta acquisisce il comando solo dopo aver raggiunto il valore corrente. La calibrazione completa termina con TERMINA CALIBRAZIONE; non rimane attiva automaticamente. I profili sono distinti per categoria di veicolo. Disconnessione, perdita di focus o heartbeat interrotto restituiscono il controllo al GNC. Il collaudo software non sostituisce una verifica fisica del dispositivo Xbox/HOTAS dell'utente.

## Strumenti

LABORATORI: 18 solutori indipendenti o sul contesto corrente, risultati SI ed esportazione JSON. I campi supplementari avanzati accettano un oggetto JSON. VEHICLE LAB: configurazione degli stadi e ambiente. DATI: telemetria, registrazione compatta, replay visivo, CSV/JSON, guasti, robustezza, convergenza, requisiti e sistemi. SISTEMA SOLARE: effemeridi, targeting, propagazione e mappa 3D. Le guide orbitali della mappa sono circolari indicative; i calcoli numerici ed i risultati SI restano quelli del motore. ASSET 3D permette di selezionare i modelli inclusi o importare GLB; i parametri fisici del veicolo non cambiano quando cambia un modello illustrativo.

I veicoli procedurali sono rimossi. Le selezioni automatiche usano modelli pre-realizzati: SLS/Orion, Falcon 9/Crew Dragon, bimotore e monomotore Innerscene, quadricottero Innerscene, esacottero Typhoon H480 e lander robotico InSight. Il rendezvous mostra Crew Dragon e una ISS pre-realizzata. I modelli e i rispettivi crediti si consultano in ASSET 3D / CREDITI E LICENZE. Il modello visivo è indicato in basso, separatamente dal profilo fisico ASTRA: non vengono attribuite ai veicoli reali le prestazioni numeriche del profilo. InSight è un riferimento grafico marziano usato nella scena di discesa generica; non è un HLS commerciale né una missione InSight sulla Luna.

La grafica nativa comprende PBR dei modelli importati, ombre geometriche, cielo con nebulosa azzurra HDR precalcolata, Terra e orizzonte lunare analitici, terreno indicizzato e animazioni guidate dalla telemetria. Le mesh statiche opache sono raggruppate per materiale; vetri ed eliche restano separati. Una cache limitata evita la rilettura continua dei GLB. High/ultra usano TAA. F2 mostra la sola vista 3D; GRAFICA consente di variare scala di risoluzione, esposizione, adattamento automatico e profondità di campo fotografica (ultimi due su Forward+). SSR non equivale a ray tracing hardware; l'atmosfera è un'approssimazione di singolo scattering. Questa build non dimostra né dichiara parità o superiorità visiva rispetto a Star Citizen. L'architettura AAA proposta in precedenza resta un obiettivo distinto dalle funzioni effettivamente implementate.

## Plugin / SDK Python

Installa il file wheel incluso, con Python 3.10 o successivo sul PC che esegue lo script:

    python -m pip install astra_simulator_client-2.2.0-py3-none-any.whl

Il simulatore stesso non richiede Python installato. Avvia ASTRA, poi:

    from astra_sdk import AstraClient
    client = AstraClient()  # rileva la porta della sessione desktop
    print(client.status())
    client.pause()
    client.reset('space', 'orbital', advanced_models=True)
    client.launch()
    for i in range(100):
        client.command(mode='python', attitude_target_deg=[10, 5, 0])
        state = client.step(0.1)
    print(client.snapshot()['desktop'])

L'alias `from astra_desktop_client import AstraClient` è disponibile. Non sono richieste dipendenze Python esterne. Il primo step acquisisce il clock esterno e ferma quello automatico: la finestra continua a mostrare la simulazione senza doppia integrazione. `client.play()` restituisce il clock al desktop. `client.close()` non chiude la finestra dell'utente. Per avviare esplicitamente l'app da Python: `AstraClient.launch_desktop(r'C:\percorso\ASTRA.exe')`.

I metodi storici status/models/state/reset/launch/step/command/stage/engineering/fault restano disponibili. Sono aggiunti snapshot, features, play, pause, set_speed, acquire_clock, recording, configure_systems, configure_route, robustness, convergence, verify_requirements, celestial e transfer. La base URL esplicita o ASTRA_API_URL prevale sul rilevamento. Più istanze GUI usano porte locali differenti; il file connection.json identifica l'ultima avviata. È possibile impostare una porta esplicita con --port.

API visuali 2.1 (il renderer deve essere aperto per le catture):

    print(client.visual_models())
    client.set_view(model='space-x-crew-dragon', show_ui=False, exposure=0.8)
    client.set_camera(azimuth_deg=55, elevation_deg=18, distance_m=13)
    print(client.renderer_status())  # backend, GPU, asset, draw call, cache, camera
    client.capture(r'C:\percorso\frame.png', overwrite=True)
    client.set_view(show_ui=True)

`capture` salva un PNG reale e attende la conferma del renderer; la directory deve già esistere. Senza overwrite=True un file esistente viene rifiutato. Le richieste di camera, modello e cattura non avanzano il tempo fisico. `view()` legge le impostazioni richieste; `renderer_status()` riporta lo stato effettivamente applicato. `telemetry(samples=100, interval_s=0.1)` è un iteratore di letture, non chiama step().

## Dati e rimozione

Profili controller e carriera risiedono nei dati utente di Godot (ASTRA Desktop); la connessione API in %LOCALAPPDATA%\ASTRA Desktop. Esportazioni e GLB importati restano dell'utente. L'uninstaller rimuove soltanto i file elencati nel manifesto del pacchetto; non elimina ricorsivamente cartelle o dati personali. La vecchia distribuzione browser resta separata. Questo installer non è firmato digitalmente.
