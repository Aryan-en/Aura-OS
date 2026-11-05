"""
AURA OS — Permission Gate
Consequential actions (shell, deletion, power) pause for explicit user approval.
Approval arrives by voice ("confirm" / "cancel") or from the HUD (agent.confirm).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

from aura.core.events import bus

_YES = re.compile(r"^\s*(?:yes|yeah|yep|confirm(?:ed)?|do it|go ahead|proceed|approve|ok(?:ay)?)\b", re.I)
_NO = re.compile(r"^\s*(?:no|nope|cancel|stop|abort|deny|don't|do not|never mind)\b", re.I)


def parse_decision(text: str) -> Optional[bool]:
    """True = approved, False = denied, None = not a decision."""
    if _YES.match(text):
        return True
    if _NO.match(text):
        return False
    return None


class PermissionGate:
    def __init__(self, timeout_sec: float = 30.0, voice_can_confirm: bool = True) -> None:
        self.timeout_sec = timeout_sec
        self.voice_can_confirm = voice_can_confirm
        self._future: Optional[asyncio.Future[bool]] = None
        self._pending: Optional[Dict[str, Any]] = None

    @property
    def pending(self) -> Optional[Dict[str, Any]]:
        return self._pending

    async def request(self, description: str, tool: str = "") -> bool:
        """Block until the user approves/denies, or the request times out (= denied)."""
        if self._future and not self._future.done():
            self._future.set_result(False)  # only one outstanding request
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()
        self._pending = {"description": description, "tool": tool}
        bus.emit("confirm.request", description=description, tool=tool,
                 voice=self.voice_can_confirm, timeout=self.timeout_sec)
        try:
            return await asyncio.wait_for(asyncio.shield(self._future), self.timeout_sec)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending = None
            bus.emit("confirm.closed")

    def resolve(self, approved: bool, source: str = "hud") -> bool:
        """Resolve the outstanding request. Returns False if nothing was pending."""
        if source == "voice" and not self.voice_can_confirm:
            return False
        if self._future and not self._future.done():
            self._future.set_result(approved)
            return True
        return False
