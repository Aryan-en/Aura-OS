"""
AURA OS — Voice Activity Detection
Energy-based speech/silence detector with an adaptive noise floor, so a TV or fan in the room
does not hold the microphone open.
"""

from __future__ import annotations

import time
from typing import Optional

from aura.voice.buffer import AudioRingBuffer


class VoiceActivityDetector:
    def __init__(
        self,
        energy_threshold: float = 500.0,
        silence_timeout_ms: int = 300,
        adaptive: bool = True,
        min_speech_ms: int = 120,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.silence_timeout_ms = silence_timeout_ms
        self.adaptive = adaptive
        self.min_speech_ms = min_speech_ms
        self.noise_floor = 0.0
        self.is_speaking = False
        self.last_speech_time: Optional[float] = None
        self.speech_start_time: Optional[float] = None

    @property
    def threshold(self) -> float:
        """Speech must clear both the configured floor and ~3x the learned ambient level."""
        return max(self.energy_threshold, self.noise_floor * 3.0) if self.adaptive else self.energy_threshold

    def process_chunk(self, chunk: bytes) -> bool:
        """Feed a chunk. Returns True when a speech utterance has just ended."""
        rms = AudioRingBuffer.calculate_rms(chunk)
        now = time.time()

        if rms >= self.threshold:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = now
            self.last_speech_time = now
            return False

        if not self.is_speaking:
            # Learn ambient level only while nobody is talking (slow EMA, capped).
            self.noise_floor = 0.98 * self.noise_floor + 0.02 * min(rms, self.energy_threshold * 2)
            return False

        if self.last_speech_time is not None:
            if (now - self.last_speech_time) * 1000.0 >= self.silence_timeout_ms:
                started = self.speech_start_time or now
                long_enough = (self.last_speech_time - started) * 1000.0 >= self.min_speech_ms
                self.is_speaking = False
                self.last_speech_time = None
                self.speech_start_time = None
                return long_enough
        return False

    def reset(self) -> None:
        self.is_speaking = False
        self.last_speech_time = None
        self.speech_start_time = None
