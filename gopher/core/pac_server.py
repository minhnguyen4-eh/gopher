"""Serve the PAC over http://127.0.0.1 instead of file://.

Chrome ignores a file:// PAC URL from the system proxy settings, but fetches an http one.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAC_PORT = 18080


class _Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # macOS often drops the connection mid-response; that is not worth a traceback
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


class PacServer:
    def __init__(self, port: int = PAC_PORT):
        self._port = port
        self._server: _Server | None = None

    def start(self, render) -> str:
        """Serve render() at /proxy.pac and return its URL. Raises OSError if the port is taken."""
        if self._server is None:
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def do_GET(self):
                    if self.path != "/proxy.pac":
                        self.send_error(404)
                        return
                    body = render().encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            self._server = _Server(("127.0.0.1", self._port), Handler)
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self._server.server_address[1]}/proxy.pac"

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
