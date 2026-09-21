"""
AURA OS — Desktop Shell Simulator Web Server
Serves the local desktop HUD interface on localhost:8765 and bridges to aurad UDS socket.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from aiohttp import web if False else None  # Use built-in asyncio stream or http.server
import http.server
import socketserver
import threading
import urllib.parse

from aura.core.config import get_default_socket_path
from aura.core.logger import logger
from aura.ipc.client import AuraIPCClient

STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).parent.parent.parent


class AuraHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP API bridging the Web HUD to the aurad daemon."""

    def _send_json(self, status_code: int, data: Any) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if path == "/Home.png":
            img_file = PROJECT_ROOT / "UI" / "Home.png"
            if img_file.exists():
                content = img_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if path == "/api/status":
            try:
                res = asyncio.run(self._call_ipc("core.status"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(503, {"error": f"Daemon offline: {e}"})
            return

        if path == "/api/agents":
            try:
                res = asyncio.run(self._call_ipc("agent.list"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(503, {"error": str(e)})
            return

        if path == "/api/tools":
            try:
                res = asyncio.run(self._call_ipc("tools.list"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(503, {"error": str(e)})
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/goal":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                prompt = data.get("prompt") or data.get("goal")
                res = asyncio.run(self._call_ipc("agent.submit_goal", {"goal": prompt}))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        self.send_error(404, "Endpoint not found")

    async def _call_ipc(self, method: str, params: dict | None = None) -> Any:
        socket_path = get_default_socket_path()
        async with AuraIPCClient(socket_path=socket_path) as client:
            return await client.call(method, params or {})

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP request logging
        pass


def run_ui_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Launch the Web HUD simulator."""
    server = http.server.ThreadingHTTPServer((host, port), AuraHTTPHandler)
    logger.info(f"AURA Desktop UI Simulator running at: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("UI Server shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_ui_server()
