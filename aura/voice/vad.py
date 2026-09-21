"""
AURA OS — Voice Activity Detection (VAD)
Detects beginning and ending of speech with configurable silence timeout.
"""

from __future__ import annotations

import time
from typing import Optional
from aura.voice.buffer import AudioRingBuffer


class VoiceActivityDetector:
    """Evaluates speech state and detects speech end after silence timeout."""

    def __init__(
        self,
        energy_threshold: float = 500.0,
        silence_timeout_ms: int = 300,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.silence_timeout_ms = silence_timeout_ms
        self.is_speaking = False
        self.last_speech_time: Optional[float] = None
        self.speech_start_time: Optional[float] = None

    def process_chunk(self, chunk: bytes) -> bool:
        """
        Process audio chunk.
        Returns True if speech was active and has now ended (utterance complete).
        """
        rms = AudioRingBuffer.calculate_rms(chunk)
        now = time.time()

        if rms >= self.energy_threshold:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = now
            self.last_speech_time = now
            return False

        # If currently in a speech utterance and energy dropped below threshold
        if self.is_speaking and self.last_speech_time is not None:
            silence_duration_ms = (now - self.last_speech_time) * 1000.0
            if silence_duration_ms >= self.silence_timeout_ms:
                self.is_speaking = False
                self.last_speech_time = None
                return True  # Utterance ended!

        return False

    def reset(self) -> None:
        """Reset internal state machine."""
        self.is_speaking = False
        self.last_speech_time = None
        self.speech_start_time = None
