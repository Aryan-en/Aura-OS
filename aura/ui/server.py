"""
AURA OS — Desktop Shell Simulator Web Server
Serves the local desktop HUD interface on localhost:8765 and bridges to aurad UDS socket.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict

import yaml

from aura.core.config import AuraConfig, get_default_socket_path
from aura.core.logger import logger
from aura.ipc.client import AuraIPCClient

STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVER_START_TIME = time.time()


def get_system_telemetry() -> Dict[str, Any]:
    """Gather live CPU, RAM, and Disk telemetry from host system."""
    disk = shutil.disk_usage(os.path.expanduser("~"))
    disk_pct = round((disk.used / disk.total) * 100, 1)

    mem_pct = 42.0
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["vm_stat"], text=True)
            m = re.findall(r"Pages (free|active|inactive|speculative|wired down):\s+(\d+)", out)
            stats = {k: int(v) for k, v in m}
            free = stats.get("free", 0) + stats.get("speculative", 0)
            used = stats.get("active", 0) + stats.get("wired down", 0)
            total = free + used
            if total > 0:
                mem_pct = round((used / total) * 100, 1)
        elif os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", encoding="utf-8") as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].strip().split()[0])
            total = mem.get("MemTotal", 1)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            mem_pct = round(((total - avail) / total) * 100, 1)
    except Exception:
        pass

    try:
        load = os.getloadavg()[0]
        cores = os.cpu_count() or 4
        cpu_pct = min(100.0, max(1.0, round((load / cores) * 100, 1)))
    except Exception:
        cpu_pct = 12.0

    return {
        "cpu": cpu_pct,
        "ram": mem_pct,
        "disk": disk_pct,
        "platform": f"{platform.system()} {platform.machine()}",
        "uptime": round(time.time() - SERVER_START_TIME, 1),
    }


class AuraHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP API bridging the Web HUD to the aurad daemon."""

    def _send_json(self, status_code: int, data: Any) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if path in ("/wallpaper.jpg", "/Reference_UI.png", "/Home.png"):
            target_img = STATIC_DIR / path.lstrip("/")
            if not target_img.exists():
                target_img = PROJECT_ROOT / "UI" / path.lstrip("/")
            if not target_img.exists():
                target_img = PROJECT_ROOT / path.lstrip("/")
            if target_img.exists():
                mime = "image/jpeg" if path.endswith((".jpg", ".jpeg")) else "image/png"
                content = target_img.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "public, max-age=86400")
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

        if path == "/api/telemetry":
            self._send_json(200, get_system_telemetry())
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

        if path == "/api/files":
            query = urllib.parse.parse_qs(parsed.query)
            req_path = query.get("path", [str(PROJECT_ROOT)])[0]
            target = Path(req_path).expanduser().resolve()
            if not target.exists() or not target.is_dir():
                target = PROJECT_ROOT

            items = []
            try:
                for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                    if entry.name.startswith(".") and entry.name not in (".venv", ".gitignore"):
                        continue
                    try:
                        st = entry.stat()
                        items.append({
                            "name": entry.name,
                            "path": str(entry),
                            "is_dir": entry.is_dir(),
                            "size": st.st_size if not entry.is_dir() else 0,
                            "mtime": time.strftime("%b %d, %H:%M", time.localtime(st.st_mtime)),
                        })
                    except OSError:
                        continue

                parent_dir = str(target.parent) if target.parent != target else str(target)
                self._send_json(200, {
                    "path": str(target),
                    "parent": parent_dir,
                    "items": items,
                })
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if path == "/api/file_content":
            query = urllib.parse.parse_qs(parsed.query)
            req_path = query.get("path", [""])[0]
            target = Path(req_path).expanduser().resolve()
            if target.is_file():
                try:
                    text = target.read_text(encoding="utf-8", errors="replace")[:65536]
                    self._send_json(200, {
                        "path": str(target),
                        "name": target.name,
                        "content": text,
                        "size": target.stat().st_size,
                    })
                except Exception as e:
                    self._send_json(500, {"error": str(e)})
            else:
                self._send_json(404, {"error": "File not found or not a regular file"})
            return

        if path == "/api/memory":
            try:
                from aura.memory.db import MemoryDB
                db = MemoryDB()
                items = db.list_recent(limit=50)
                self._send_json(200, {"items": items})
            except Exception:
                self._send_json(200, {"items": [
                    {"key": "user_name", "value": "Aryan", "category": "preference", "updated_at": time.time() - 3600},
                    {"key": "system_target", "value": "ARM64 Linux (Raspberry Pi 5 / UTM)", "category": "system", "updated_at": time.time() - 1800},
                    {"key": "audio_stack", "value": "PipeWire 16kHz Mono RingBuffer", "category": "architecture", "updated_at": time.time() - 900},
                    {"key": "hand_landmarks", "value": "21-point 3D MediaPipe kinematics", "category": "vision", "updated_at": time.time() - 300},
                ]})
            return

        if path == "/api/gemini":
            from aura.agents.gemini import GeminiClient
            client = GeminiClient()
            masked = (
                client.api_key[:6] + "..." + client.api_key[-4:]
                if client.api_key and len(client.api_key) > 10
                else ""
            )
            self._send_json(200, {
                "configured": client.is_configured(),
                "model": client.model,
                "has_key": bool(client.api_key),
                "masked_key": masked,
            })
            return

        if path == "/api/voice/status":
            try:
                res = asyncio.run(self._call_ipc("voice.status"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(503, {
                    "state": "WAIT_WAKE",
                    "wake_word": "aura",
                    "is_speaking": False,
                    "error": str(e),
                })
            return

        if path == "/api/settings":
            try:
                cfg = AuraConfig.load()
                self._send_json(200, cfg.model_dump())
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        if parsed.path == "/api/goal":
            try:
                data = json.loads(body.decode("utf-8"))
                prompt = data.get("prompt") or data.get("goal")
                res = asyncio.run(self._call_ipc("agent.submit_goal", {"goal": prompt}))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/terminal":
            try:
                data = json.loads(body.decode("utf-8"))
                cmd = data.get("command", "").strip()
                cwd = data.get("cwd") or str(PROJECT_ROOT)
                if not cmd:
                    self._send_json(400, {"error": "No command provided"})
                    return

                try:
                    ipc_res = asyncio.run(self._call_ipc("tools.execute", {
                        "name": "terminal.run_command",
                        "args": {"command": cmd, "cwd": cwd, "timeout_sec": 30.0},
                    }))
                    if ipc_res.success:
                        self._send_json(200, ipc_res.data)
                        return
                except Exception:
                    pass

                proc = subprocess.run(
                    cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30
                )
                self._send_json(200, {
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "combined": (proc.stdout + proc.stderr).strip(),
                })
            except subprocess.TimeoutExpired:
                self._send_json(200, {"command": cmd, "exit_code": 124, "combined": "Command timed out (30s)"})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/memory":
            try:
                from aura.memory.db import MemoryDB
                data = json.loads(body.decode("utf-8"))
                key = data.get("key", "").strip()
                val = data.get("value", "").strip()
                cat = data.get("category", "general").strip()
                if not key or not val:
                    self._send_json(400, {"error": "key and value required"})
                    return
                db = MemoryDB()
                db.set(key, val, category=cat)
                self._send_json(200, {"success": True, "key": key})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/settings":
            try:
                data = json.loads(body.decode("utf-8"))
                target_cfg = PROJECT_ROOT / "config" / "rpi5.yaml"
                with open(target_cfg, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f)
                self._send_json(200, {"success": True, "saved_to": str(target_cfg)})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/gemini/test":
            try:
                from aura.agents.gemini import GeminiClient

                data = json.loads(body.decode("utf-8"))
                key = data.get("api_key", "").strip()
                model = data.get("model", "gemini-2.5-flash")
                client = GeminiClient(api_key=key, model=model)
                res = client.test_connection()
                self._send_json(200, res)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/gemini/save":
            try:
                data = json.loads(body.decode("utf-8"))
                key = data.get("api_key", "").strip()
                model = data.get("model", "gemini-2.5-flash")
                if key:
                    os.environ["GEMINI_API_KEY"] = key
                target_cfg = PROJECT_ROOT / "config" / "rpi5.yaml"
                existing = {}
                if target_cfg.exists():
                    with open(target_cfg, "r", encoding="utf-8") as f:
                        existing = yaml.safe_load(f) or {}
                if "gemini" not in existing:
                    existing["gemini"] = {}
                existing["gemini"]["api_key"] = key
                existing["gemini"]["model"] = model
                with open(target_cfg, "w", encoding="utf-8") as f:
                    yaml.safe_dump(existing, f)
                self._send_json(200, {
                    "success": True,
                    "message": f"Gemini API key linked and saved successfully ({model})",
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/voice/listen":
            try:
                res = asyncio.run(self._call_ipc("voice.listen"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/voice/pause":
            try:
                res = asyncio.run(self._call_ipc("voice.pause"))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/voice/speak":
            try:
                data = json.loads(body.decode("utf-8"))
                text = data.get("text", "").strip()
                res = asyncio.run(self._call_ipc("voice.speak", {"text": text}))
                self._send_json(200, res.data if res.success else {"error": res.error})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/voice/interact":
            try:
                data = json.loads(body.decode("utf-8"))
                prompt = data.get("prompt") or data.get("goal", "")
                speak = data.get("speak", True)
                res = asyncio.run(self._call_ipc("voice.interact", {"prompt": prompt, "speak": speak}))
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
    import argparse

    parser = argparse.ArgumentParser(description="AURA OS Desktop Shell Simulator Web Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (e.g. 0.0.0.0 for LAN access on Raspberry Pi)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number to listen on (default: 8765)",
    )
    args = parser.parse_args()
    run_ui_server(host=args.host, port=args.port)
