"""
AURA OS — PCM Audio Circular Ring Buffer
Maintains high-performance, lock-free ring buffer for 16kHz mono audio streams.
"""

from __future__ import annotations

import math
from typing import Optional


class AudioRingBuffer:
    """Ring buffer holding recent audio samples for wake word pre-roll and VAD."""

    def __init__(self, capacity_bytes: int = 16000 * 2 * 5) -> None:  # 5 seconds of 16kHz 16-bit audio
        self.capacity = capacity_bytes
        self.buffer = bytearray(capacity_bytes)
        self.write_pos = 0
        self.total_written = 0

    def write(self, data: bytes) -> None:
        """Append incoming PCM audio chunk into circular buffer."""
        length = len(data)
        if length >= self.capacity:
            self.buffer[:] = data[-self.capacity:]
            self.write_pos = 0
            self.total_written += length
            return

        end_pos = self.write_pos + length
        if end_pos <= self.capacity:
            self.buffer[self.write_pos:end_pos] = data
        else:
            first_chunk = self.capacity - self.write_pos
            self.buffer[self.write_pos:] = data[:first_chunk]
            self.buffer[:end_pos - self.capacity] = data[first_chunk:]

        self.write_pos = end_pos % self.capacity
        self.total_written += length

    def get_recent(self, num_bytes: int) -> bytes:
        """Extract the most recent N bytes in sequential chronological order."""
        num_bytes = min(num_bytes, min(self.capacity, self.total_written))
        if num_bytes == 0:
            return b""

        start_pos = (self.write_pos - num_bytes) % self.capacity
        if start_pos + num_bytes <= self.capacity:
            return bytes(self.buffer[start_pos:start_pos + num_bytes])
        else:
            first_part = bytes(self.buffer[start_pos:])
            second_part = bytes(self.buffer[:(start_pos + num_bytes) % self.capacity])
            return first_part + second_part

    @staticmethod
    def calculate_rms(data: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy of 16-bit PCM audio."""
        if not data:
            return 0.0
        count = len(data) // 2
        if count == 0:
            return 0.0

        sum_squares = 0.0
        for i in range(0, len(data) - 1, 2):
            sample = int.from_bytes(data[i:i+2], byteorder="little", signed=True)
            sum_squares += sample * sample

        return math.sqrt(sum_squares / count)
