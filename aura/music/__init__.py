"""
AURA OS — Music (YouTube Music)
Finds tracks and builds "up next" queues with the unofficial `ytmusicapi` (no login needed for search).
PLAYBACK happens in the HUD through YouTube's official embedded player. When the browser running the
HUD is signed in to a YouTube Premium account, Premium's ad-free playback applies. Aura never handles
Google credentials, and never extracts or downloads audio streams.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

_yt: Any = None


def _client() -> Any:
    global _yt
    if _yt is None:
        try:
            from ytmusicapi import YTMusic
        except ImportError as e:
            raise RuntimeError("Music needs ytmusicapi: pip install 'aura-os[music]'") from e
        _yt = YTMusic()
    return _yt


def _thumb(item: Dict[str, Any]) -> str:
    thumbs = item.get("thumbnails") or ([item["thumbnail"]] if item.get("thumbnail") else [])
    thumbs = thumbs if isinstance(thumbs, list) else []
    return str(thumbs[-1]["url"]) if thumbs and isinstance(thumbs[-1], dict) else ""


def _track(item: Dict[str, Any]) -> Dict[str, Any]:
    artists = item.get("artists") or []
    return {
        "videoId": item["videoId"],
        "title": item.get("title", "Unknown"),
        "artist": ", ".join(a["name"] for a in artists if a.get("name")) or "Unknown artist",
        "thumb": _thumb(item),
    }


def search_tracks(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    res = _client().search(query, filter="songs", limit=limit)
    return [_track(r) for r in res if r.get("videoId")][:limit]


def build_queue(query: str, size: int = 25) -> List[Dict[str, Any]]:
    """Best match first, followed by YouTube Music's radio ("up next") for that track."""
    hits = search_tracks(query, 1)
    if not hits:
        return []
    first = hits[0]
    queue = [first]
    try:
        radio = _client().get_watch_playlist(first["videoId"], limit=size)
        for t in radio.get("tracks", []):
            if t.get("videoId") and t["videoId"] != first["videoId"]:
                queue.append(_track(t))
    except Exception:
        pass  # a search hit alone is still a playable queue
    return queue[:size]


class NowPlaying:
    """Last state reported by the HUD (it owns the player), so voice can answer "what's playing"."""

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {}
        self.updated = 0.0

    def update(self, state: Dict[str, Any]) -> None:
        self.state = {k: state.get(k) for k in ("title", "artist", "playing", "videoId")}
        self.updated = time.time()

    def fresh(self, max_age: float = 15.0) -> bool:
        """True while the HUD player is alive (it reports a heartbeat every few seconds)."""
        return bool(self.state.get("title")) and time.time() - self.updated < max_age

    def describe(self) -> Optional[str]:
        s = self.state
        if not s.get("title"):
            return None
        return f"{s['title']} by {s['artist']}" + ("" if s.get("playing") else ", paused")


now_playing = NowPlaying()
