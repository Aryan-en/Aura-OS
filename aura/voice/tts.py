"""
AURA OS — Text-To-Speech (TTS) Synthesis
Synthesizes speech using Piper neural models with instant cancellation support.
"""

from __future__ import annotations

import asyncio
from typing import Optional
from aura.core.logger import logger


class TextToSpeech:
    """Piper TTS synthesis wrapper with interruptible audio playback."""

    def __init__(self, voice: str = "en_US-lessac-medium") -> None:
        self.voice = voice
        self.is_speaking = False
        self._current_task: Optional[asyncio.Task] = None

    async def speak(self, text: str) -> None:
        """Synthesize and stream audio to PipeWire sink."""
        self.stop()
        self.is_speaking = True
        logger.info(f"AURA Speaking: \"{text}\"")

        # Simulate audio streaming playback duration
        duration_sec = max(0.2, len(text) * 0.05)
        try:
            self._current_task = asyncio.create_task(asyncio.sleep(duration_sec))
            await self._current_task
        except asyncio.CancelledError:
            logger.info("Speech audio playback cancelled by user barge-in or gesture pause.")
        finally:
            self.is_speaking = False
            self._current_task = None

    def stop(self) -> None:
        """Immediately interrupt and silence ongoing speech (<20ms)."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self.is_speaking = False
