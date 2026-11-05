"""
AURA OS — System Tools
Time, status, volume, UI navigation and power control exposed to agents and voice.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from typing import Any, Dict

from aura.core.events import bus
from aura.tools.registry import registry

VIEWS = ("home", "agents", "files", "applications", "terminal", "browser", "notebook",
         "automation", "smarthome", "system", "research", "settings")


@registry.register("system.time", description="Get the current local date and time.")
async def tool_time() -> Dict[str, Any]:
    now = time.localtime()
    return {
        "time": time.strftime("%I:%M %p", now).lstrip("0"),
        "date": time.strftime("%A, %B %d, %Y", now),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", now),
    }


@registry.register("system.status", description="Report CPU, memory, disk usage and temperature.")
async def tool_status() -> Dict[str, Any]:
    from aura.ui.telemetry import get_system_telemetry

    return get_system_telemetry()


@registry.register("ui.open_view", description=f"Show a HUD screen. view is one of: {', '.join(VIEWS)}.")
async def tool_open_view(view: str) -> Dict[str, Any]:
    view = view.strip().lower()
    if view not in VIEWS:
        raise ValueError(f"Unknown view '{view}'. Choose from: {', '.join(VIEWS)}")
    bus.emit("ui.view", view=view)
    return {"view": view}


async def _run(*cmd: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    return out.decode("utf-8", "replace").strip()


@registry.register("system.set_volume", description="Set output volume: percent 0-100, or 'up'/'down'/'mute'/'unmute'.")
async def tool_set_volume(level: str) -> Dict[str, Any]:
    level = str(level).strip().lower().rstrip("%")
    if shutil.which("wpctl"):
        sink = "@DEFAULT_AUDIO_SINK@"
        if level in ("mute", "unmute"):
            await _run("wpctl", "set-mute", sink, "1" if level == "mute" else "0")
        elif level in ("up", "down"):
            await _run("wpctl", "set-volume", sink, "10%+" if level == "up" else "10%-")
        elif level.isdigit():
            await _run("wpctl", "set-volume", sink, f"{min(100, int(level))}%")
        else:
            raise ValueError("level must be 0-100, up, down, mute or unmute")
    elif shutil.which("amixer"):
        arg = {"up": "10%+", "down": "10%-", "mute": "mute", "unmute": "unmute"}.get(level)
        if arg is None and level.isdigit():
            arg = f"{min(100, int(level))}%"
        if arg is None:
            raise ValueError("level must be 0-100, up, down, mute or unmute")
        await _run("amixer", "set", "Master" if arg not in ("mute", "unmute") else "Master", arg)
    else:
        raise RuntimeError("No volume control available (install wireplumber or alsa-utils).")
    bus.emit("system.volume", level=level)
    return {"volume": level}


@registry.register(
    "system.power",
    description="Power control: action is 'reboot' or 'shutdown'.",
    requires_voice_confirmation=True,
)
async def tool_power(action: str) -> Dict[str, Any]:
    if not re.fullmatch(r"reboot|shutdown", action.strip().lower()):
        raise ValueError("action must be 'reboot' or 'shutdown'")
    action = action.strip().lower()
    asyncio.get_running_loop().call_later(
        3, lambda: asyncio.ensure_future(
            _run("sudo", "-n", "systemctl", "reboot" if action == "reboot" else "poweroff"))
    )
    return {"action": action, "in_seconds": 3}
