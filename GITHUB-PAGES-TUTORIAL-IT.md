# ASTRA Browser Edition: GitHub Pages & installation on every device

**ASTRA Browser 1.3.1** | Python 3.14 / Pyodide WebAssembly | Italian tutorial

## 0. Read before publishing

- This directory is a **standalone static app**: it contains the physics Python
  code plus WebGL assets, runs in each visitor's browser, and needs NO always-on
  server, payment card, bank verification, or service subscription.
- **Every Python source file in `astra/` becomes public** if you publish it on
  GitHub Pages. Keep your **documentation-only showcase repository separate**.
- The separate HTTP Python SDK (`astra.client`, `.whl`) **cannot connect to
  this edition from another PC**: there is no HTTP backend. For remote Python
  commands use the original ASTRA 1.3 server on a private network/hosting.
- Browser/GPU/RAM limitations still apply: smartphones, especially older iPhones,
  may render slowly or run out of memory. WebGL2, WebAssembly and service worker
  support are required for all features. “Every device” means **compatible**
  browser devices, not literally every model.
- Offline only works **after the site has been opened while online and the user
  has clicked `SALVA PER OFFLINE` and received `OFFLINE PRONTO`**. The GitHub
  Actions workflow below bundles all Pyodide core files, and the PWA caches
  the main interface, Python code, runtime, and selected lower-resolution
  assets. Extra 3D models and optional textures need to be visited while online
  before they work offline. Clearing site storage also deletes the offline files.

## 1. Create your GitHub repository (0 euro, no bank card)

1. Sign up or sign in at https://github.com .
2. Click **+ > New repository** and call it e.g. `astra-browser`.
3. Choose **Public** (GitHub Pages with GitHub Free). Do not initialize README
   if you plan to push the existing project from Terminal.
4. On Ubuntu, extract the **ASTRA-BROWSER-1.3.1.zip** archive, then open a terminal
   in the extracted `ASTRA-BROWSER-1.3.1` folder (which has `index.html` at root).
5. Publish **the Browser Edition only**, not the separate `ASTRA-1.3-FULL.zip`
   to this repository. Do not put API keys, tokens or `.env` files in Git.

```bash
cd ~/Scaricati/ASTRA-BROWSER-1.3.1  # adjust if extracted elsewhere
git init
git branch -M main
git add .
git commit -m "Deploy ASTRA Browser WASM + PWA"
git remote add origin https://github.com/YOUR_USERNAME/astra-browser.git
git push -u origin main
```

GitHub may ask you to authenticate with a browser or Personal Access Token.
You do **not** need to buy a server or enter a credit card.

## 2. Enable automatic GitHub Pages deployment

1. On GitHub open your `astra-browser` repository.
2. Click **Settings > Pages**.
3. Under **Build and deployment > Source** select **GitHub Actions**.
4. Go to **Actions > Deploy ASTRA Browser to GitHub Pages**.
5. If necessary click **Run workflow**, or push a commit to `main`.
6. The included `.github/workflows/pages.yml` downloads the pinned **Pyodide
   314.0.7** runtime automatically at build time (no paid service), validates the
   Python bridge and JavaScript syntax, and deploys the static app.
7. Once the deployment is green, find the live URL in **Settings > Pages**:

```text
https://YOUR_USERNAME.github.io/astra-browser/
```

This is an **example URL**, not an already existing deployment. Loading the
website for the first time may need tens of megabytes of downloaded WASM,
Python stdlib and 3D assets. The browser runs the simulation on the visitor's
CPU; the visitor's graphics device handles WebGL.

**Important:** GitHub Pages publishes from the *repository itself*. Do not
select "Deploy from a branch" with `/docs` when using this workflow; choose
"GitHub Actions". Files must have been extracted so that `index.html` is at
repository root, not inside an extra folder.

## 3. Android / tablet installation

