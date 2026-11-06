"""
AURA OS — System media control
Reads and controls whatever is playing on the computer itself, through the OS's real media interfaces:
  Linux / Raspberry Pi : MPRIS via `playerctl` (Spotify, VLC, mpv, Chromium/Firefox tabs, ...)
  macOS                : Spotify and Apple Music via AppleScript
macOS' system-wide Now Playing is not available to third-party tools since macOS 15.4, so other macOS
apps (browser tabs, etc.) cannot be read or controlled from here.
"""

from __future__ import annotations

import platform
import shutil
from typing import Any, Dict, List, Optional

from aura import audio

SEP = "\x1f"
ACTIONS = {"pause", "resume", "next", "previous", "toggle"}
_PLAYERCTL = {"pause": "pause", "resume": "play", "next": "next", "previous": "previous", "toggle": "play-pause"}
_APPLESCRIPT = {"pause": "pause", "resume": "play", "next": "next track", "previous": "previous track",
                "toggle": "playpause"}
MAC_APPS = ("Spotify", "Music")


def _pick(players: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Prefer a player that is playing, then one that is paused; ignore stopped/empty ones."""
    for want in ("playing", "paused"):
        for p in players:
            if p["status"] == want and p.get("title"):
                return p
    return None


def parse_playerctl(output: str) -> List[Dict[str, Any]]:
    players = []
    for line in output.splitlines():
        parts = line.split(SEP)
        if len(parts) < 5:
            continue
        status, artist, title, art, name = parts[:5]
        players.append({"player": name, "status": status.lower(), "artist": artist, "title": title,
                        "art": art if art.startswith("http") else "", "source": "mpris"})
    return players


async def _linux_status() -> Optional[Dict[str, Any]]:
    if not shutil.which("playerctl"):
        return None
    fmt = SEP.join(["{{status}}", "{{artist}}", "{{title}}", "{{mpris:artUrl}}", "{{playerName}}"])
    rc, out = await audio.run("playerctl", "-a", "metadata", "--format", fmt)
    return _pick(parse_playerctl(out)) if rc == 0 else None


def _mac_status_script(app: str) -> str:
    return (f'if application "{app}" is running then\n'
            f'  tell application "{app}"\n'
            f'    if player state is stopped then return ""\n'
            f'    return (player state as text) & linefeed & (name of current track) & linefeed & (artist of current track)\n'
            f'  end tell\n'
            f'end if\nreturn ""')


def parse_mac(app: str, output: str) -> Optional[Dict[str, Any]]:
    lines = output.splitlines()
    if len(lines) < 3 or not lines[1]:
        return None
    return {"player": app.lower(), "status": lines[0].strip().lower(), "title": lines[1], "artist": lines[2],
            "art": "", "source": "applescript"}


async def _mac_status() -> Optional[Dict[str, Any]]:
    found = []
    for app in MAC_APPS:
        rc, out = await audio.run("osascript", "-e", _mac_status_script(app))
        p = parse_mac(app, out) if rc == 0 else None
        if p:
            found.append(p)
    return _pick(found)


async def status() -> Optional[Dict[str, Any]]:
    """The active system player, or None. Shape: {player, status, title, artist, art, source}."""
    if platform.system() == "Darwin":
        return await _mac_status()
    return await _linux_status()


async def control(action: str) -> Dict[str, Any]:
    """Send a transport command to the active player. Raises RuntimeError if there is none."""
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {', '.join(sorted(ACTIONS))}")
    cur = await status()
    if cur is None:
        raise RuntimeError("No media player is active on this computer.")
    if cur["source"] == "mpris":
        rc, out = await audio.run("playerctl", "-p", cur["player"], _PLAYERCTL[action])
    else:
        app = "Spotify" if cur["player"] == "spotify" else "Music"
        rc, out = await audio.run("osascript", "-e", f'tell application "{app}" to {_APPLESCRIPT[action]}')
    if rc != 0:
        raise RuntimeError(f"{cur['player']} did not accept the command: {out[:120]}")
    return {"player": cur["player"], "action": action}
