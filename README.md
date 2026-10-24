# ASTRA Browser 1.3.1 · On-device Python & WebGL (PWA)

**[Guida completa GitHub Pages + Android / iOS / Desktop](GITHUB-PAGES-TUTORIAL-IT.md)**

This static edition runs a copy of ASTRA Python physics via Pyodide/WebAssembly
inside a browser Worker. No Python hosting or API server is needed. Browser
physics source is public when this site is published. The separate HTTP SDK
requires the original Python server and cannot attach to this browser Worker.

For fully offline use, self-host the Pyodide core via
`python3 tools/prepare_pyodide.py` (also executed by GitHub Actions), then
press `SALVA PER OFFLINE` on the installed PWA while online.

---

# ASTRA 1.0

ASTRA è un simulatore aerospaziale gratuito e open source, pensato per imparare,
giocare con missioni e sperimentare con controller software. La simulazione
gira localmente: il server HTTP e il motore fisico sono Python standard, mentre
la scena 3D gira nel browser sul dispositivo dell'utente.

## Avvio rapido

Richiede Python 3.10 o successivo; non richiede pacchetti esterni.

```sh
python3 -m astra
```

Apri <http://127.0.0.1:8765>. Il server genera `dist/` dai file correnti a ogni
avvio, così l'app e la versione distribuita restano allineate.

Su Windows, Ubuntu e macOS si usa Python 3 nel terminale. Su Android e iOS si
può aprire ASTRA da un browser aggiornato. Per accedervi da un altro dispositivo
sulla stessa rete Wi-Fi, avvia il server con `python3 -m astra --host 0.0.0.0`
e usa l'indirizzo LAN del computer. L'API locale non ha autenticazione: usare
questa modalità solo su una rete fidata e non esporla su Internet.

## Engineering Studio — sette nuovi solutori scientifici

Il pannello **Engineering Studio** è accessibile dall’icona laboratorio nella barra laterale.
Integra strumenti **indipendenti** per orbite (Cowell RK5(4) adattivo, J₂, drag),
propulsione (ugello de Laval e inversione area–Mach), aerodinamica (trim numerico),
strutture (FEM di Hermite), termica (volumi finiti impliciti), energia orbitale
(pannelli solari ed eclissi) e collegamenti radio (Friis / Shannon).
I parametri sono in SI; i risultati includono limiti, grafici quando pertinenti
e download JSON. **I solutori non modificano il motore di volo attivo** e non
sono strumenti di certificazione.

Endpoint: `GET /api/v1/engineering` elenca i solutori,
`POST /api/v1/engineering` accetta `{"analysis":"orbit","duration_s":5400}`
e restituisce telemetria e assunzioni. Con Python: `AstraClient().engineering("beam",
tip_force_N=-500, elements=20)`; vedi `examples/python_engineering_studio.py`.
Il client MATLAB espone anche `sim.engineering("thermal", struct(...))`.
Documentazione approfondita: [ENGINEERING-STUDIO.md](ENGINEERING-STUDIO.md).

## Modalità SIM e GIOCA

