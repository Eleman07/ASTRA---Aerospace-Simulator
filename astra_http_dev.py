import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from browser_bridge import route_raw


class AstraHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        if not self.path.startswith("/api/v1/"):
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))

        try:
            payload = json.loads(self.rfile.read(length)) if length else {}

            result = json.loads(route_raw(json.dumps({
                "method": self.command,
                "path": self.path.removeprefix("/api/v1"),
                "payload": payload
            })))

            status = 200 if result["ok"] else 400
            response = result["data"] if result["ok"] else {
                "error": result["error"]
            }

        except Exception as exc:
            status = 500
            response = {"error": str(exc)}

        body = json.dumps(response).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


print("ASTRA API: http://127.0.0.1:8765", flush=True)
HTTPServer(("127.0.0.1", 8765), AstraHandler).serve_forever()
