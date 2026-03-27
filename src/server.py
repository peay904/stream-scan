import logging
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

from src.config import config

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
