"""
AURA OS — 3D Spatial Raycaster & Screen Coordinate Projector
Projects 3D pointing vectors onto the 2D Wayland desktop surface for the Cyan Reticle (UI-021).
"""

from __future__ import annotations

from typing import Optional, Tuple
from pydantic import BaseModel, Field
from aura.vision.landmarks import HandLandmarks


class ScreenTarget(BaseModel):
    """Calculated 2D desktop screen coordinate."""
    x_percent: float = Field(..., ge=0.0, le=1.0)
    y_percent: float = Field(..., ge=0.0, le=1.0)
    screen_x: int
    screen_y: int
    is_pointing: bool


class SpatialRaycaster:
    """Projects index finger pointing vector to desktop coordinates with jitter filtering."""

    def __init__(self, display_width: int = 1920, display_height: int = 1080, smoothing_alpha: float = 0.3) -> None:
        self.width = display_width
        self.height = display_height
        self.alpha = smoothing_alpha
        self.smooth_x: Optional[float] = None
        self.smooth_y: Optional[float] = None

    def project(self, landmarks: HandLandmarks) -> ScreenTarget:
        """Calculate screen intersection point from hand pose."""
        # Index tip coordinates in camera normalized space [0.0 - 1.0]
        # Invert X for mirror camera display
        raw_x = 1.0 - landmarks.index_tip.x
        raw_y = landmarks.index_tip.y

        # Exponential moving average filter for jitter reduction
        if self.smooth_x is None or self.smooth_y is None:
            self.smooth_x = raw_x
            self.smooth_y = raw_y
        else:
            self.smooth_x = self.alpha * raw_x + (1.0 - self.alpha) * self.smooth_x
            self.smooth_y = self.alpha * raw_y + (1.0 - self.alpha) * self.smooth_y

        clamped_x = max(0.0, min(1.0, self.smooth_x))
        clamped_y = max(0.0, min(1.0, self.smooth_y))

        px = int(clamped_x * self.width)
        py = int(clamped_y * self.height)

        is_pointing = (
            landmarks.is_index_extended() and
            not landmarks.is_middle_extended() and
            not landmarks.is_ring_extended()
        )

        return ScreenTarget(
            x_percent=clamped_x,
            y_percent=clamped_y,
            screen_x=px,
            screen_y=py,
            is_pointing=is_pointing,
        )
