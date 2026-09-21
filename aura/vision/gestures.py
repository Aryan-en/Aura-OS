"""
AURA OS — Hand Gesture Classifier
Heuristic and kinematic gesture classification for the Jarvis multimodal vocabulary.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from aura.vision.landmarks import HandLandmarks


class GestureType(str, Enum):
    NONE = "NONE"
    POINT = "GEST-001_POINT"
    PINCH = "GEST-002_PINCH"
    OPEN_PALM = "GEST-003_OPEN_PALM"
    SWIPE_LEFT = "GEST-004_SWIPE_LEFT"
    SWIPE_RIGHT = "GEST-004_SWIPE_RIGHT"
    AIR_PUSH = "GEST-005_AIR_PUSH"


class GestureEvent(BaseModel):
    """Event emitted when a canonical gesture is recognized."""
    gesture: GestureType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    screen_x: Optional[float] = None
    screen_y: Optional[float] = None
    timestamp: float = Field(default_factory=time.time)


class GestureClassifier:
    """Classifies temporal streams of hand landmarks."""

    def __init__(self) -> None:
        self._history: List[tuple[float, HandLandmarks]] = []
        self._max_history = 10

    def classify(self, landmarks: HandLandmarks) -> GestureEvent:
        now = time.time()
        self._history.append((now, landmarks))
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # 1. Check OPEN_PALM (GEST-003: Emergency Stop / Pause)
        # All 5 fingers extended flat, palm open
        if landmarks.is_all_fingers_extended() and landmarks.pinch_distance() > 0.15:
            return GestureEvent(gesture=GestureType.OPEN_PALM, confidence=0.95)

        # 2. Check PINCH (GEST-002: Drag / Pan)
        # Thumb tip and index tip touching (< 0.05 normalized distance)
        if landmarks.pinch_distance() < 0.05:
            return GestureEvent(
                gesture=GestureType.PINCH,
                confidence=0.90,
                screen_x=landmarks.index_tip.x,
                screen_y=landmarks.index_tip.y,
            )

        # 3. Check AIR_PUSH (GEST-005: Spatial Tap / Click)
        # Fast forward movement along Z-axis of index tip
        if len(self._history) >= 3 and landmarks.is_index_extended():
            old_time, old_landmarks = self._history[-3]
            dt = now - old_time
            if dt > 0:
                dz = landmarks.index_tip.z - old_landmarks.index_tip.z
                # Forward impulse into screen (negative Z)
                if dz < -0.04 and not landmarks.is_middle_extended():
                    return GestureEvent(
                        gesture=GestureType.AIR_PUSH,
                        confidence=0.88,
                        screen_x=landmarks.index_tip.x,
                        screen_y=landmarks.index_tip.y,
                    )

        # 4. Check SWIPE WAVE (GEST-004)
        if len(self._history) >= 4:
            old_time, old_landmarks = self._history[-4]
            dt = now - old_time
            if dt > 0:
                dx = landmarks.wrist.x - old_landmarks.wrist.x
                velocity = dx / dt
                if velocity > 1.2:
                    return GestureEvent(gesture=GestureType.SWIPE_RIGHT, confidence=0.85)
                elif velocity < -1.2:
                    return GestureEvent(gesture=GestureType.SWIPE_LEFT, confidence=0.85)

        # 5. Check POINT & RAYCAST (GEST-001)
        # Index extended, middle/ring/pinky curled
        if (
            landmarks.is_index_extended() and
            not landmarks.is_middle_extended() and
            not landmarks.is_ring_extended() and
            not landmarks.is_pinky_extended()
        ):
            return GestureEvent(
                gesture=GestureType.POINT,
                confidence=0.92,
                screen_x=landmarks.index_tip.x,
                screen_y=landmarks.index_tip.y,
            )

        return GestureEvent(gesture=GestureType.NONE, confidence=0.0)
