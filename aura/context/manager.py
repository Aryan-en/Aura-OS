"""
AURA OS — Desktop Context Engine
Monitors focused Wayland windows, active application metadata, and clipboard contents.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class WindowContext(BaseModel):
    """Active window telemetry."""
    app_id: str = Field(default="org.gnome.Terminal")
    title: str = Field(default="Terminal — aura-os")
    pid: int = Field(default=1234)
    surface_id: int = Field(default=1)
    focused: bool = Field(default=True)


class DesktopContext(BaseModel):
    """Consolidated desktop operational state."""
    active_window: WindowContext = Field(default_factory=WindowContext)
    clipboard_text: Optional[str] = None
    focused_element: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class ContextEngine:
    """Manages active window and semantic desktop context for autonomous agents."""

    def __init__(self) -> None:
        self._current_context = DesktopContext()

    def update_active_window(self, app_id: str, title: str, pid: int = 0) -> None:
        self._current_context.active_window = WindowContext(
            app_id=app_id,
            title=title,
            pid=pid,
            focused=True,
        )
        self._current_context.timestamp = time.time()

    def update_clipboard(self, text: str) -> None:
        self._current_context.clipboard_text = text
        self._current_context.timestamp = time.time()

    def get_snapshot(self) -> Dict[str, Any]:
        """Return serialized state dictionary to feed into agent prompts."""
        return self._current_context.model_dump()
