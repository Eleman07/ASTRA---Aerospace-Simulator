# ASTRA Flight Systems 1.4.1 — pubblicazione GitHub

## A. Da dove partire

Devi avere la cartella ~/ASTRA-Aerospace-Simulator con la sottocartella .git.
La patch ZIP contiene solo i file cambiati e **non** contiene .git o
nuovi asset 3D. La versione completa contiene anche gli asset, ma non .git.

## B. Salva il lavoro attuale

```bash
cd ~/ASTRA-Aerospace-Simulator
git status --short
cd ~
tar -czf "$HOME/ASTRA-before-141-$(date +%Y%m%d-%H%M%S).tar.gz" \
  --exclude=.git ASTRA-Aerospace-Simulator
```

## C. Installa la patch

Scarica ASTRA-FLIGHT-SYSTEMS-1.4.1-PATCH.zip in ~/Downloads, poi:

```bash
cd ~/ASTRA-Aerospace-Simulator
unzip -o ~/Downloads/ASTRA-FLIGHT-SYSTEMS-1.4.1-PATCH.zip -d .
```

Controlla che la versione non sia piu 1.3.1:

```bash
grep -o 'FLIGHT SYSTEMS 1.4.1' index.html
grep -n __version__ astra/__init__.py
```

## D. Test prima del push

```bash
cd ~/ASTRA-Aerospace-Simulator
source ~/Aerospace/astrox/bin/activate
python -m unittest discover -s tools -p 'test_*.py' -v
python -m compileall -q astra server.py browser_bridge.py
node --check app.js
node --check engineering-studio.js
node --check disciplines.js
node --check browser-engine-worker.js
node --check service-worker.js
```

Deve comparire `Ran 30 tests` e `OK`. Se `node` non e installato:
`sudo apt update && sudo apt install -y nodejs npm`.

## E. Commit e push

```bash
cd ~/ASTRA-Aerospace-Simulator
git remote -v
# Se necessario correggi il remote:
git remote set-url origin https://github.com/Eleman07/ASTRA-Aerospace-Simulator.git

git add -A
git diff --cached --check
git status --short
git commit -m "ASTRA Flight Systems 1.4.1: physics, interface, release version"
git pull --rebase origin main
git push origin main
```

Se durante `git pull --rebase` compare `CONFLICT`, fermati; risolvi il
conflitto nel file indicato, poi `git add <file>` e `git rebase --continue`.
Non usare `git push --force`.

## F. Attendi GitHub Actions e verifica la pagina

Apri:
https://github.com/Eleman07/ASTRA-Aerospace-Simulator/actions

Il nuovo workflow verifica 30 test Python e la sintassi JavaScript prima del deploy.
Apri il sito dall'indirizzo indicato in Settings -> Pages: evita di utilizzare
un vecchio URL con tre trattini nel nome del repository.

Prova in ordine:
1. Versione superiore: `FLIGHT SYSTEMS 1.4.1`.
2. Biblioteca discipline: `MODELLO PARAMETRICO` per i modelli non ancora
   validati ad alta fedelta, con limiti dichiarati.
3. Engineering Studio: 18 modelli, `wind_shear` -> `ATTIVA VENTO NELLA MISSIONE`.
4. Seleziona un aereo o drone, apri Studio, scegli `wind_shear`, attiva il vento
   (il comando reinizializza la missione), poi avvia il volo.
5. Verifica dal motore `state.environment.wind_profile_model =
   MONIN_OBUKHOV_SURFACE_LAYER`.

Se vedi ancora la versione 1.3.1: apri DevTools -> Application -> Service Workers,
seleziona Unregister per ASTRA; in Storage -> Clear site data cancella la cache
ASTRA e ricarica con Ctrl+Shift+R. Questo cancella anche i dati locali del sito:
esporta prima eventuali missioni salvate.

## G. Avvio API Python locale

Terminale 1:

```bash
cd ~/ASTRA-Aerospace-Simulator
source ~/Aerospace/astrox/bin/activate
python -u server.py --open
```

Terminale 2:

```bash
cd ~/ASTRA-Aerospace-Simulator
source ~/Aerospace/astrox/bin/activate
curl http://127.0.0.1:8765/api/v1/status
python examples/gnc_demo.py
```

## H. Limiti rimanenti

La fisica di ala finita/comprimibilita subsonica, vento Monin-Obukhov e
correzione di spinta d'ugello e integrata / documentata, ma NON sostituisce
CFD, dati sperimentali, SPICE, FEA 3D o modelli RF convalidati. Gli altri
studi Engineering Studio restano solver parametrici on-demand, non forze nel
motore. Consulta ENGINEERING-1.4.1-STATUS.md.
