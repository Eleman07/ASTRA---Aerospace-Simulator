# ASTRA — proposta locale da approvare

Base GitHub: `Eleman07/ASTRA-Aerospace-Simulator`, ramo `main`, commit
`8b69cbba5bbfd0a5fc7e78ead9dea0a6c9f6a5ab` (copia del 26 ottobre 2026).
Nessun push, commit remoto, branch remoto o pull request è stato creato.
La versione pubblica resta 1.4.1; questa è una proposta di modifica, cache locale build 292.

## Cosa cambia

**Grafica.** Il renderer WebGL2 usa un BRDF metallic/roughness GGX con Fresnel
Schlick, luce diretta, ambiente analitico, calcoli in spazio lineare e tone mapping.
Legge dal GLB metallicFactor, roughnessFactor, texture metallic/roughness ed
emissiveFactor. Terra con riflesso oceanico approssimato, foschia in funzione della
distanza, bordo atmosferico, panorama stellare solidale alla camera. La ISS passa
dalla vecchia scala arbitraria (circa 190 km nella scena) a un ingombro nominale
109 m coerente con la scala terrestre. Non sono implementati ray tracing, ombre
tra tutte le mesh, normal mapping, texture emissive o simulazione meteorologica.

**Interfaccia.** Quattro pannelli Missione / Dati / GNC / Modelli, telemetria
essenziale sempre visibile, grafico di quota, modalità Vista libera, dettagli e
importazione GLB richiudibili, timeline a richiesta. Mantiene gli ID e i controlli
esistenti. I tab supportano frecce, Home/End e focus da tastiera. Non aggiunge
framework, dipendenze runtime, font remoti o servizi esterni.

**Modelli.** Nuovi sottosistemi calcolati a ogni sottopasso fisico, con timestamp e
parametri esportati nella telemetria `live_systems`:

- Strutture: trave a sbalzo di riferimento, carico uniforme dalla pressione dinamica,
  momento, tensione, freccia e margine elastico. Geometria e materiale configurabili.
- Termica: temperatura di un pannello a capacità concentrata; integrazione implicita
  del bilancio radiativo. Sutton–Graves del motore fornisce l'ingresso in rientro.
- Energia: generazione solare, eclisse geometrica, consumo e SoC del bus di riferimento.
  Per il drone si usa la batteria del motore esistente, senza consumarla due volte.
- Comunicazioni: distanza e visibilità dalla stazione iniziale, Friis, Eb/N₀,
  BER BPSK, margine e ritardo. Per i veicoli ECI la stazione ruota con la Terra.
- Verifica: controlli continui sulle soglie dei quattro sottosistemi.
- Robotica: la rotta A* si applica realmente al GNC LQR UAV. Il drone segue i waypoint
  a 30 m, torna lungo il percorso inverso, rientra sulla piazzola e atterra.
  La rotta di riferimento e la traiettoria percorsa sono distinte nel 3D.

I quattro sottosistemi sono **osservatori collegati alla missione**, non un
accoppiamento bidirezionale: non deformano la mesh, non cambiano le forze, non
spengono gli attuatori e non interrompono l'API radio. La rotta UAV, invece,
modifica i comandi di guida e quindi il moto. Le etichette restano oneste:
“parametrico” non viene sostituito artificialmente da “validato”.

## Copertura delle 13 schede «MODELLO PARAMETRICO»

| Scheda | Collegamento effettivo nella proposta | Limite conservato |
|---|---|---|
| Propulsione | Spinta, portata, ugello e rotori già nel motore | Ciclo a generatore di gas resta analisi separata |
| Aerodinamica | Polare, derivate e correzione comprimibile già nel motore | Lifting-line separata; nessuna CFD |
| Effemeridi | Catalogo e trasferimenti già eseguibili | Nessuna sostituzione con SPICE |
| Traiettorie | Lambert e Cowell già eseguibili nel laboratorio/navigatore | Non comandano nuove missioni interplanetarie |
| Rendezvous | Guida e dinamica già nel motore; geometria ISS corretta | Nessun docking/contact model |
| Strutture | **Nuovo osservatore continuo**, q → trave | Nessun feedback aeroelastico né FEM 3D |
| Atmosfera | COESA76, Dryden, vento e surface layer già nel motore | Nessun meteo reale |
| Energia | **Nuovo bus continuo**, eclisse; batteria UAV effettiva | Bus di riferimento senza feedback al GNC |
| Comunicazioni | **Nuovo budget continuo** sulla geometria di volo | Nessuna perdita comandi simulata |
| Robotica | **Nuovo A* → GNC → volo 3D → atterraggio** | Mappa sintetica, nessuna garanzia anticollisione |
| Lanciatori | Stadi, masse e propulsione già nel motore | Nessuna nuova turbomacchina/slosh |
| Atterraggi planetari | Solver 6-DOF esistente, verificato nella suite dei solutori | Resta un laboratorio; non aggiunta una missione planetaria giocabile |
| Sistemi e requisiti | **Nuove soglie continue** più predicati esistenti | Non è verifica formale o certificazione |

