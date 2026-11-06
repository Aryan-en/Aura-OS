"""
AURA OS — Audio output driver
Real system volume on every platform Aura runs on:
  Linux/Pi: PipeWire (`wpctl`) or ALSA (`amixer`)    macOS: CoreAudio via AppleScript
"""

from __future__ import annotations

import asyncio
import platform
import re
import shutil
from typing import Any, Dict, Optional, Tuple


async def run(*cmd: str, timeout: float = 5.0) -> Tuple[int, str]:
    """Run a command, return (exit code, combined output). Never raises on a missing/failed command."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, out.decode("utf-8", "replace").strip()
    except (FileNotFoundError, asyncio.TimeoutError, OSError) as e:
        return 127, str(e)


def backend() -> Optional[str]:
    if platform.system() == "Darwin" and shutil.which("osascript"):
        return "coreaudio"
    if shutil.which("wpctl"):
        return "pipewire"
    if shutil.which("amixer"):
        return "alsa"
    return None


async def get_volume() -> Dict[str, Any]:
    """{'percent': int, 'muted': bool, 'backend': str}"""
    be = backend()
    if be == "coreaudio":
        rc, out = await run("osascript", "-e",
                            "set v to get volume settings\nreturn (output volume of v as text) & \",\" & (output muted of v as text)")
        pct, _, muted = out.partition(",")
        return {"percent": int(pct) if pct.isdigit() else 0, "muted": muted.strip() == "true", "backend": be}
    if be == "pipewire":
        rc, out = await run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        m = re.search(r"([\d.]+)", out)
        return {"percent": round(float(m.group(1)) * 100) if m else 0, "muted": "MUTED" in out, "backend": be}
    if be == "alsa":
        rc, out = await run("amixer", "get", "Master")
        m = re.search(r"\[(\d+)%\]", out)
        return {"percent": int(m.group(1)) if m else 0, "muted": "[off]" in out, "backend": be}
    raise RuntimeError("No audio driver found (install wireplumber or alsa-utils).")


async def set_volume(level: str) -> Dict[str, Any]:
    """level: 0-100, 'up', 'down', 'mute', 'unmute'. Returns the resulting state."""
    level = str(level).strip().lower().rstrip("%")
    if level not in ("up", "down", "mute", "unmute") and not level.isdigit():
        raise ValueError("level must be 0-100, up, down, mute or unmute")
    be = backend()
    if be is None:
        raise RuntimeError("No volume control available (install wireplumber or alsa-utils).")
    if be == "coreaudio":
        if level in ("mute", "unmute"):
            script = f"set volume output muted {'true' if level == 'mute' else 'false'}"
        else:
            cur = (await get_volume())["percent"]
            target = {"up": cur + 10, "down": cur - 10}.get(level, int(level) if level.isdigit() else cur)
            script = f"set volume output volume {max(0, min(100, target))}"
        await run("osascript", "-e", script)
    elif be == "pipewire":
        sink = "@DEFAULT_AUDIO_SINK@"
        if level in ("mute", "unmute"):
            await run("wpctl", "set-mute", sink, "1" if level == "mute" else "0")
        elif level in ("up", "down"):
            await run("wpctl", "set-volume", "-l", "1.0", sink, "10%+" if level == "up" else "10%-")
        else:
            await run("wpctl", "set-volume", sink, f"{min(100, int(level))}%")
    else:
        arg = {"up": "10%+", "down": "10%-", "mute": "mute", "unmute": "unmute"}.get(level) or f"{min(100, int(level))}%"
        await run("amixer", "set", "Master", arg)
    return await get_volume()
