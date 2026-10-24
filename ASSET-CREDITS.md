# Crediti e licenze degli asset

Il codice ASTRA è distribuito con licenza MIT; le texture hanno provenienza e
crediti separati. Le texture NASA qui elencate sono materiale NASA riutilizzabile
secondo le rispettive pagine sorgente. ASTRA non è affiliato né approvato dalla
NASA.

## Terra

- Superficie: NASA Earth Observatory, *Blue Marble: Next Generation*, mappa
  globale di luglio 2004, sorgente 21600×10800 px (2 km/pixel). Il file è
  conservato in `assets/source/earth-blue-marble-july-2004-21.6k.jpg`; la pagina
  NASA chiede di citare “NASA Earth Observatory”. [Pagina NASA](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/),
  [JPEG originale](https://assets.science.nasa.gov/content/dam/science/esd/eo/images/bmng/bmng-base/july/world.200407.3x21600x10800.jpg).
- ASTRA compone la superficie con la mappa delle nuvole e serve livelli WebP
  fino a 8192×4096 sui dispositivi compatibili; profili più leggeri usano le
  versioni 2048×1024 o 1024×512 e il limite massimo supportato dalla GPU.
- Nuvole: NASA Goddard Space Flight Center, *Blue Marble: Clouds*, file
  `cloud_combined_2048.jpg`; immagine di Reto Stöckli, composta da osservazioni
  satellitari MODIS visibili e infrarosse. [Scheda NASA](https://visibleearth.nasa.gov/images/57747/blue-marble-clouds/77558l),
  [file NASA](https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57747/cloud_combined_2048.jpg).
- La superficie e le nuvole sono compositi di anni differenti e restano una
  visualizzazione statica: non rappresentano il meteo attuale e non alimentano
  la fisica atmosferica.
- Per la rampa a Cape Canaveral, ASTRA include due ortofoto georeferenziati
  USGS/USDA NAIP: assets/source/usgs-naip-cape-canaveral-wide-120km.jpg copre
  circa 120 km e assets/source/usgs-naip-cape-canaveral-near-6km.jpg copre
  6 km. I WebP derivati sono inclusi in assets/ con livelli per GPU; il livello
  ravvicinato arriva a 4000×4000 px. Il servizio descrive la copertura NAIP
  come prevalentemente 0,6 m per pixel. Dato pubblico: il materiale USGS/USDA
  è in pubblico dominio. Le zone senza dati e i siti fuori dal ritaglio mostrano
  la mappa NASA sottostante.
  [Descrizione e servizio USGS](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer),
  [licenza e descrizione NAIP](https://www.usgs.gov/media/images/tnmcorps-naip-imagery-layer).

## Via Lattea

- Mosaico infrarosso 2MASS, `2mass_orig_aspect.png`, pubblicato da NASA Goddard
  Space Flight Center. I dati 2MASS sono del progetto congiunto University of
  Massachusetts Amherst e IPAC/Caltech. [Scheda, descrizione e crediti NASA](https://svs.gsfc.nasa.gov/30020/),
  [file NASA](https://svs.gsfc.nasa.gov/vis/a030000/a030000/a030020/2mass_orig_aspect.png).
- Il motore conserva la banda infrarossa della Via Lattea, ne sfuma i margini
  nel cielo e aggiunge un campo di polveri tenue, deterministico e generato
  proceduralmente sull'intera volta, oltre a stelle puntiformi. Il campo
  sintetico completa la copertura visiva ma non rappresenta misure astronomiche;
  i colori del mosaico centrale sono quelli della visualizzazione 2MASS, non una
  fotografia in luce visibile.

## Altri pianeti e lune

Le mappe visive di pianeti e lune diverse dalla Terra sono generate localmente
con palette e strutture procedurali specifiche per corpo (fasce dei giganti,
ghiacci, nubi e crateri). Sono illustrazioni, non mappe scientifiche o dati di
altitudine. Non alimentano le effemeridi né la dinamica di volo.

## File e trasformazioni

Le sorgenti originali sono conservate in `assets/source/`. Lo script
`tools/build_visual_assets.py` produce le texture WebP con conversione e
ricampionamento: Terra 1K/2K/4K/5.4K e Via Lattea 1K/2K/4K; non cambia la
fisica. La generazione facoltativa richiede
Pillow e NumPy. L'app a runtime non ha dipendenze Python esterne.

I crediti ai dati astronomici sono in [README.md](README.md); le orbite
planetarie usano gli elementi approssimati JPL descritti in
`astra/celestial.py`.


## Rampa di lancio

- Mobile Launcher per il programma Artemis: modello 3D pre-realizzato della
  NASA, attribuito dalla scheda ufficiale a NASA/Samuel H. Neblett. ASTRA usa
  il GLB assemblato locale. La sorgente Draco originale è conservata in
  `assets/source/vehicles/nasa-mobile-launcher-assembled-source.glb`; il GLB
  servito da ASTRA è stato decodificato ed esportato senza Draco con Blender,
  preservando mesh e materiali. Resta un modello pre-realizzato, orientato
  sull’asse verticale originale e appoggiato al piano di lancio; non è una rampa
  costruita con primitive ASTRA. Consultare
  le [NASA Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
  per il riuso e l’attribuzione. [Scheda e download del modello NASA](https://science.nasa.gov/3d-resources/mobile-launcher/).

## Modelli 3D dei veicoli

Il catalogo include modelli 3D già realizzati e distribuiti con l'app. ASTRA li
carica solo quando selezionati, li mette nella cache del browser e seleziona il
livello di dettaglio in base al dispositivo. I modelli sono visuali: massa,
propulsione, aerodinamica, batteria, controlli e traiettoria restano del profilo
fisico ASTRA selezionato. Non sono CAD certificati e non implicano affiliazione
né approvazione NASA.

- Space Launch System (SLS) Block 1 con Orion: il modello completo usato al
  lancio proviene dal file STL ufficiale NASA 3D Resources, conservato in
  `assets/source/vehicles/sls-block1-official-nasa.stl`. I dispositivi leggeri
  usano una copia da 64 mila triangoli; quelli ad alte prestazioni caricano la
  geometria completa NASA, circa 274 mila triangoli, senza decimazione. Entrambe
  le copie ricevono materiali PBR illustrativi neutri ai booster e allo stadio
  superiore, arancione al core stage, scuri agli ugelli e chiari a Orion. Non
  genera parti geometriche. Le varianti di stadio superiore e di veicolo
  orbitale restano derivate dall'archivio Blender NASA conservato in
  `assets/source/vehicles/sls-block1-nasa.7z`; al rientro viene usata la
  capsula Orion NASA. [Scheda e modello NASA SLS](https://science.nasa.gov/3d-resources/space-launch-system-sls-block-1/),
  [modello Orion](https://science.nasa.gov/3d-resources/orion-capsule/).
  La NASA dichiara le risorse gratuite da scaricare e usare secondo le proprie
  [Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/).
- Crew Dragon 2 con trunk: modello 3D di KUBAHA, distribuito con licenza
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). ASTRA include
  attribuzione e sorgente; il file visuale per il rientro omette il trunk e i
  pannelli solari separabili mantenendo la geometria originale della capsula.
  [Pagina del modello](https://sketchfab.com/3d-models/spacex-dragon-2-1b125e30a2cb442288580290536fbe5d).
- Falcon 9 Block 5: modello 3D di Fac-tory-o da
  [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Falcon_9.stl),
  rilasciato con licenza
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). La sorgente
  STL è conservata in `assets/source/vehicles/Falcon_9.stl`; ASTRA estrae lo
  stack assemblato e assegna finiture illustrative. I dispositivi leggeri
  usano una copia da circa 47 mila triangoli; quelli ad alte prestazioni
  caricano l'intero stack assemblato, circa 556 mila triangoli, senza
  decimazione (`tools/prepare_falcon9_glb.py` e
  `tools/prepare_falcon9_high_glb.py`). Ogni mesh derivata resta soggetta alla
  stessa licenza e all'attribuzione dell'autore.
  ASTRA mostra lo stack completo al lancio, Dragon 2 con trunk in orbita e la
  sola capsula al rientro; geometria e finiture non sono CAD certificati.
- La capsula Orion NASA proviene dalla mesh STL ufficiale (modello “no fbc”);
  ASTRA converte il solido in GLB e aggiunge finiture illustrative neutre,
  senza cambiare la geometria sorgente. Le finiture non sono dati ottici NASA.
- Aereo X-57 Maxwell: modello della raccolta NASA, dimostratore sperimentale a
  propulsione elettrica. [Scheda NASA](https://science.nasa.gov/3d-resources/x-57-maxwell/).
- Aereo monomotore a elica Innerscene: modello GLB pre-realizzato con licenza
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). La sorgente
  originale è conservata in `assets/source/vehicles/innerscene-single-engine-propeller-aircraft.glb`
  e la copia runtime ottimizzata in `assets/vehicles/innerscene-propeller-aircraft.glb`
  mantiene 59.988 triangoli; le due pale restano mesh separate per l'animazione.
  I dispositivi ad alte prestazioni caricano la sorgente completa (circa 144
  mila triangoli). [Scheda e dettagli del modello](https://www.innerscene.com/tools/library/3d-parts/single-engine-propeller-aircraft-d6091ef1).
- Quadricottero X-frame con elettronica di volo: modello originale Innerscene,
  scala nominale e licenza [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
  [Scheda, dettagli tecnici e download](https://www.innerscene.com/tools/library/3d-parts/quadcopter-with-flight-electronics-a25968c1).

## Stazione orbitale

- International Space Station (ISS) (B): GLB NASA pre-realizzato da
  NASA/Michael D. Carbajal, caricato come bersaglio visivo nel rendezvous LEO.
  ASTRA non ricostruisce la stazione con primitive. La geometria originale è
  distribuita in `assets/vehicles/nasa-iss-b.glb`; la copia sorgente è in
  `assets/source/vehicles/nasa-iss-b.glb`. L'asset runtime è convertito dal GLB
  Draco e decimato a circa 45 mila triangoli con lo script Blender
  `tools/convert_glb_without_draco.py`, per caricarlo anche sul profilo grafico
  leggero. La scala in scena è solo di presentazione; dinamica e telemetria
  restano in SI. Consultare la scheda NASA e le
  [NASA Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
  per l'attribuzione. [Scheda e download ufficiale](https://science.nasa.gov/3d-resources/international-space-station-iss-b/).

I file sorgente e le note di licenza sono conservati in
`assets/source/vehicles/`; ASTRA esporta modelli GLB autonomi senza
compressione Draco per il decoder locale. Il profilo del dispositivo seleziona
mesh complete dove disponibili e copie ottimizzate sui dispositivi con risorse
limitate. Tutti i modelli sono visuali: non corrispondono a CAD certificati e
non forniscono parametri di massa, propulsione o aerodinamica del veicolo reale.
La grafica di ASTRA cambia modello tra lanciatore e capsula di rientro, ma gli
eventi e i parametri di volo sono quelli del profilo fisico ASTRA selezionato.
Nessun modello implica affiliazione o approvazione NASA, SpaceX o degli autori.


## Additional local reference
- `assets/source/user-nebula-reference.jpg` — user-provided nebula image integrated as the ASTRA 1.2.2 space background source.
