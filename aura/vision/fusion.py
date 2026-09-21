"""
AURA OS — Multimodal Fusion Engine
Synchronizes voice tokens with 3D spatial hand gestures to resolve deictic references.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aura.core.logger import logger
from aura.vision.gestures import GestureEvent
from aura.vision.raycaster import ScreenTarget


class DeicticTarget(BaseModel):
    """The resolved spatial target when a user speaks a demonstrative pronoun."""
    word: str
    screen_x: int
    screen_y: int
    confidence: float
    timestamp: float = Field(default_factory=time.time)


class MultimodalFusionEngine:
    """Fuses voice utterances with spatial gesture coordinates."""

    DEICTIC_WORDS = {"this", "that", "these", "those", "here", "there"}

    def __init__(self, temporal_window_ms: int = 400) -> None:
        self.window_ms = temporal_window_ms
        self._target_history: List[tuple[float, ScreenTarget]] = []
        self._gesture_history: List[tuple[float, GestureEvent]] = []

    def record_target(self, target: ScreenTarget) -> None:
        """Record a spatial reticle screen target."""
        now = time.time()
        self._target_history.append((now, target))
        self._cleanup()

    def record_gesture(self, gesture: GestureEvent) -> None:
        """Record a gesture event."""
        now = time.time()
        self._gesture_history.append((now, gesture))
        self._cleanup()

    def _cleanup(self) -> None:
        """Drop entries older than 2x temporal window."""
        cutoff = time.time() - (self.window_ms / 1000.0 * 2.0)
        self._target_history = [item for item in self._target_history if item[0] >= cutoff]
        self._gesture_history = [item for item in self._gesture_history if item[0] >= cutoff]

    def resolve_deictic_reference(self, utterance: str) -> Optional[DeicticTarget]:
        """
        Check if utterance contains deictic pronoun ('this', 'that', 'here')
        and match with simultaneous hand pointing vector.
        """
        tokens = re.findall(r"\b\w+\b", utterance.lower())
        matched_word = next((w for w in tokens if w in self.DEICTIC_WORDS), None)

        if not matched_word:
            return None

        # Find most recent pointing target
        if not self._target_history:
            return None

        recent_time, recent_target = self._target_history[-1]
        now = time.time()
        if (now - recent_time) * 1000.0 <= self.window_ms and recent_target.is_pointing:
            logger.info(
                f"Multimodal Fusion: Resolved '{matched_word}' to screen position ({recent_target.screen_x}, {recent_target.screen_y})"
            )
            return DeicticTarget(
                word=matched_word,
                screen_x=recent_target.screen_x,
                screen_y=recent_target.screen_y,
                confidence=0.92,
            )

        return None
