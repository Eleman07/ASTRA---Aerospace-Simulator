#!/usr/bin/env python3
"""ASTRA local HTTP API and shared 3D simulation viewer.

Usage:
    python server.py --open

The Python client advances the simulation. The browser reads
the same state, avoiding independent physics engines.
"""

import argparse
import json
import threading
import webbrowser

from http.server import (
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from urllib.parse import urlsplit

from browser_bridge import route_raw


ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()


# Local browser bridge:
# Replace Pyodide calls with HTTP calls to the Python engine.
# When the viewer asks for /step, return /state instead.
# This prevents the browser from advancing the physics twice.

BROWSER_API = """
export async function browserApi(path, payload) {
    const viewerStep = path === "/step";
    const endpoint = viewerStep ? "/state" : path;
    const post = payload !== undefined && !viewerStep;

    const response = await fetch("/api/v1" + endpoint, {
        method: post ? "POST" : "GET",
        headers: {"Content-Type": "application/json"},
        body: post ? JSON.stringify(payload) : undefined,
        cache: "no-store"
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "ASTRA HTTP error");
    }

    return data;
}

export function browserReady() {
    return Promise.resolve(true);
}

// Update the viewer even when the Play button is not pressed.
// The existing STEP control updates the WebGL scene through
// consumeEngine(). Its /step request is redirected to /state.
setInterval(() => {
    const step = document.getElementById("step");
    if (step && !step.disabled) {
        step.click();
    }
}, 200);
"""


# Do not register the production GitHub Pages offline cache
# while using the local development server.

LOCAL_SERVICE_WORKER = """
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => {
    event.waitUntil(self.registration.unregister());
});
"""


class AstraHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(ROOT),
            **kwargs
        )

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_content(self, content, content_type, status=200):
        if isinstance(content, str):
            content = content.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlsplit(self.path).path

        if path.startswith("/api/v1/"):
            return self.handle_api()

        if path == "/browser-api.js":
            return self.send_content(
                BROWSER_API,
                "text/javascript; charset=utf-8"
            )

        if path == "/service-worker.js":
            return self.send_content(
                LOCAL_SERVICE_WORKER,
                "text/javascript; charset=utf-8"
            )

        if any(
            component.startswith(".")
            for component in path.split("/")
            if component
        ):
            return self.send_error(404)

        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path.startswith("/api/v1/"):
            return self.handle_api()

        self.send_error(404)

    def handle_api(self):
        try:
            length = int(self.headers.get("Content-Length", 0))

            if length < 0 or length > 2_000_000:
                return self.send_content(
                    '{"error":"Invalid request size"}',
                    "application/json",
                    413
                )

            payload = {}

            if self.command == "POST":
                body = self.rfile.read(length)
                payload = json.loads(body or b"{}")

            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")

            request = {
                "method": self.command,
                "path": self.path.removeprefix("/api/v1"),
                "payload": payload,
            }

            with LOCK:
                result = json.loads(
                    route_raw(json.dumps(request))
                )

            if result.get("ok"):
                status = 200
                response = result["data"]
            else:
                status = 400
                response = {
                    "error": result.get("error", "Unknown error")
                }

            self.send_content(
                json.dumps(response, allow_nan=False),
                "application/json; charset=utf-8",
                status
            )

        except (ValueError, TypeError) as error:
            self.send_content(
                json.dumps({"error": str(error)}),
                "application/json",
                400
            )

        except Exception as error:
            self.send_content(
                json.dumps({"error": str(error)}),
                "application/json",
                500
            )

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/v1/"):
            super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(
        description="ASTRA Local Simulation Server"
    )

    parser.add_argument(
        "--port", type=int, default=8765
    )
    parser.add_argument(
        "--open", action="store_true"
    )

    args = parser.parse_args()

    address = f"http://127.0.0.1:{args.port}"

    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        AstraHandler
    )
    server.daemon_threads = True

    print()
    print("ASTRA LOCAL SIMULATION SERVER")
    print("-----------------------------")
    print("3D Viewer:", address)
    print("HTTP API: ", address + "/api/v1/status")
    print()
    print("Press Ctrl+C to stop.")
    print(flush=True)

    if args.open:
        webbrowser.open(address)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ASTRA.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
