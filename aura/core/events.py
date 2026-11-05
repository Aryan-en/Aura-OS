"""
AURA OS — Event Bus
In-process pub/sub with a replayable ring of recent events. The HUD polls the ring
(via IPC `events.poll`) to render voice state, transcripts, confirmations and UI commands.
"""

from __future__ import annotations

import itertools
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List

Event = Dict[str, Any]


class EventBus:
    def __init__(self, maxlen: int = 300) -> None:
        self._events: Deque[Event] = deque(maxlen=maxlen)
        self._ids = itertools.count(1)
        self._subs: List[Callable[[Event], None]] = []

    def emit(self, type_: str, **data: Any) -> Event:
        ev: Event = {**data, "id": next(self._ids), "ts": time.time(), "type": type_}  # reserved keys win
        self._events.append(ev)
        for cb in list(self._subs):
            try:
                cb(ev)
            except Exception:
                pass
        return ev

    def subscribe(self, cb: Callable[[Event], None]) -> None:
        self._subs.append(cb)

    def since(self, last_id: int = 0, limit: int = 100) -> List[Event]:
        return [e for e in self._events if e["id"] > last_id][-limit:]

    @property
    def last_id(self) -> int:
        return self._events[-1]["id"] if self._events else 0


# Process-wide bus shared by the daemon subsystems.
bus = EventBus()
