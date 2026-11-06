"""AURA OS — Music tools (play, transport). The HUD plays; these tools tell it what to do."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from aura.core.events import bus
from aura.music import build_queue, now_playing, system_media
from aura.tools.registry import registry

ACTIONS = ("pause", "resume", "toggle", "next", "previous", "volume_up", "volume_down")


@registry.register("music.play", description="Play a song, artist or mood on YouTube Music (query).")
async def tool_play(query: str) -> Dict[str, Any]:
    queue = await asyncio.to_thread(build_queue, query)
    if not queue:
        raise ValueError(f"I couldn't find anything for '{query}'.")
    bus.emit("music.queue", tracks=queue, index=0)
    return {"title": queue[0]["title"], "artist": queue[0]["artist"], "queued": len(queue)}


@registry.register("music.control", description=f"Control playback. action is one of: {', '.join(ACTIONS)}.")
async def tool_control(action: str) -> Dict[str, Any]:
    """Aura's own HUD player wins while it is alive; otherwise drive the computer's active media player."""
    action = action.strip().lower()
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {', '.join(ACTIONS)}")
    if action.startswith("volume_"):
        from aura import audio

        state = await audio.set_volume("up" if action == "volume_up" else "down")
        bus.emit("system.volume", **state)
        return {"action": action, "target": "system", **state}
    if now_playing.fresh():
        bus.emit("music.control", action=action)
        return {"action": action, "target": "hud"}
    try:
        res = await system_media.control(action)
        return {**res, "target": "system"}
    except RuntimeError:
        if not now_playing.state.get("title"):
            raise ValueError("Nothing is playing. Say 'play' and a song name.") from None
        bus.emit("music.control", action=action)  # HUD may hold a paused queue
        return {"action": action, "target": "hud"}