Questa consegna non trasforma tutte le discipline in nuovi sistemi accoppiati
ad alta fedeltà: le righe che restano studi separati sono esplicite sopra.

## Provala localmente

Apri la cartella della copia di lavoro e usa il server statico per la Browser Edition:

```bash
python3 tools/prepare_pyodide.py
python3 -m http.server 8842 --bind 127.0.0.1
```

Apri `http://127.0.0.1:8842`. Il runtime è già preparato nella copia consegnata.
`server.py` è invece il viewer dell'API Python esterna: il suo polling non avanza
il tempo e quindi non è il server da usare per questa prova con il tasto Play.

1. Apri **Modelli**, espandi i parametri e applicali prima del lancio.
2. Avvia, osserva i risultati, metti in pausa: letture e grafica non devono
   consumare energia o avanzare il tempo da sole.
3. Per la rotta: seleziona **Drone**, apri Engineering Studio → Robotica UAV,
   calcola A*, premi **Applica rotta al drone**, chiudi il laboratorio e avvia.
   Per una prova breve: griglia 8×8, cella 1 m, densità 0, seed 42.
4. Esporta Mission Data Lab: i dati includono configurazione, monitor e rotta.
5. Reset ripristina i parametri di riferimento e rimuove la rotta applicata.

## API nuove

`POST /systems/configure` nel Worker (oppure `/api/v1/systems/configure` via server
Python) accetta gli override dei parametri di `astra/live_systems.py`, soltanto
prima del lancio. Validazione di tipo, finitezza, limiti e nomi sconosciuti.

`POST /mission/route` accetta gli stessi parametri del solver `robotics_route`;
ricalcola il percorso sul backend, richiede UAV pronto, rotta trovata, massimo
512 waypoint e raggio 500 m. Non accetta risultati pianificati dal client come
verità. Il motore applica lo stesso controllo LQR già usato per la missione.

## Verifiche

Comandi riproducibili:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p 'test_*.py' -v
node tools/test_materials.mjs
npm install --prefix /tmp/astra-qa playwright
NODE_PATH=/tmp/astra-qa/node_modules node tools/test_workspace_browser.cjs
```

- Suite Python: **48 test superati**, compresi i 18 nuovi test numerici/integrazione.
- GLB: quattro asset reali, conservazione fattori PBR e rifiuto riferimenti texture errati.
- Browser reale: Chrome, WebGL2 via SwiftShader, Worker Pyodide, start/pausa,
  configurazione dal form, tab, vista libera, rotta A* applicata dall'interfaccia,
  atterraggio, catalogo, viewport 390 px; nessun errore JS/WebGL nei controlli.
- Le prove software non sono un benchmark FPS su GPU fisica né test Safari/iOS.
- Nessun test di accuratezza rispetto a dati di volo certificati è dichiarato.

I log e le schermate effettive sono nella cartella di consegna, fuori dal codice.

## Applicazione a GitHub, soltanto dopo approvazione

La patch è ancorata al commit indicato in apertura. Prima di applicarla a una
copia aggiornata verificare `git apply --check ASTRA-proposta.patch`. L'archivio
aggiornamento contiene i file nuovi/modificati con i percorsi del repository.
Il runtime Pyodide non va committato: il workflow GitHub Pages esistente lo prepara.
La cache PWA passa a v292 e include entrambi i nuovi moduli JavaScript e Python.

Titolo suggerito: `Improve WebGL materials and flight workspace; integrate live systems and UAV routes`.
