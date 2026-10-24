# Come installare il README e il test API su GitHub

Questa patch NON sostituisce il simulatore e non modifica il motore fisico. Aggiunge al repository:

- `README.md`: nuova presentazione inglese con tutorial illustrato
- `docs/images/*`: immagini reali annotate + diagrammi dichiarati come tali
- `docs/API_TESTING.md`: tutorial completo per API browser e server originale
- `api-test.html`: pagina interattiva per testare il Worker Pyodide
- `tools/test_astra_http.py`: test automatico dell'SDK HTTP originale
- `downloads/*.whl`: SDK Python 1.3 installabile senza pip online

## Aggiornamento da terminale Ubuntu

Se il repository è già presente in una cartella, entra in quella cartella. Altrimenti clonalo:

```bash
git clone https://github.com/Eleman07/ASTRA---Aerospace-Simulator.git
cd ASTRA---Aerospace-Simulator
```

Estrai lo ZIP **direttamente nella radice** del repository, mantenendo la struttura delle cartelle. Lo ZIP è impacchettato senza cartella esterna:

```bash
unzip -o ~/Scaricati/ASTRA-README-API-KIT.zip -d .
git status
git add README.md api-test.html docs/API_TESTING.md docs/images docs/media tools/test_astra_http.py downloads/
git commit -m "Add visual English README and browser/HTTP API tests"
git push origin main
```

In alternativa: estrai lo ZIP dal file manager e copia tutti i file e le cartelle al livello di `README.md` del repository.

## Dopo il deploy

Apri: https://eleman07.github.io/ASTRA---Aerospace-Simulator/api-test.html

Premi **1 · Test status / models / state** e poi **2 · Run rocket launch API test**.

Controlla `PASS` e scarica il rapporto JSON.

Il test HTTP con `astra.client` va invece eseguito contro il server locale originale (non GitHub Pages): tutti i comandi sono in `docs/API_TESTING.md`.
