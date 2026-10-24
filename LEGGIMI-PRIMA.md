# ASTRA Browser 1.3.3 — Fix Pyodide 314

## Difetto identificato
Pyodide 314 ha rimosso il supporto ai Web Worker classici; ASTRA utilizzava
`new Worker(..., {type:'classic'})` e `importScripts()`. La build statica
passava i test GitHub Actions ma il motore WebAssembly non si inizializzava.

## File da sostituire nel repository (mantieni i percorsi!)
- `/browser-api.js`
- `/browser-engine-worker.js`
- `/service-worker.js`
- `/index.html`
- `/tools/prepare_pyodide.py`
- `/tools/test_browser_distribution.py`
- `/diagnostics.html` (nuovo)

## Procedura consigliata su Ubuntu
Scompatta questo ZIP dentro la radice del repository locale ASTRA e avvia:

```bash
git add browser-api.js browser-engine-worker.js service-worker.js index.html diagnostics.html tools/prepare_pyodide.py tools/test_browser_distribution.py
git commit -m "Fix Pyodide 314 module worker and browser startup"
git push origin main
```

Nella scheda Actions attendi l'esito verde del workflow. Apri
`https://eleman07.github.io/ASTRA---Aerospace-Simulator/diagnostics.html`,
seleziona "Svuota cache ASTRA precedente" e ricarica ASTRA. Poi usa la pagina
per verificare l'inizializzazione del motore.

## Controllo richiesto in CI
`tools/prepare_pyodide.py` deve scaricare anche `pyodide.mjs` e includerlo
nell'artifact Pages. `node --check` da solo non può verificare WebAssembly.

## Validazione di questa patch
- Test Python originali: 10 superati.
- Sintassi JS worker, API e service worker: controllata.
- Modalità ES module coerente con le note ufficiali di Pyodide 314.
- L'avvio WebAssembly completo in un browser reale non è stato convalidato
  in questo ambiente: usare `diagnostics.html` dopo il deploy.