- **SIM**: missioni controllate da sequenziatore GNC, comandi manuali o codice.
- **Vehicle Lab**: assembla stack fino a quattro stadi con serbatoi e motori per stadio. Massa, propellente e spinta di ogni stadio alimentano la dinamica ECI; allo svuotamento, la massa secca viene separata e il motore successivo si accende. Il pilota può anche separare manualmente dal pulsante o dall'API: ASTRA spegne il motore e contabilizza propellente e massa scartati. Il preset LEO a quattro stadi fornisce circa 9,22 km/s ideali con una riserva ACS da 60 kg inclusa nella massa; mantiene inoltre propellente per circolarizzazione e deorbita. Il catalogo delle parti è esposto via API; la spinta segue la correzione della pressione ambientale dell'ugello, il consumo usa la stessa spinta effettiva, il T/W diagnostico usa il livello del mare e il Δv è calcolato con Tsiolkovsky a stadi, ideale nel vuoto e senza perdite gravitazionali o aerodinamiche.
- **Mission Data Lab**: crea una registrazione pulita a ogni reset per veicoli spaziali, aerei e droni; conserva anche lo snapshot API completo prima del lancio, con modello, configurazione e condizioni iniziali. Registra ogni secondo simulato e a ogni transizione di fase l'intero stato restituito dall'API del motore, fino a 4096 campioni. Gli snapshot includono i campi disponibili per il veicolo: fase e tempo, posizione, velocità al suolo e velocità rispetto all'aria con frame NED/ECI esplicito, assetto o comando d'assetto, comandi, GNC e stime di navigazione, parametri del veicolo, propellente o batteria, ambiente, eventi di staging, orbita e metriche di missione. Il JSON conserva la struttura originale dentro `sample.state`, include metadati di missione e un dizionario dei campi con unità, tipo e conteggio di valori presenti, nulli o non restituiti. Il CSV appiattisce tutti i campi annidati in colonne `state.*` e aggiunge i metadati `mission.*`, incluso lo snapshot iniziale. Il grafico include errore d’assetto, fattore di carico e riserva ACS; il campione selezionato mostra subito stato/fase, assetto, posizione con frame, tipo di orbita quando applicabile e fattore di carico, oltre allo snapshot completo ispezionabile. La registrazione viene conservata localmente in IndexedDB, con ripiego su localStorage quando necessario; se il browser non consente il salvataggio, i dati della sessione restano esportabili finché la pagina è aperta. I campioni oltre il limite vengono decimati e il file dichiara quanti campioni sono stati acquisiti e conservati. Nei profili di lancio l’assetto quaternion 3-DOF del corpo è propagato con inerzia cilindrica approssimata, controllo TVC a due assi durante la spinta e RCS a tre assi in coast; il controllore d’assetto è campionato a 20 Hz, indipendentemente dal passo RK4; la riserva ACS è inclusa nel dimensionamento, nella massa istantanea e nella telemetria. Il navigatore ECI propaga accelerometro corpo e gravità J2, poi corregge posizione e velocità con fix GNSS sintetici a 1 Hz: il ricevitore misura in ECEF e la conversione ECEF→ECI include la velocità di rotazione terrestre; l’IMU è campionata a 20 Hz con bias e rumore deterministici, mentre la covarianza Joseph e un gate NIS dichiarato rigettano fix incoerenti. La guida automatica d’ascesa, inserzione LEO e l’assetto LVLH usano questa stima; Mission Data Lab esporta stima, incertezza, integrità GNSS e stato vero separatamente. Il riferimento quaternion è ideale: errori di giroscopio/assetto, lever arm e geometria discreta dei thruster non sono modellati. Restano inoltre esclusi momenti aerodinamici, slosh e flessibilità. Nel rendezvous LEO l’assetto usa quaternion, coppia gravitazionale e ruote di reazione. Gli elementi orbitali classificano la conica e identificano LEO, orbita ellittica terrestre, traiettoria suborbitale o fuga. La telemetria include la forza specifica traslazionale nel frame corpo e il fattore di carico come norma divisa per g₀; non rappresentano tensioni o margini strutturali.
- **Mission Robustness Lab**: dal Data Lab avvia campagne Monte Carlo con seed riproducibile e un motore isolato per prova. Varia massa, spinta, resistenza e, secondo il dominio, portanza, batteria e vento; la campagna usa sigma dichiarate, distribuzioni normali indipendenti troncate a ±3σ. Confronta esito, durata, pressione dinamica, carico g, flusso termico, touchdown e risorse; riporta P05/P50/P95 e la frazione di missioni concluse con intervallo di Wilson al 95%. Esporta le singole prove in JSON o CSV senza modificare la missione attiva. Le dispersioni sono ipotesi didattiche, non tolleranze misurate; fino a 24 prove (2–4 per il profilo LEO completo). La campagna non è una certificazione di affidabilità o uno studio di convergenza numerica.
- **Convergence Lab**: nel Mission Data Lab ripete il profilo selezionato con passi RK4 `h`, `h/2`, `h/4` e, facoltativamente, `h/8`, `h/16` o `h/32`. Mantiene fissa la cadenza GNC e quella del controllore d’assetto di lancio (20 Hz) e confronta stato ECI o NED, quota, assetto, risorse, picco di pressione dinamica relativa e tempi di transizione delle fasi a un orizzonte comune; mostra l'ordine osservato e applica tolleranze esplicite, regolabili nei campi avanzati o nell'API. Il criterio sul picco q usa una soglia predefinita dello 0,1% rispetto al maggiore dei due valori confrontati (con riferimento minimo di 1 Pa); anche questa soglia è modificabile. Usa motori indipendenti; segnala separatamente fasi divergenti e missioni terminate prima dell'orizzonte. Vale solo per quel veicolo, scenario, modello e intervallo: non dimostra la validità fisica del modello né garantisce la convergenza in ogni condizione. I dati si esportano in JSON e CSV.
- **Failure Injection Lab / FDIR**: inietta una perdita di spinta del motore su razzo/aereo, di un rotore sul drone, perdita barometro su aereo/drone o perdita GNSS anche sul lanciatore. Il navigatore ECI spacecraft fonde accelerometro body a 20 Hz con GNSS sintetico posizione/velocità ECEF a 1 Hz, convertito in ECI includendo la rotazione terrestre; il filtro atmosferico combina barometro e quota GNSS. Se mancano i fix, tutti i filtri propagano l’INS e la covarianza cresce. FDIR dichiara la perdita dopo due epoche senza fix e la telemetria riporta integrità, età dell’ultimo campione valido e scarti. La guida di ascesa usa la stima inerziale finché il GNSS è indisponibile; il relativo rendezvous non espone questo guasto perché usa un sensore relativo separato. In automatico, il drone annulla il decollo se perde GNSS a terra; se è in volo congela il punto stimato e atterra sul posto usando INS e quota barometrica. In controllo manuale o Python la risposta automatica non assume il controllo. Il monitor propulsivo deterministico rileva invece residui a ogni passo fisico. Il Mission Data Lab registra stato sensore, incertezza, rilevamento, azione e log eventi; il ripristino rimuove l'effetto e conserva la storia. Sul pad un T/W residuo ≤ 1 inibisce il lancio spaziale; i guasti propulsivi rilevati durante il decollo annullano il decollo e applicano i freni quando presenti. In volo l’aereo segue la polare per calcolare la velocità di massima efficienza, mantiene la traccia ricavata dal filtro GNSS/IMU e passa alla guida di avvicinamento per un atterraggio forzato. Il drone ricalcola il mixer tenendo conto dei rotori degradati e rientra automaticamente solo se l'allocatore resta a rango pieno, la spinta disponibile è almeno 1,25 volte il peso e la perdita non supera il limite dichiarato per il profilo (30% sul quadricottero, 80% sull'esacottero). Fuori da questo inviluppo il pannello dichiara la risposta consultiva, senza attivare l'autopilota di emergenza. Il drone è segnato come incidentato se il touchdown supera 2,5 m/s. Il terreno usa una superficie piana e non modella ostacoli o selezione di pista; per il veicolo spaziale in volo il monitor resta consultivo. Il rendezvous orbitale con RCS non accetta guasti del motore principale. Python e MATLAB espongono gli stessi endpoint tramite il client locale.
- **External Controller Link Watchdog**: la modalità `python` per i controller programmati sorveglia l'ultimo comando per 1,0 s simulato; ogni chiamata `command()` rinnova il collegamento. I client Python e MATLAB espongono `heartbeat()` per rinnovarlo senza cambiare i setpoint; il blocco Simulink lo rinnova a ogni passo. Alla scadenza, lo spacecraft riprende la guida automatica, l'aereo in volo avvia planata e atterraggio forzato, il drone in volo torna alla piazzola e un decollo aereo/drone ancora a terra viene abortito. `external_control` espone timer, stato e log degli eventi; il controllo manuale può assumere esplicitamente il veicolo e viene segnalato come override. Mettere in pausa la simulazione mette in pausa anche il timer. È un comportamento dimostrativo del simulatore, non un protocollo certificato per veicoli reali.
- **Stack SLS animato per evento**: il visualizzatore mostra lo stack NASA in ascesa, la mesh dell'ICPS e Orion dopo la prima separazione, il veicolo Orion dopo la seconda e la capsula nel rientro. La scala dei GLB segue le dimensioni relative delle configurazioni. La fisica resta quella del profilo ASTRA scelto: gli eventi grafici non sono telemetria di un lancio NASA.
- **SLS completo sulla Mobile Launcher NASA**: la scena iniziale usa il modello ufficiale SLS Block 1 con core stage, booster laterali, stadio superiore e Orion. Il profilo leggero carica la copia a 64.000 triangoli; quello ad alte prestazioni carica la geometria NASA completa, circa 274.000 triangoli, senza decimazione. La rampa è il modello NASA Mobile Launcher assemblato. Entrambi sono asset pre-realizzati con attribuzione e sorgenti riportate in `ASSET-CREDITS.md`.
- **Falcon 9 Block 5 e Crew Dragon**: un modello completo del lanciatore accompagna il decollo; la scena passa alla Dragon 2 con trunk nelle fasi orbitali e alla capsula per il rientro. Per i dispositivi leggeri la mesh pesa circa 1 MB e usa circa 47.000 triangoli; per quelli ad alte prestazioni l’intero stack assemblato mantiene circa 556.000 triangoli. Il modello è visuale e mantiene attribuzione e licenza CC BY-SA 4.0 in `ASSET-CREDITS.md`.
- **Modelli 3D pre-realizzati per i veicoli**: il catalogo aereo include NASA X-57 e un monomotore Innerscene CC0 da 59.988 triangoli per i dispositivi leggeri; i dispositivi ad alte prestazioni caricano la mesh originale da circa 144.000 triangoli. Le pale dell’elica animano dal comando motore e gli RPM sono indicativi, non telemetria fisica. Il drone usa un GLB Innerscene CC0, il rendezvous il GLB NASA della ISS e il lancio la Mobile Launcher NASA. La scala dei modelli è legata alle dimensioni di riferimento, mentre la dinamica resta nel profilo ASTRA. Se un file non si carica, l’asset resta in errore/loading invece di essere sostituito da una mesh surrogata.
- **GIOCA**: progressione persistente separata per pilota, ingegnere e
  scienziato; obiettivi, gradi e osservazioni scientifiche sono salvati nel
  browser dell'utente.
- Spazio, aereo e drone hanno modelli fisici, telemetria e ambienti separati.
  Le missioni automatiche partono da terra e terminano con atterraggio o
  recupero. Lo spazio offre il profilo suborbitale e, con uno stack custom da
  almeno 9,2 km/s di Δv ideale e T/W minimo 1,1 per stadio, una missione LEO
  completa: ascesa e staging, coast fino all'apogeo, circolarizzazione,
  un'orbita completa, orientamento retrogrado RCS con verifica d'assetto,
  impulso di deorbita, ingresso a 120 km, scudo e
  paracadute. Il propagatore usa ECI, gravità centrale e J2, drag COESA76,
  spinta corretta per la pressione ambientale e consumo coerente con la spinta
  effettiva. Cutoff, orbita di inserzione, durata in orbita, deorbita, pressione
  dinamica, flusso convettivo di ristagno e touchdown sono riportati in
  telemetria. Nelle fasi di rientro il flusso e il carico integrato usano la
  correlazione Sutton–Graves per l'aria terrestre e il raggio di punta del
  modello di capsula. È un indicatore cold-wall del punto di ristagno: non
  calcola riscaldamento radiativo, temperatura della parete, conduzione,
  ablazione o dimensionamento del TPS. Il coefficiente terrestre è documentato
  nel [rapporto NASA sulla correlazione](https://ntrs.nasa.gov/citations/19720003329);
  la differenza tra flusso di ristagno e risposta dei materiali è descritta nel
  [rapporto NASA sul dimensionamento TPS](https://ntrs.nasa.gov/api/citations/20060004824/downloads/20060004824.pdf).
  L'atmosfera è un giorno standard statico.
  Durante il volo, il pannello orbitale mostra perigeo, apogeo, semiasse,
  eccentricità, inclinazione e periodo; la guida didattica segue la fase
  effettiva della missione.
- Il profilo **Rendezvous LEO** parte da un'orbita circolare e guida il veicolo
  di servizio ASTRA (massa secca 400 kg, capacità RCS 80 kg, 24 N, Isp 220 s)
  da circa 1 km fino a un punto di mantenimento 20 m dietro il bersaglio.
  Calcola la navigazione relativa nel frame RTN, compresa la velocità corretta
  per la rotazione del frame. Un filtro di Kalman a 6 stati propaga la stima con
  la matrice di transizione Clohessy–Wiltshire e l'ingresso RCS RTN noto a
  accelerazione costante sul passo; parte da un prior gaussiano riproducibile
  (σ posizione 2 m; σ velocità 0,05 m/s), poi fonde fix relativi
  sintetici a 1 Hz con rumore gaussiano (σ posizione 0,5 m; σ velocità
  0,01 m/s). Se un passo RK4 attraversa l'epoca del fix, lo stato del sensore
  è interpolato al tempo esatto e il filtro predice, corregge e riprende la
  propagazione in quell'ordine. Il controllore PD usa questa stima, non lo stato perfetto. La
  telemetria esporta sia la stima sia lo stato reale per confrontarli. Il
  controllore basato sulle equazioni Clohessy–Wiltshire comanda RCS saturati a
  24 N. Il propellente segue la legge di massa di Tsiolkovsky con Isp 220 s.
  La verifica numerica converge in circa 700 s e mantiene il punto senza
  consumo eccessivo. È un modello relativo linearizzato: il sensore è
  sintetico, generato dallo stato del simulatore, e non rappresenta un ricevitore
  GNSS operativo; non include keep-out zone, sensori ottici, attracco o
  collisioni. L'assetto LVLH è un corpo rigido a 3 assi integrato con
  quaternion, coppia gravitazionale terrestre e ruote di reazione saturate; un
  target separato si controlla dal pannello o con il client Python. Il pannello
  espone errore d'assetto, autorità e momento delle ruote oltre a range, velocità
  relativa e fase GNC; il Mission Data Lab registra ogni stato.
- L'Explorer mostra pianeti e lune, effemeridi planetarie JPL SSD approssimate,
  finestre e tempi di trasferimento. Il Lambert universale a zero rivoluzioni
  fornisce il seme della ricerca; la rotta planetaria selezionata viene poi
  integrata con Cowell RK4 sotto la gravità newtoniana del Sole e degli otto
  pianeti, con passi ridotti vicino alle sfere d'influenza. Una matrice di
  transizione dello stato integrata con la dinamica guida le correzioni Newton
  della velocità iniziale; il raccordo iterativo aggiorna anche le direzioni
  dei confini SOI. Il puntamento termina entro 100 m e il raccordo SOI entro
  max(10 km, 10⁻⁴·rSOI).
  Iterazioni e residui sono esposti. Le 97 coppie posizione/velocità
  integrate alimentano l'anteprima 3D e l'API restituisce lo stato con
  interpolazione cubica di Hermite. Le effemeridi sono approssimate e la ricerca
  di finestre è una griglia Lambert, non un'ottimizzazione multi-rivoluzione.
  Il trasferimento Terra–Luna è geocentrico a due corpi e usa un’orbita lunare
  ellittica e inclinata inizializzata dagli elementi medi JPL DE405/LE405 al J2000;
  il semiasse del modello a due corpi viene ricavato dal periodo e dal GM combinato
  Terra–Luna, mentre il semiasse medio JPL resta riportato come riferimento.
  Non usa un’effemeride JPL/Horizons e omette le perturbazioni solari. Le altre
  lune restano orbite circolari illustrative. Per i pianeti, i Δv di partenza e cattura restano stime
  impulsive patched-conic; le tratte da una luna al suo pianeta non sono simulate.
  Nessun percorso interplanetario attuale esegue spinta finita, guida GNC, TCM,
  aerobraking o atterraggio. La rotta è un pianificatore scientifico, non ancora
  un veicolo controllabile che vola tra i corpi.
- La libreria delle discipline copre 20 materie aerospaziali e distingue i
  modelli attivi, semplificati e ancora da integrare.

## Direzione di prodotto

ASTRA combina il ciclo di missione e l'esplorazione approfondita ispirati alle
mod di KSP 1 con una presentazione 3D immersiva ispirata a KSP 2 e una base
scientifica dichiarata. In pratica: scegli un veicolo e un profilo, parti da una
piazzola o da una pista, pilota o programma il GNC, segui telemetria e fasi,
poi recupera il veicolo e progredisci nei percorsi di carriera. Pianeti, lune,
API di controllo, modelli GLB personali e guida didattica completano il ciclo.

La precisione ingegneristica è esplicita: la scena 3D è separata dal propagatore,
le unità sono SI e la libreria dichiara quali modelli sono attivi, approssimati o
ancora da integrare. KSP è un riferimento di design; ASTRA non usa codice o
asset dei giochi.

## Grafica e modelli personali

La scena WebGL 2 gira sul dispositivo e adatta qualità, dettaglio, frequenza
obiettivo e risoluzione delle texture in base alle sue capacità. La Terra usa
Blue Marble NASA fino a 8K sui dispositivi più potenti, con livelli 2K e 1K
per le fasce bilanciata e leggera; il filtro anisotropico mantiene più nitide le
superfici viste a radente quando la GPU lo supporta. Per il sito di Cape
Canaveral la build include due ortofoto USGS NAIP, uno di 120 km e uno di 6 km,
con livelli selezionati in locale in base alla GPU (fino a 4K vicino alla
rampa). Funzionano offline; i vuoti e il bordo dell'ortofoto si fondono
gradualmente con la mappa globale NASA.
Gli ortofoto sono solo grafici e non alimentano la dinamica o il modello
atmosferico. Terra e nuvole usano compositi satellitari NASA Blue Marble sulla
sfera globale; il rendering non sovrappone una seconda mesh locale alla stessa
texture. La volta celeste 360° conserva il mosaico infrarosso 2MASS pubblicato
da NASA, con margini sfumati e nubi diffuse sintetiche, strutturate su più
scale e continue lungo la longitudine per evitare grandi aree apparentemente
vuote. Il campo aggiunto è visivo e non è un dato astronomico. La camera LEO
orienta la scena verso la Terra per mantenere il globo testurizzato nel campo
visivo; l'inquadratura torna libera quando si ruota manualmente. Le
scene atmosferiche aggiungono nubi procedurali, separate dal modello COESA76.
Nell’Explorer, gli altri pianeti e le lune usano mappe procedurali distinte per
corpo, con fasce dei giganti gassosi e superfici craterizzate per i mondi rocciosi.
Sono dettagli grafici illustrativi, non mappe topografiche o dati d’osservazione;
non influiscono su effemeridi, traiettorie o forze.
La scena atmosferica converte uniformemente 10 m in un'unità di scena e segue
il veicolo: la traiettoria NED disegnata deriva dagli stati ricevuti dal motore.
L'aereo parte da 150 m dopo la soglia di una pista visuale da 3.000 × 30 m;
il drone usa una piazzola VTOL dedicata. Il terreno si aggiorna a tasselli
continui lungo la missione, mentre pista, taxiway e hangar restano ancorati
all'aeroporto. Terreno e segnaletica sono grafica, non collisioni né input
alla dinamica; posizione, quota e traiettoria fisiche restano in unità SI.
Le date e le trasformazioni sono indicate
in `ASSET-CREDITS.md`. Se WebGL 2 non è
disponibile, l'interfaccia mantiene comandi e telemetria con una vista Canvas 2D.

Nell'anteprima dei trasferimenti planetari, la posizione propagata è mostrata
con il GLB orbitale già realizzato del veicolo scelto nel catalogo (o con il
modello GLB caricato dall'utente), orientato nella direzione della velocità.
Il veicolo è ingrandito per restare visibile sulla mappa del Sistema Solare;
la sua dimensione grafica non è in scala con i pianeti e non modifica la
traiettoria. Il marcatore luminoso resta un ripiego durante il caricamento o
quando il GLB selezionato non è disponibile.

È possibile importare un modello **GLB 2.0 autonomo** per spazio, aereo o drone.
La categoria selezionata lo mostra nell'ambiente corrispondente. I file vengono
letti nel browser, senza upload. L'importazione è grafica: non cambia masse,
propulsione o aerodinamica del veicolo ASTRA selezionato. Sono supportate mesh
statiche e texture incorporate; vedere i messaggi nell'interfaccia per i limiti
del parser.

## Fisica e limiti

- Veicoli atmosferici: stato locale NED, dinamica a 6 gradi di libertà, gravità,
  polare alare quasi stazionaria parametrica con transizione continua allo stallo,
  incremento della resistenza post-stallo, servi delle superfici di controllo del
  primo ordine con rateo limitato, atmosfera standard COESA76, contatto con la
  pista/suolo, rullaggio e freni, navigazione verticale con filtro di Kalman
  lineare, IMU e barometro sintetici, con quota GNSS sintetica a 1 Hz come
  sorgente verticale di riserva (σ=3 m). Il filtro dichiara la sorgente attiva,
  integrità e età dei fix; in assenza di entrambe le sorgenti propaga l'INS e
  fa crescere la covarianza. Nei profili automatici di planata,
  avvicinamento e atterraggio, il GNC usa la velocità verticale stimata dal
  filtro per regolare il rateo di discesa. Durante il flare mantiene una
  velocità di riferimento almeno pari a `max(1,20·Vstall, Vdecollo)` e toglie
  potenza al contatto, prima del rullaggio frenato. Il controllo di velocità
  proietta lungo la velocità rispetto all'aria gravità, forze aerodinamiche e
  ratei del corpo; converte la spinta richiesta in potenza con l'inversione
  della teoria del disco attuatore usata dal propulsore. La telemetria espone
  rateo stimato positivo verso il basso, sorgente e riferimento di flare. I
  filtri verticali e orizzontali usano l'aggiornamento di covarianza Joseph e
  rigettano le misure con innovazione normalizzata oltre la soglia dichiarata;
  la telemetria riporta conteggio e integrità dei fix respinti. Il sensore resta
  sintetico e deterministico, quindi il gate non equivale a un ricevitore o a
  una validazione avionica reale.
- UAV multirotore: mixer geometrico di spinta e momenti per quadricottero ed
  esacottero, con velocità angolare individuale dei motori e ritardi distinti
  in accelerazione e decelerazione. La telemetria riporta RPM, spinta richiesta
  e prodotta, momenti e saturazione del mixer. Il bilancio energetico in Wh usa
  la spinta rotorica effettiva, non il solo comando collettivo.
  La potenza indotta usa la teoria del disco attuatore in salita/discesa assiale;
  il modello aggiunge figura di merito del rotore, efficienza motore, potenza di
  profilo, avionica e potenza parassita della fusoliera. La telemetria espone
  potenza, energia residua e consumata. Un filtro di Kalman planare combina IMU
  e fix GNSS sintetici a 5 Hz per mantenere posizione, velocità e rientro sulla
  piazzola, più quota GNSS a 1 Hz come backup del barometro. Dopo una perdita
  GNSS, il drone in automatico congela la posizione INS stimata e atterra sul
  posto; la discesa nominale inizia invece dopo aver raggiunto la piazzola. La stima
  di autonomia a potenza corrente è diagnostica, non una previsione della missione.
  La dinamica del rotore è del primo ordine e i parametri elettrici sono valori
  di riferimento; non sono inclusi il modello ESC, la batteria equivalente di
  circuito, le flessioni delle pale o le interazioni aerodinamiche tra rotori.
  La fase angolare di ogni rotore viene integrata nello stesso RK4 dalle
  velocità angolari effettive e viene esposta via API per sincronizzare le pale
  del modello GLB con i motori simulati. Ad alti RPM la vista aggiunge un disco
  di moto sfocato a bassa opacità, così l’aliasing dei fotogrammi non fa sembrare
  ferme le eliche che stanno ruotando.
  La guida orizzontale e verticale usa un LQR continuo a doppio integratore con
  accelerazione limitata a 3 m/s², compensazione del drag e feed-forward di
  gravità; la matrice di Riccati ha soluzione chiusa, senza iterazioni. Il
  controllore d’assetto PD interno segue rollio e beccheggio richiesti.
- Controllo esterno UAV: la modalità `python` applica i comandi ricevuti dal
  software dell'utente e riconosce il touchdown dal moto e dalla velocità
  d'impatto, senza dipendere dal sequenziatore automatico.
- Veicolo spaziale: propagazione ECI con RK4, gravità terrestre e termine J₂;
  rientro con resistenza aerodinamica parametrica e profilo atmosferico COESA76
  fino a 1.000 km.
- L'atmosfera COESA76 usa le equazioni idrostatiche standard fino a 85 km e la
  tabella COESA76 sopra tale quota (passo 5 km fino a 300 km, più largo oltre,
  con interpolazione logaritmica di pressione e densità). È un'atmosfera statica
  di riferimento e non riproduce meteo, ora locale o variazioni solari giornaliere;
  fuori dall’intervallo indicato il modello è marcato come fuori dominio. Lo studio
  variabile del drag orbitale richiede un modello come NRLMSIS. Fonte del
  modello standard: [NASA U.S. Standard Atmosphere 1976](https://ntrs.nasa.gov/api/citations/19770009539/downloads/19770009539.pdf).
- **Campo di raffiche Dryden deterministico**: per aerei e UAV, un seed crea
  una realizzazione a fase casuale dei tre spettri spaziali Dryden longitudinal,
  laterale e verticale; il veicolo attraversa il campo congelato in base alla
  distanza percorsa rispetto all’aria media. Le intensità RMS `sigma_uvw_m_s`
  e le scale integrali `length_uvw_m` sono configurabili e compaiono in
  telemetria insieme a raffica NED, vento medio e distanza nel campo. Il modello
  entra nella velocità relativa all’aria, quindi modifica forze aerodinamiche,
  drag, pressione dinamica, propulsione e risposta GNC. Il campo è riproducibile
  tra esecuzioni e indipendente dal passo RK4; non include gradienti di raffica,
  coerenza spaziale trasversale né l’evoluzione temporale del meteo. Le formule
  spettrali seguono la verifica NASA del modello Dryden:
  [NASA/TM-2019-220143](https://ntrs.nasa.gov/api/citations/20190000875/downloads/20190000875.pdf).
- La polare fissa degli aerei espone α, β, q, CL, CD, CY e margine di stallo
  nella telemetria. Il modello 6-DOF usa anche Cl/Cm/Cn con derivati statici e
  di smorzamento, derivate di comando per alettoni/elevatore/timone e valori Cm0
  configurati per il trim di riferimento del modello. Coefficienti, derivate,
  trim e coefficienti di momento correnti sono esportati nella telemetria. Dopo
  l'angolo di stallo dichiarato dal modello, CL converge verso una curva
  post-stallo smussata e CD cresce quadraticamente. I derivati sono ipotesi
  generiche non calibrate; non si modellano stallo dinamico, isteresi, numero di
  Reynolds, Mach, flap, aerelasticità o mappe sperimentali/certificate.
  Sotto 1 Pa di pressione dinamica la telemetria marca la valutazione di stallo
  come non applicabile e l'interfaccia nasconde gli angoli/polari poco
  significativi a bassa velocità; i valori numerici restano disponibili nello
  snapshot, con lo stato di validità esplicito.
- Aereo: alettoni, elevatore e timone hanno limiti di deflessione, risposta del
  primo ordine e rateo massimo configurati nel catalogo. Deflessioni comandate,
  misurate dal modello e ratei saturati fanno parte dello snapshot completo.
  Non è modellato il collegamento elastico delle superfici alla struttura.
- Pianeti: gli archi di trasferimento integrano la gravità puntiforme Sun+8
  pianeti con RK4 e correggono la condizione terminale entro 100 m; gli elementi
  kepleriani JPL SSD restano approssimati e validi nel periodo indicato
  1800–2050. Le orbite delle lune sono approssimazioni circolari illustrative.
  I budget patched-conic sono impulsivi: non simulano propulsione elettrica,
  guida, navigazione, manovre di correzione o discesa planetaria.
- Aereo e UAV usano PD d’assetto; il rendezvous spacecraft usa quaternion PD, coppia gravitazionale e ruote di reazione, mentre il lancio orbitale combina propagazione traslazionale ECI e assetto quaternion a 3 DOF con TVC/RCS; la guida UAV usa LQR continuo. Non sono
  inclusi MPC, CFD,
  propagazione N-corpi nella missione di lancio LEO o modelli certificati di
  motore e materiali.
- Il modello energetico UAV è a disco attuatore: non risolve le pale, i vortici,
  l'effetto suolo, lo stallo in vortex-ring, le mappe ESC/motore, la temperatura
  o la caduta di tensione della batteria. Le masse e i parametri elettrici dei
  droni sono configurazioni di riferimento ASTRA, da sostituire con dati misurati
  per uno studio quantitativo di un mezzo specifico.

Questi modelli servono per didattica e prototipazione software, non per
progettare, costruire o pilotare veicoli reali. La copertura e i limiti sono
visibili anche nella libreria interattiva.

## Verifica numerica locale

```sh
python3 -m unittest discover -s tests -v
```

I controlli confrontano l'atmosfera con valori COESA76, verificano la continuità
fra strati, l'ordine globale 4 del propagatore RK4 sia nel caso kepleriano sia
con J₂, la chiusura dei trasferimenti, la convergenza del puntamento N-corpi,
la matrice di sensibilità Cowell rispetto a perturbazioni centrate della velocità,
i filtri di Kalman verticale e planare a più passi temporali, i limiti del
Vehicle Lab e il completamento delle missioni con recupero e vento.

## API

- Python: `astra.client.AstraClient`.
- MATLAB: `matlab/+astra/AstraClient.m`.
- Simulink: `matlab/AstraSimulinkSystem.m` tramite blocco MATLAB System.
- API JSON: `/api/v1/openapi.json`, endpoint `state`, `status`, `models`, `vehicle-parts`,
  `celestial`, `transfer`, `convergence`, `robustness`, `fault`, `fault/clear`,
  `engineering`, `reset`, `launch`, `command`, `step` e `stage`.
  Il reset accetta `scenario="leo-return"` con uno stack custom da almeno
  9,2 km/s di Δv ideale e T/W 1,1 su ogni stadio; le manovre di inserzione e
  deorbita devono inoltre restare entro la riserva effettiva dello stack.

I client Python e MATLAB espongono stato, cataloghi, comando e `heartbeat()` per
rinnovare la modalità programmatica senza modificare gli attuatori, oltre a reset,
lancio e passo. Entrambi consentono trasferimenti, effemeridi, campagne di
robustezza e studi di convergenza; MATLAB usa `sim.transferState("mars", 86400)`,
`sim.convergence(struct("vehicle","aircraft","horizon_s",30,"levels",3))` e
`sim.robustness(struct("vehicle","drone","samples",4,"seed",417))`.
Python usa `sim.inject_fault("engine_thrust_loss", 0.3)`,
`sim.inject_fault("gnss_dropout")` e `sim.clear_faults()`; MATLAB espone
`sim.injectFault("rotor_thrust_loss", 0.4, 1)` per il rotore con indice zero-based 1
e `sim.clearFaults()`. Il System block Simulink offre gli stessi metodi durante
l'esecuzione.
Lo studio usa lo stesso profilo a passi dimezzati, su motori separati dalla missione aperta.
Python usa timeout configurabili (15 s predefiniti) e MATLAB timeout da 10 s
per il controllo ordinario. Trasferimenti e studi isolati usano 300 s in entrambi
i client. Gli errori HTTP Python diventano `AstraAPIError` con codice e messaggio del server. Per gli
aerei e gli UAV il reset può impostare un vento costante
locale NED, ad esempio `sim.reset("aircraft", wind_ned_m_s=[-8, 0, 0])` per
un vento da Nord che soffia verso Sud, oppure un profilo verticale assoluto:

```python
wind_profile = [
    {"altitude_m": 0, "velocity_ned_m_s": [0, 0, 0]},
    {"altitude_m": 1000, "velocity_ned_m_s": [0, 4, 0]},
    {"altitude_m": 3000, "velocity_ned_m_s": [0, 8, 0]},
]
sim.reset("aircraft", wind_profile_ned_m_s=wind_profile)
```

Il profilo usa quota geometrica, componenti Nord/Est/Giù in m/s, interpolazione
lineare e valori costanti oltre i nodi estremi. Accetta da 2 a 16 nodi tra 0 e
84.852 km; ogni vettore resta entro l’inviluppo di 60 m/s per gli aerei o 16 m/s
per gli UAV. Il vento uniforme e quello a profilo sono alternativi. La
telemetria fornisce il profilo caricato, il modello d’interpolazione, il vento
locale alla quota corrente e l’indicatore di saturazione ai bordi. L’interfaccia
offre il preset «Taglio verticale · 0–12 m/s»; profili personalizzati si impostano
tramite HTTP, Python, MATLAB o Simulink. È un campo statico prescritto,
uniforme orizzontalmente: non è una previsione meteorologica. La campagna
Monte Carlo applica uno scostamento orizzontale comune a tutte le quote, poi
proietta ogni vettore fuori inviluppo sul limite ammesso con un margine numerico
minimo. La proiezione scala tutte le componenti del nodo, compresa quella
verticale: gli scostamenti effettivi possono quindi differire tra le quote.
Ogni prova esporta il profilo realizzato e la regola di limitazione.

La telemetria separa velocità al suolo, velocità vera e pressione dinamica,
ed espone la velocità relativa all'aria sia in NED sia nel frame corpo;
aerodinamica, guida e potenza parassita del drone usano la stessa velocità,
incluse le raffiche Dryden. L'autopilota aereo applica anche un angolo di crab per
compensare il vento laterale nel circuito northbound. Il vettore è limitato a
60 m/s per gli aerei e 16 m/s per i droni; i venti non si applicano ai
veicoli spaziali. Gli stessi preset sono
selezionabili nell'interfaccia. `AstraClient` MATLAB accetta il vettore nel
parametro `windNED` di `reset`, seguito da `turbulence` e `windProfileNED`;
il blocco Simulink espone le proprietà `WindNED`, `Turbulence` e `WindProfileNED`.
La turbolenza è opzionale e, per compatibilità, disattivata per default:

```python
dryden = {"model": "dryden", "seed": 417,
          "sigma_uvw_m_s": [1.2, 0.8, 0.5],
          "length_uvw_m": [140, 90, 45]}
sim.reset("aircraft", model_id="corvo-t2",
          wind_ned_m_s=[-5, 1, 0], turbulence=dryden)
campaign = sim.robustness(vehicle="aircraft", model_id="corvo-t2",
                          samples=8, seed=417,
                          baseline_turbulence=dryden)
```

I componenti `u/v/w` sono riferiti agli assi longitudinali/trasversali/verticali;
il vento orizzontale viene proiettato nel frame NED usando la direzione dell’aria
media. Le scale sono comprese tra 0,1 m e 100 km; ciascuna intensità RMS fra 0 e
30 m/s, con norma RMS massima di 16 m/s per i droni. La campagna Monte Carlo
mantiene identico il campo per isolare le incertezze di veicolo rispetto al
rumore ambientale. MATLAB usa il settimo argomento `turbulence` di `reset` e
Simulink offre la proprietà `Turbulence`.
Nell’interfaccia, il pannello VENTO permette di selezionare le tre intensità
dimostrative ASTRA o di impostare seed, RMS e scale spaziali prima di avviare la
missione; l’intensità istantanea della raffica compare nella telemetria.

Per vedere un controllore esterno completo in azione, avvia ASTRA
in un terminale e poi esegui dalla cartella del progetto:

```sh
python3 examples/python_uav_autopilot.py
python3 examples/python_orbital_attitude.py
```

Entrambi gli esempi accettano `--base-url http://host:porta` o la variabile
`ASTRA_BASE_URL`. Il controller orbitale usa la modalità `python` e rinnova il
link ogni 0,5 s simulati.

L'esempio usa le stime verticale e orizzontale per controllare quota, posizione
N/E e assetto, compensa il vento laterale a 6 m/s, poi torna alla piazzola e
atterra tramite l'API locale.
Per gli aerei, `sim.command(brakes_pct=75)` applica la frenata ruote durante il
rullaggio; la telemetria restituisce il comando attivo in `state["command"]`.

  `AstraClient.transfer("mars", "2026-10-22T00:00:00Z")` restituisce date di
  partenza/arrivo, Δv, residuo di convergenza Lambert e 49 punti dell'arco
  eliocentrico. `AstraClient.transfer_state("mars", elapsed_s, date)` restituisce
  la posizione e la velocità propagate al tempo trascorso, con frame e corpo
  centrale espliciti. La tratta Luna viene propagata geocentricamente e combinata
  con l'epemeride terrestre per la posizione eliocentrica.

Il file `matlab/README.md` descrive l'uso di MATLAB e Simulink.

## Licenza

Il codice è distribuito con licenza MIT: vedere [LICENSE](LICENSE). Le texture
NASA hanno crediti e sorgenti documentati separatamente; vedere
[ASSET-CREDITS.md](ASSET-CREDITS.md). Questa distinzione è consultabile anche
dal pannello informazioni dell'interfaccia. Per rigenerare le varianti WebP
servono facoltativamente Pillow e NumPy; non sono dipendenze dell'app.


## ASTRA 1.1 cockpit update

- The **Play** mode exposes two large, drag- and touch-enabled flight joysticks, with keyboard/gamepad controls; it selects manual flight control when entering Play.
- The **Show/Hide Data** control collapses telemetry and other technical chrome while keeping flight controls accessible. Display preferences persist locally.
- UI language is detected from browser preferences (English fallback) and can be overridden with the top bar language selector. The main cockpit captions support English, Italian, Spanish, French, German and Portuguese; some deep engineering explanations remain in Italian pending complete internationalisation.
- PDF API references in English: `docs/ASTRA_1.1_Python_API_Manual_EN.pdf` and `docs/ASTRA_1.1_MATLAB_Simulink_API_Manual_EN.pdf`.

For the most reliable gamepad response, use 1x simulation time and a modern WebGL 2 browser. Large-time-warp values are intended for mission propagation, not manual aerobatic control.


## ASTRA 1.2.4: engineering expansion and terrain visibility

Engineering Studio now supports `robotics_route` (deterministic eight-connected A* occupancy-grid planning with no corner cutting) and `planetary_descent` (one-dimensional RK4 variable-mass powered landing with gravity, drag and throttle guidance). Both are independent, parameterized scientific exercises accessed via `POST /api/v1/engineering`; they do **not** steer the active 3-D vehicle. The Engineering Studio Compute action no longer calls `reportValidity()` on a non-form div.

Aircraft rendering uses a 3×3 grid of terrain chunks with eight lower-LOD neighbours surrounding the main tile, plus a longer far clipping range. This improves terrain visibility in flight at altitude. Chunk geometry is approximate with no georeferenced imagery, buildings, collision geometry, or DEM.

ASTRA remains a research/educational prototype. The remaining abbreviated disciplines (thermal, propulsion, aerodynamics, planetary ephemerides, structures, systems engineering, etc.) have declared limits and are **not** magically made full fidelity by this release.


## ASTRA 1.3 · Engineering model expansion

Six independent, SI-unit analyses have been added: rocket turbomachinery power
balance, Prandtl lifting-line aerodynamics, configurable Lambert boundary-value
solver, Earth-conical-umbra electrical sizing and radio BER/pointing/losses, and quaternion rigid-body planetary powered landing.
Mission-linked requirement verification is available at
`POST /api/v1/requirements/verify`; inspect the Engineering Studio interface or
`ENGINEERING-STUDIO.md`. The models do **not** make the entire spacecraft, aircraft,
or UAV simulation high-fidelity or certify it for real-world use.
