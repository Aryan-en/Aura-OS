"""
AURA OS — System Tools
Time, status, volume, UI navigation and power control exposed to agents and voice.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict

from aura import audio
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
    _, out = await audio.run(*cmd)
    return out


@registry.register("system.set_volume", description="Set output volume: percent 0-100, or 'up'/'down'/'mute'/'unmute'.")
async def tool_set_volume(level: str) -> Dict[str, Any]:
    state = await audio.set_volume(level)
    bus.emit("system.volume", **state)
    return state


@registry.register("system.get_volume", description="Read the current output volume (percent, muted).")
async def tool_get_volume() -> Dict[str, Any]:
    return await audio.get_volume()


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
