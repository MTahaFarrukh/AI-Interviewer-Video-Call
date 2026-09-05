"""Serve the Phase 1 frontend and mint LiveKit join tokens. Never log secrets."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from config import ROOT_DIR, load_settings
from services.livekit_token import get_livekit_token_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("firstround.token")

FRONTEND_DIR = ROOT_DIR / "frontend"
HOST = "127.0.0.1"
PORT = 8080

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


def _mint_token(name: str) -> dict[str, str]:
    """Compatibility wrapper — single implementation lives in LiveKitTokenService."""
    join = get_livekit_token_service().mint_join_token(name)
    return {
        "token": join.token,
        "url": join.url,
        "room": join.room,
        "identity": join.identity,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        logger.info("%s %s", self.address_string(), fmt % args)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"ok": True, "mode": "voice"})
            return
        if path in {"/", "/index.html"}:
            path = "/index.html"
        relative = path.lstrip("/")
        file_path = (FRONTEND_DIR / relative).resolve()
        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
            self._send_json(403, {"error": "forbidden"})
            return
        if not file_path.is_file():
            self._send_json(404, {"error": "not found"})
            return
        content_type = CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
        self._send_bytes(200, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/token":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return
        name = str(data.get("name") or "").strip()
        if not name:
            self._send_json(400, {"error": "name is required"})
            return
        try:
            payload = _mint_token(name)
        except Exception:
            logger.exception("Failed to mint join token")
            self._send_json(500, {"error": "could not create interview token"})
            return
        logger.info("[TOKEN] issued room=%s identity=%s", payload["room"], payload["identity"])
        self._send_json(200, payload)


def main() -> None:
    load_settings()
    if not FRONTEND_DIR.exists():
        raise SystemExit(f"Frontend directory missing: {FRONTEND_DIR}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info("Frontend ready at http://%s:%s", HOST, PORT)
    logger.info("Open that URL, enter a name, then click Join Interview")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Token server stopped")
        server.server_close()


if __name__ == "__main__":
    main()
