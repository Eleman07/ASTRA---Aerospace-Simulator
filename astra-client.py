
#!/usr/bin/env python3
"""
ASTRA — Rocket GNC Demo
Local physics engine + HTTP API + 3D visualization.

Run:
    python astra-client.py
"""

import json
import sys
import time
import threading
import webbrowser

from pathlib import Path
from http.server import (
    ThreadingHTTPServer,
    SimpleHTTPRequestHandler,
)
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from browser_bridge import route_raw
except ImportError:
    sys.exit(
        "ERRORE: salva astra-client.py nella cartella "
        "ASTRA---Aerospace-Simulator, accanto a browser_bridge.py"
    )

HOST = "127.0.0.1"
PORT = 8877
URL = f"http://{HOST}:{PORT}"
DT = 0.1
MAX_Q = 25000.0  # Pa

engine_lock = threading.RLock()


# Il browser legge lo stato del motore Python locale.
# /step viene convertito in /state, perché è il controller
# Python a far avanzare la simulazione.
BROWSER_API = r"""
export async function browserApi(path, payload) {
    const viewerStep = path === "/step";
    const endpoint = viewerStep ? "/state" : path;

    const url = "/api/v1" + endpoint;
    const post = payload !== undefined && !viewerStep;

    const response = await fetch(url, {
        method: post ? "POST" : "GET",
        headers: {"Content-Type": "application/json"},
        body: post ? JSON.stringify(payload) : undefined,
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(
            "ASTRA API HTTP " + response.status +
            ": " + await response.text()
        );
    }

    return response.json();
}

export function browserReady() {
    return Promise.resolve(true);
}
"""


class AstraServer(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(ROOT),
            **kwargs
        )

    def send_data(self, data, content_type):
        if isinstance(data, str):
            data = data.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/browser-api.js":
            return self.send_data(
                BROWSER_API,
                "text/javascript; charset=utf-8"
            )

        # Disabilita la cache PWA durante questa prova locale.
        if path == "/service-worker.js":
            return self.send_data(
                "self.addEventListener('install', "
                "e => self.skipWaiting());"
                "self.addEventListener('activate', "
                "e => e.waitUntil(self.clients.claim()));",
                "text/javascript"
            )

        if path.startswith("/api/v1/"):
            return self.handle_api()

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/v1/"):
            return self.handle_api()

        self.send_error(404)

    def handle_api(self):
        try:
            size = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(size) if size else b"{}"
            payload = json.loads(body)

            request = {
                "method": self.command,
                "path": self.path.removeprefix("/api/v1"),
                "payload": payload,
            }

            with engine_lock:
                result = json.loads(
                    route_raw(json.dumps(request))
                )

            response = (
                result["data"]
                if result["ok"]
                else {"error": result["error"]}
            )
            status = 200 if result["ok"] else 400

        except Exception as exc:
            response = {"error": str(exc)}
            status = 500

        data = json.dumps(response).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # Evita di stampare ogni richiesta di telemetria.
        if not self.path.startswith("/api/"):
            pass


def api(path, payload=None):
    """Client HTTP Python integrato nello stesso file."""
    data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    req = Request(
        URL + "/api/v1" + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )

    with urlopen(req, timeout=15) as response:
        return json.load(response)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def gnc_controller():
    """Controllo della spinta basato sulla pressione dinamica."""

    print("[GNC] Controller pronto.")

    last_print = 0.0

    while True:
        try:
            state = api("/state")

            if (
                not state.get("mission_started")
                or state.get("vehicle") != "space"
                or state.get("scenario") == "orbital"
                or state.get("phase") in (
                    "LANDED", "CRASHED", "ABORTED"
                )
            ):
                time.sleep(0.2)
                continue

            altitude = state.get("altitude_m", 0.0)
            t = state.get("time_s", 0.0)

            environment = state.get("environment") or {}
            q = environment.get("dynamic_pressure_Pa", 0.0)

            # Guidance: limitare la pressione dinamica.
            error = MAX_Q - q

            # Controllore proporzionale della spinta.
            throttle = clamp(
                85.0 + 0.002 * error,
                55.0,
                100.0
            )

            # Mantiene l'assetto iniziale verticale del launcher.
            # Il motore ASTRA gestisce l'attuazione dell'assetto.
            api("/command", {
                "mode": "python",
                "throttle_pct": throttle,
            })

            # Unico integratore temporale: Python.
            result = api("/step", {"dt_s": DT})

            now = time.monotonic()
            if now - last_print >= 1.0:
                print(
                    f"[GNC] t={t:6.1f}s | "
                    f"h={altitude:9.1f}m | "
                    f"q={q:8.0f}Pa | "
                    f"throttle={throttle:5.1f}% | "
                    f"phase={result.get('phase')}"
                )
                last_print = now

            time.sleep(DT)

        except Exception as exc:
            print("[GNC] Errore:", exc)
            time.sleep(1)


def main():
    server = ThreadingHTTPServer(
        (HOST, PORT),
        AstraServer
    )

    thread = threading.Thread(
        target=gnc_controller,
        daemon=True
    )
    thread.start()

    print()
    print("====================================")
    print("     ASTRA — ROCKET GNC DEMO")
    print("====================================")
    print("Simulatore:", URL)
    print("API:       ", URL + "/api/v1/status")
    print()
    print("Apri la pagina e premi AVVIA MISSIONE.")
    print("Il razzo sarà controllato dallo script Python.")
    print("Premi Ctrl+C per terminare.")
    print()

    webbrowser.open(URL)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nASTRA terminato.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
