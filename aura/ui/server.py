"""
AURA OS — HUD Web Server
Serves the HUD and bridges it to the aurad daemon over its Unix socket.

Security model
  * Binds to loopback by default (the kiosk browser runs on the same machine).
  * Any non-loopback client must present the per-device token (cookie / header / ?token=).
  * State-changing requests must come from the same origin (blocks cross-site and DNS-rebinding).
  * No wildcard CORS. File access is limited to configured roots; secrets are never returned.
  * The HUD terminal is disabled unless `ui.allow_terminal: true`.
"""

from __future__ import annotations

import asyncio
import hmac
import http.server
import ipaddress
import json
import os
import secrets
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from aura.core.config import AuraConfig, get_default_socket_path
from aura.core.logger import logger
from aura.ipc.client import AuraIPCClient
from aura.ui.telemetry import get_system_telemetry

STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = Path.home() / ".config" / "aura"
TOKEN_FILE = CONFIG_DIR / "ui_token"
SECRETS_FILE = CONFIG_DIR / "secrets.env"
USER_CONFIG = CONFIG_DIR / "aura.yaml"
MAX_BODY = 256 * 1024
MAX_FILE_BYTES = 64 * 1024
SENSITIVE_NAMES = {".env", "secrets.env", "ui_token", "id_rsa", "id_ed25519", "authorized_keys", ".netrc"}
SENSITIVE_DIRS = {".ssh", ".gnupg", ".aws"}

# IPC methods the HUD may call generically (vault/skills/router). Everything else needs a dedicated route.
READ_RPCS = {"music.system", "volume.get", "vault.list", "vault.read", "vault.search", "skills.list", "router.stats"}
WRITE_RPCS = {"music.control", "volume.set", "music.state", "vault.add", "vault.compile", "skills.run", "skills.approve", "skills.reject",
              "skills.audit", "skills.from_voice_dump"}

SLOW_RPCS = {"voice.interact", "agent.submit_goal", "skills.run", "vault.compile",
             "skills.audit", "skills.from_voice_dump"}

_cfg = AuraConfig.load()


def load_or_create_token() -> str:
    """Per-device access token for LAN clients (created 0600 on first run)."""
    try:
        return TOKEN_FILE.read_text().strip()
    except OSError:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        token = secrets.token_urlsafe(24)
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        return token


TOKEN = load_or_create_token()


def _is_loopback(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr.split("%")[0]).is_loopback
    except ValueError:
        return False


def _allowed_roots() -> list[Path]:
    return [Path(r).expanduser().resolve() for r in _cfg.ui.file_roots]


def _safe_path(raw: str) -> Optional[Path]:
    """Resolve `raw` and return it only if inside an allowed root and not a secret."""
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not any(p == r or r in p.parents for r in _allowed_roots()):
        return None
    if p.name in SENSITIVE_NAMES or any(part in SENSITIVE_DIRS for part in p.parts):
        return None
    return p


def _mask(key: Optional[str]) -> str:
    return f"{key[:4]}…{key[-3:]}" if key and len(key) > 10 else ""