1. Open the HTTPS Pages URL in Chrome or Edge on Android.
2. Allow the Python engine to reach `BROWSER ENGINE ... THIS DEVICE`.
3. Click **SALVA PER OFFLINE**. Keep the site open and stay connected until
   it says `OFFLINE PRONTO` (may consume a lot of mobile data).
4. Open browser menu **⋮ > Install app** or **Add to Home screen**.
5. Launch the ASTRA icon from Home, test **Space / Aircraft / Drone**.
6. Test airplane mode *after* confirming offline storage completion.

## 4. iPhone / iPad installation

1. Open the HTTPS Pages URL in **Safari**.
2. Tap **Share** (square with arrow) > **Add to Home Screen** (menu labels may vary).
3. Confirm **Add** to place the icon on the Home Screen.
4. Open the installed app while online, then click **SALVA PER OFFLINE** to cache
   the supported assets.
5. Keep sufficient free storage; Safari/iOS may reclaim cached data, so offline
   operation cannot be guaranteed after long inactivity or low-storage events.

## 5. Ubuntu / Windows / macOS installation

1. Open the HTTPS Pages URL in Chrome/Edge (WebGL2-capable browser required).
2. Use the Install icon in the address bar, or **⋮ > Cast, save and share >
   Install page as app** (wording varies).
3. Open the installed app and press **SALVA PER OFFLINE** while connected.
4. A PWA can open like a normal desktop window but is still a browser app.

## 6. Test locally BEFORE pushing to GitHub

Run tests from the extracted project directory:

```bash
python3 tools/test_browser_distribution.py
node --check app.js
```

For an offline-capable development version, download the Pyodide runtime **once**:

```bash
python3 tools/prepare_pyodide.py
python3 -m http.server 8080
```

Then open `http://127.0.0.1:8080` in your browser. Never open `index.html`
with a `file://` URL: web workers, wasm fetching and service workers require
HTTP(S). Local localhost is treated as a secure context for service workers.

## 7. Optional Cloudflare Pages (no card)

You can connect the same browser repository to Cloudflare Pages. Set framework
**None**, output directory **`.`** (site root) and build command:

```bash
python3 tools/prepare_pyodide.py
```

GitHub Pages workflow is the tested deployment **configuration**, not a claim
that the hosted simulator has already been manually tested. Cloudflare Pages
limits and build behavior may differ and should be verified at deployment.

## 8. Troubleshooting

- **Black screen or "BROWSER ENGINE FAILED"**: open browser console; verify
  that Pyodide is available at `vendor/pyodide/pyodide.js` and its companion
  .wasm/.mjs/.zip/lock files; check HTTP 404, WASM support and ad blockers.
- **Works online but not offline**: go online, click **SALVA PER OFFLINE** and
  wait for **OFFLINE PRONTO**; installed PWA by itself is not an offline guarantee.
- **Works locally but 404 on GitHub Pages**: `index.html` must be repository root;
  Pages Source **GitHub Actions**; check workflow status and URLs with the repo prefix.
- **Phone is slow**: use smaller assets / close tabs / avoid 100x time acceleration;
  mobile browsers can suspend background tabs or evict cached files.
- **Python SDK cannot connect**: that's expected in standalone Browser Edition;
  local Python classes in a Web Worker are not a public HTTP endpoint.
- **Commercial/proprietary algorithm protection**: never upload private physics
  sources into a public static deployment. Client-side Python/JS/WASM can be
  downloaded, inspected or reverse engineered.

## Suggested two-repository structure

- `astra-aerospace-gnc`: public docs-only README, diagrams, graphs, selective
  original algorithm examples, demo video and portfolio links.
- `astra-browser`: browser app and on-device simulation engine source required
  by Pyodide, hosted by GitHub Pages; use only if you're comfortable publishing
  the client-side physics source.

**Portfolio:** https://elemanprojects.com

Official docs:
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://pyodide.org/en/stable/usage/downloading-and-deploying.html
- https://web.dev/learn/pwa/installation
