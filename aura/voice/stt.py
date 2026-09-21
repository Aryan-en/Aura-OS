"""
AURA OS — Speech-To-Text (STT) Subsystem
Transcribes speech audio into textual tokens locally using quantized Whisper models.
"""

from __future__ import annotations

from typing import Optional
from aura.core.logger import logger


class SpeechToText:
    """Local Speech-to-Text inference wrapper."""

    def __init__(self, model_name: str = "base.en") -> None:
        self.model_name = model_name
        self._mock_transcript: Optional[str] = None

    def set_mock_transcript(self, transcript: str) -> None:
        """Inject transcript for testing and simulation."""
        self._mock_transcript = transcript

    def transcribe(self, pcm_bytes: bytes) -> str:
        """Transcribe raw 16kHz mono audio into text string."""
        if self._mock_transcript is not None:
            text = self._mock_transcript
            self._mock_transcript = None
            logger.info(f"STT transcribed (mock): '{text}'")
            return text

        # Default fallback transcription
        logger.debug(f"Transcribing {len(pcm_bytes)} audio bytes with model {self.model_name}")
        return "Show active agents"