def _save_secret(name: str, value: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = []
    if SECRETS_FILE.exists():
        lines = [ln for ln in SECRETS_FILE.read_text().splitlines() if not ln.startswith(f"{name}=")]
    lines.append(f"{name}={value}")
    fd = os.open(SECRETS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")


class AuraHTTPHandler(http.server.BaseHTTPRequestHandler):
    server_version = "AuraHUD"

    # ------------------------------------------------------------------ helpers
    def _send(self, status: int, body: bytes, ctype: str, extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Any) -> None:
        self._send(status, json.dumps(data).encode(), "application/json", {"Cache-Control": "no-store"})

    def _cookie_token(self) -> str:
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "aura_token":
                return v
        return ""

    def _authorized(self, query_token: str = "") -> bool:
        if _is_loopback(self.client_address[0]):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
            return host in ("localhost", "127.0.0.1", "::1", "")  # blocks DNS rebinding
        supplied = self.headers.get("X-Aura-Token") or self._cookie_token() or query_token
        return hmac.compare_digest(supplied, TOKEN)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True  # non-browser client (curl, CLI)
        return urllib.parse.urlparse(origin).netloc == self.headers.get("Host")

    def _body(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("Request body too large")
        data = json.loads(self.rfile.read(n) or b"{}")
        return data if isinstance(data, dict) else {}

    async def _ipc(self, method: str, params: Optional[dict] = None) -> Any:
        # Calls that may legitimately wait on the user (approval prompts) or an LLM get a long timeout.
        timeout = 75.0 if method in SLOW_RPCS else None
        async with AuraIPCClient(socket_path=get_default_socket_path()) as client:
            return await client.call(method, params or {}, timeout=timeout)

    def _ipc_json(self, method: str, params: Optional[dict] = None, fallback: Optional[dict] = None) -> None:
        try:
            res = asyncio.run(self._ipc(method, params))
            self._json(200 if res.success else 500, res.data if res.success else {"error": res.error})
        except Exception as e:
            self._json(503, fallback if fallback is not None else {"error": f"Daemon offline: {e}"})

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        path = parsed.path
        if not self._authorized(q.get("token", [""])[0]):
            self._send(401, b"Unauthorized: open the HUD from the device itself or use the token URL.", "text/plain")
            return

        if path in ("/", "/index.html"):
            index = STATIC_DIR / "index.html"
            if not index.exists():
                self._send(404, b"HUD not installed", "text/plain")
                return
            extra = {"Cache-Control": "no-cache"}
            tok = q.get("token", [""])[0]
            if tok and hmac.compare_digest(tok, TOKEN):
                extra["Set-Cookie"] = f"aura_token={TOKEN}; Path=/; HttpOnly; SameSite=Strict"
            self._send(200, index.read_bytes(), "text/html; charset=utf-8", extra)
            return

        if path in ("/wallpaper.jpg", "/Reference_UI.png", "/Home.png"):
            for base in (STATIC_DIR, PROJECT_ROOT / "UI", PROJECT_ROOT):
                f = base / path.lstrip("/")
                if f.is_file():
                    mime = "image/jpeg" if path.endswith(".jpg") else "image/png"
                    self._send(200, f.read_bytes(), mime, {"Cache-Control": "public, max-age=86400"})
                    return

        routes = {
            "/api/status": ("core.status", None, None),
            "/api/agents": ("agent.list", None, None),
            "/api/tools": ("tools.list", None, None),
            "/api/memory": ("memory.list", None, {"items": []}),
            "/api/voice/status": ("voice.status", None, {"state": "OFFLINE", "error": "daemon offline"}),
        }
        if path in routes:
            method, params, fb = routes[path]
            self._ipc_json(method, params, fb)
            return

        if path.startswith("/api/x/"):
            method = path[len("/api/x/"):]
            if method in READ_RPCS:
                self._ipc_json(method, {k: v[0] for k, v in q.items() if k != "token"})
                return
            self._send(404, b"Not Found", "text/plain")
            return

        if path == "/api/events":
            since = int(q.get("since", ["0"])[0] or 0)
            self._ipc_json("events.poll", {"since": since, "voice": q.get("voice", ["0"])[0] == "1"},
                           {"events": [], "last_id": since, "offline": True})
            return

        if path == "/api/telemetry":
            self._json(200, get_system_telemetry())
            return

        if path == "/api/files":
            target = _safe_path(q.get("path", [str(Path.home())])[0])
            if target is None or not target.is_dir():
                target = _allowed_roots()[0]
            items = []
            for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith(".") or entry.name in SENSITIVE_NAMES:
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                items.append({"name": entry.name, "path": str(entry), "is_dir": entry.is_dir(),
                              "size": 0 if entry.is_dir() else st.st_size,
                              "mtime": time.strftime("%b %d, %H:%M", time.localtime(st.st_mtime))})
            roots = _allowed_roots()
            parent = target.parent if any(target != r for r in roots) and _safe_path(str(target.parent)) else target
            self._json(200, {"path": str(target), "parent": str(parent), "items": items})
            return

        if path == "/api/file_content":
            target = _safe_path(q.get("path", [""])[0])
            if target is None or not target.is_file():
                self._json(404, {"error": "File not found or access denied"})
                return
            with open(target, "rb") as f:
                text = f.read(MAX_FILE_BYTES).decode("utf-8", "replace")
            self._json(200, {"path": str(target), "name": target.name, "content": text,
                             "size": target.stat().st_size})
            return

        if path == "/api/gemini":
            from aura.agents.gemini import GeminiClient

            c = GeminiClient()
            self._json(200, {"configured": c.is_configured(), "model": c.model,
                             "has_key": bool(c.api_key), "masked_key": _mask(c.api_key)})
            return

        if path == "/api/settings":
            data = AuraConfig.load().model_dump(mode="json")
            data["gemini"]["api_key"] = _mask(data["gemini"].get("api_key"))
            data["socket"].pop("socket_path", None)
            self._json(200, data)
            return

        if path == "/api/hardware":
            from aura.core.hardware import detect_hardware

            hw = detect_hardware()
            self._json(200, {"model": hw.model, "board": hw.board, "ram_mb": hw.ram_mb,
                             "cores": hw.cores, "profile": hw.profile})
            return

        self._send(404, b"Not Found", "text/plain")

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._authorized() or not self._same_origin():
            self._json(403, {"error": "Forbidden"})
            return
        try:
            body = self._body()
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, {"error": str(e)})
            return

        try:
            if path.startswith("/api/x/"):
                method = path[len("/api/x/"):]
                if method not in READ_RPCS | WRITE_RPCS:
                    self._json(404, {"error": "Endpoint not found"})
                else:
                    self._ipc_json(method, body)
            elif path == "/api/goal":
                self._ipc_json("agent.submit_goal", {"goal": body.get("prompt") or body.get("goal")})
            elif path == "/api/confirm":
                self._ipc_json("agent.confirm", {"approved": bool(body.get("approved"))})
            elif path == "/api/voice/listen":
                self._ipc_json("voice.listen")
            elif path == "/api/voice/pause":
                self._ipc_json("voice.pause")
            elif path == "/api/voice/speak":
                self._ipc_json("voice.speak", {"text": str(body.get("text", "")).strip()})
            elif path == "/api/voice/interact":
                self._ipc_json("voice.interact", {"prompt": body.get("prompt") or body.get("goal", ""),
                                                  "speak": body.get("speak", True)})
            elif path == "/api/memory":
                self._ipc_json("memory.set", {"key": body.get("key", ""), "value": body.get("value", ""),
                                              "category": body.get("category", "general")})
            elif path == "/api/terminal":
                self._terminal(body)
            elif path == "/api/settings":
                cfg = AuraConfig.load().model_dump(mode="json")
                for section, vals in body.items():
                    if section in cfg and isinstance(vals, dict) and section not in ("socket",):
                        vals.pop("api_key", None)
                        cfg[section].update(vals)
                cfg["gemini"]["api_key"] = None  # secrets live in secrets.env only
                cfg["socket"].pop("socket_path", None)
                AuraConfig(**cfg)  # validate before writing
                CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                USER_CONFIG.write_text(yaml.safe_dump(cfg))
                self._json(200, {"success": True, "saved_to": str(USER_CONFIG),
                                 "note": "Restart aura-core to apply."})
            elif path == "/api/gemini/test":
                from aura.agents.gemini import GeminiClient

                key = str(body.get("api_key", "")).strip() or None
                self._json(200, GeminiClient(api_key=key, model=body.get("model")).test_connection())
            elif path == "/api/gemini/save":
                key = str(body.get("api_key", "")).strip()
                model = str(body.get("model", "gemini-2.5-flash")).strip()
                if key:
                    _save_secret("GEMINI_API_KEY", key)
                try:
                    asyncio.run(self._ipc("core.set_gemini", {"api_key": key, "model": model}))
                except Exception:
                    pass  # daemon not running: key is picked up at next start
                self._json(200, {"success": True, "message": f"Gemini key saved securely ({model})"})
            else:
                self._json(404, {"error": "Endpoint not found"})
        except Exception as e:
            logger.warning(f"HUD request {path} failed: {e}")
            self._json(500, {"error": str(e)})

    def _terminal(self, body: Dict[str, Any]) -> None:
        if not _cfg.ui.allow_terminal:
            self._json(403, {"error": "Terminal is disabled. Set ui.allow_terminal: true to enable."})
            return
        cmd = str(body.get("command", "")).strip()
        cwd = _safe_path(str(body.get("cwd") or Path.home())) or Path.home()
        if not cmd:
            self._json(400, {"error": "No command provided"})
            return
        try:
            proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
            out = (proc.stdout + proc.stderr).strip()
            self._json(200, {"command": cmd, "exit_code": proc.returncode, "stdout": proc.stdout,
                             "stderr": proc.stderr, "combined": out})
        except subprocess.TimeoutExpired:
            self._json(200, {"command": cmd, "exit_code": 124, "combined": "Command timed out (30s)"})

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_ui_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    host = host or _cfg.ui.host
    port = port or _cfg.ui.port
    server = http.server.ThreadingHTTPServer((host, port), AuraHTTPHandler)
    logger.info(f"AURA HUD running at http://{host}:{port}")
    if not _is_loopback(host):
        logger.warning(f"Listening on the network. Remote access URL: http://<device-ip>:{port}/?token={TOKEN}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="AURA OS HUD web server")
    ap.add_argument("--host", default=None, help="Bind address (default: ui.host, loopback)")
    ap.add_argument("--port", type=int, default=None)
    a = ap.parse_args()
    run_ui_server(a.host, a.port)
