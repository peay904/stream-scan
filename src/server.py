import logging
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

from src.config import config

_DIGEST_JS_PATH = os.path.join(os.path.dirname(__file__), "..", "digest.js")

logger = logging.getLogger(__name__)


class DigestHandler(SimpleHTTPRequestHandler):
    """Serves /output directory. Redirects / to latest.html."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/output", **kwargs)

    def do_GET(self):
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/latest.html")
            self.end_headers()
            return
        if self.path == "/digest.js":
            try:
                with open(_DIGEST_JS_PATH, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_error(404)
            return
        super().do_GET()

    def log_message(self, format, *args):
        # Suppress 200/304 noise; only log errors
        if args[1] not in ("200", "304"):
            logger.warning(f"Web server: {format % args}")


def start_server() -> HTTPServer:
    """Start HTTP server in a background daemon thread."""
    port = config.WEB_PORT
    server = HTTPServer(("0.0.0.0", port), DigestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Web server running at http://0.0.0.0:{port} — serving /output")
    return server
