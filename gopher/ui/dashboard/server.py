"""Local web dashboard, served on 127.0.0.1 and opened from the menubar."""

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ...core.controller import Controller, NotConfigured

INDEX_HTML = Path(__file__).with_name("index.html")


class Dashboard:
    def __init__(self, controller: Controller):
        self.controller = controller
        self.token = secrets.token_urlsafe(16)  # blocks other web pages from driving the API
        self._server: ThreadingHTTPServer | None = None

    def open(self):
        if self._server is None:
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        port = self._server.server_address[1]
        webbrowser.open(f"http://127.0.0.1:{port}/?t={self.token}")

    def close(self):
        if self._server:
            self._server.shutdown()
            self._server = None

    def _handler(self):
        dash = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _authorized(self) -> bool:
                return (self.headers.get("Host", "").startswith("127.0.0.1:")
                        and self.headers.get("X-Token") == dash.token)

            def _send(self, code, body, ctype="application/json"):
                data = body.encode() if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype + "; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json(self, obj, code=200):
                self._send(code, json.dumps(obj))

            def do_GET(self):
                if self.path.startswith("/api/state"):
                    if not self._authorized():
                        return self._json({"error": "forbidden"}, 403)
                    return self._json(dash.controller.snapshot())
                if self.path.startswith("/?t=" + dash.token):
                    return self._send(200, INDEX_HTML.read_text(), "text/html")
                self._send(404, "not found", "text/plain")

            def do_POST(self):
                if not self._authorized():
                    return self._json({"error": "forbidden"}, 403)
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self._json({"error": "bad json"}, 400)
                try:
                    if self.path == "/api/toggle":
                        dash.controller.toggle()
                    elif self.path == "/api/config":
                        dash.controller.apply_config(body)
                    else:
                        return self._json({"error": "not found"}, 404)
                except (NotConfigured, ValueError, TypeError) as e:
                    return self._json({"error": str(e)}, 400)
                self._json({"ok": True})

        return Handler
