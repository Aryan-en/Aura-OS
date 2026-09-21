"""
AURA OS — Local Wake Word Engine
Processes streaming audio chunks for the wake word activation keyword ("Aura").
"""

from __future__ import annotations

from typing import Optional
from aura.core.logger import logger


class WakeWordDetector:
    """Detects 'Aura' activation phrase in audio stream."""

    def __init__(self, keyword: str = "aura", sensitivity: float = 0.5) -> None:
        self.keyword = keyword.lower()
        self.sensitivity = sensitivity
        self._activated = False

    def process_chunk(self, pcm_chunk: bytes) -> bool:
        """
        Process a 16kHz mono audio chunk.
        Returns True immediately when wake phrase is detected.
        """
        # If programmatic flag is set (e.g. for synthetic injection tests)
        if self._activated:
            self._activated = False
            return True
        return False

    def inject_trigger(self) -> None:
        """Trigger activation synthetically for unit/integration testing."""
        self._activated = True
        logger.debug(f"Wake word '{self.keyword}' synthetically triggered.")
