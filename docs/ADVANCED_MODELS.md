# ASTRA 1.5 — Advanced live science

All thirteen previously parametric disciplines now have runtime integration. `science.disciplines` reports applicability, coupling, SI values, time and limitations. Active means implemented, not experimentally validated.

Enable with `/reset`: `{"vehicle":"space","scenario":"orbital","advanced_models":true}`. The UI defaults to advanced; uncheck **Modelli avanzati nel motore** before launch to compare the legacy path. Lunar descent uses `scenario:"planetary"`.

## Runtime contracts

### propulsion

Ugello Laval con urto normale, pressione di camera transitoria e calibrazione F/Isp: spinta e portata alimentano RK4 e bilancio del propellente. Attuatori a elica/rotore e RCS finiti restano operativi.

Gas perfetto congelato, geometria di riferimento e risposta del primo ordine; nessuna chimica reagente, identificazione motore o separazione viscosa.

### aerodynamics

Ritardo convettivo della portanza nella dinamica 6-DoF, polare non lineare di stallo e incremento empirico della resistenza comprimibile; forze calcolate nella stessa traiettoria.

Coefficienti generici, correzione transonica limitata, nessuna CFD, identificazione sperimentale o aeroelasticità completa.

### celestial-mechanics

Perturbazioni differenziali di Sole, Luna e sette pianeti nelle propagazioni ECI del veicolo e del bersaglio. Epoca UTC configurabile e interpolazione delle effemeridi.

Elementi planetari approssimati JPL e Luna kepleriana media: non DE/SPICE né integrazione mutua completa del sistema solare.

### mission-design

Riferimento cubico a energia di controllo minima per avvicinamento a durata finita; posizione, velocità e accelerazione di riferimento alimentano realmente la guida RCS.

Il riferimento non include i vincoli nella soluzione ottima: saturazione gestita dal controllore, nessuna ottimalità globale vincolata.

### rendezvous

Guida relativa con differenza non lineare della gravità J2 e dei terzi corpi, trasporto RTN, inseguimento della traiettoria e manovra di fuga dalla sfera di esclusione.

Filtro relativo CW mantenuto; velocità del riferimento RTN osculante, RCS continuo equivalente, nessun docking/contact o certificazione della sicurezza.

### structures

Primo modo della trave FEM Hermite con massa consistente, risposta dinamica Newmark, smorzamento, energia, tensione alla radice e verifica temporale del limite elastico durante il volo.

Monitor di un membro strutturale di riferimento configurabile; nessuna pretesa di FEM dell’intero veicolo, flutter, slosh o plasticità.

### atmosphere

COESA76, strato superficiale e campo spaziale deterministico a spettro von Karman opzionale, con forze dipendenti dalla velocità rispetto all’aria.

Spettro finito monodimensionale e atmosfera standard, non meteo reale. RMS configurabile; Dryden precedente disponibile quando il campo avanzato è disattivato.

### power

EPS con penombra da sovrapposizione dei dischi apparenti, incidenza dei pannelli dall’assetto, efficienza carica/scarica, bilancio delle perdite e disponibilità reale degli attuatori.

Bus di riferimento, salvo batteria UAV già fisica; niente invecchiamento elettrochimico o cablaggio dettagliato. Il Sole delle effemeridi è usato per la generazione.

### communications

Friis/BPSK, perdita di puntamento, probabilità di pacchetto e coda deterministica con serializzazione e tempo luce. Canale RF opzionale applica ritardi e perdite ai comandi Python.

RF simulata, non rete Internet; niente multipath, codifica o fading atmosferico. I controlli locali restano diretti.

### robotics

A* con ostacoli gonfiati per ingombro e raggio di cella, divieto di taglio degli angoli e rotta applicata al GNC UAV; distanza dagli ostacoli monitorata durante il volo.

Mappa sintetica 2D nota; niente SLAM, percezione, ostacoli dinamici o garanzia di separazione sotto disturbi e rientri di emergenza.

### launch-systems

Centro di massa e inerzia da guscio e riempimento del propellente alimentano TVC/RCS; limitazione automatica max-q, eventi di staging e masse finite nel motore.

Geometria di riferimento, niente slosh, deformazioni dei serbatoi o momenti aerodinamici identificati.

### planetary-landing

Missione lunare attiva selezionabile: 6-DoF quaternion, gravità variabile, inerzia dipendente dalla massa, ritardo motore, filtro Kalman radar/Doppler rumoroso e contatto localizzato con propellente finito.

Piazzola fisica piana, terreno visivo sintetico esterno; niente DEM, gambe elastiche, interazione plume-suolo o guida ottima.

### systems-engineering

Requisiti temporali tipizzati SI a ogni passo con finestre di copertura, minimi/massimi, primo fallimento persistente, seed, versione dei modelli e hash della configurazione.

Verifica campionata: PASS_SO_FAR non dimostra gli intervalli fra campioni e non costituisce certificazione o prova formale.

## Reproducibility and validation

Pure state reads; deterministic epoch and seeds; SHA-256 configuration identity; units validated for temporal requirements. The standard engine path retains prior API defaults. `tools/test_advanced_mission.py` checks analytical limits, energy/mass ledgers, orbital convergence to the hold point and live lunar landing. GPU evidence is in `test-results/advanced-browser.json`; hardware controller behavior and hardware FPS are not inferred from software-rendered tests.

## Renderer

Scene-linear HDR RGBA16F where EXT_color_buffer_float is supported, RGBA8 fallback, 1k/2k/4k geometry shadow maps with PCF, quarter-resolution bloom, depth ambient occlusion, FXAA and one final filmic/sRGB transform. Earth atmosphere uses view/sun optical-depth integration; cloud coverage and lunar terrain are synthetic visual assets, not observed weather or a DEM. Mesh density uses smaller spheres for rocks and ground details. Matrices retain double precision on the CPU before WebGL upload. Quality presets change actual GPU work; no Star Citizen parity, ray tracing or sustained hardware FPS is claimed.

## References

- NASA Glenn, [rocket thrust](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-thrust-equation/).
- JPL Solar System Dynamics, [approximate planetary positions](https://ssd.jpl.nasa.gov/planets/approx_pos.html).
- UC Berkeley OpenSees, [Newmark method](https://opensees.berkeley.edu/wiki/index.php/Newmark_Method).
