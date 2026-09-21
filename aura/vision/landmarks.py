"""
AURA OS — Hand Landmark Data Model & Kinematics
Defines standard 21 3D hand keypoints adhering to MediaPipe landmark topology.
"""

from __future__ import annotations

import math
from typing import List, Tuple
from pydantic import BaseModel, Field


class Point3D(BaseModel):
    """3D point coordinate in camera space."""
    x: float = Field(..., description="Horizontal coordinate [0.0 - 1.0]")
    y: float = Field(..., description="Vertical coordinate [0.0 - 1.0]")
    z: float = Field(default=0.0, description="Depth coordinate relative to wrist")

    def distance_to(self, other: Point3D) -> float:
        """Euclidean distance in 3D space."""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


class HandLandmarks(BaseModel):
    """Container for the 21 3D hand keypoints."""
    points: List[Point3D] = Field(..., min_length=21, max_length=21)

    # Landmark Indices:
    # 0: Wrist
    # 1-4: Thumb (CMC, MCP, IP, TIP)
    # 5-8: Index (MCP, PIP, DIP, TIP)
    # 9-12: Middle (MCP, PIP, DIP, TIP)
    # 13-16: Ring (MCP, PIP, DIP, TIP)
    # 17-20: Pinky (MCP, PIP, DIP, TIP)

    @property
    def wrist(self) -> Point3D:
        return self.points[0]

    @property
    def thumb_tip(self) -> Point3D:
        return self.points[4]

    @property
    def index_mcp(self) -> Point3D:
        return self.points[5]

    @property
    def index_tip(self) -> Point3D:
        return self.points[8]

    @property
    def middle_tip(self) -> Point3D:
        return self.points[12]

    @property
    def ring_tip(self) -> Point3D:
        return self.points[16]

    @property
    def pinky_tip(self) -> Point3D:
        return self.points[20]

    def is_finger_extended(self, tip_idx: int, pip_idx: int) -> bool:
        """Check if finger tip is extended away from wrist further than PIP joint."""
        wrist = self.wrist
        tip_dist = self.points[tip_idx].distance_to(wrist)
        pip_dist = self.points[pip_idx].distance_to(wrist)
        return tip_dist > pip_dist

    def is_index_extended(self) -> bool:
        return self.is_finger_extended(8, 6)

    def is_middle_extended(self) -> bool:
        return self.is_finger_extended(12, 10)

    def is_ring_extended(self) -> bool:
        return self.is_finger_extended(16, 14)

    def is_pinky_extended(self) -> bool:
        return self.is_finger_extended(20, 18)

    def is_all_fingers_extended(self) -> bool:
        """Check for flat open palm."""
        return (
            self.is_index_extended() and
            self.is_middle_extended() and
            self.is_ring_extended() and
            self.is_pinky_extended()
        )

    def pinch_distance(self) -> float:
        """Distance between thumb tip and index tip."""
        return self.thumb_tip.distance_to(self.index_tip)

    def pointing_vector(self) -> Tuple[float, float, float]:
        """Direction vector from index MCP to index TIP."""
        dx = self.index_tip.x - self.index_mcp.x
        dy = self.index_tip.y - self.index_mcp.y
        dz = self.index_tip.z - self.index_mcp.z
        norm = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        return (dx / norm, dy / norm, dz / norm)
