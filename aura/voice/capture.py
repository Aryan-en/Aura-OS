"""
AURA OS — Microphone Capture
Streams 16 kHz mono S16_LE PCM from the system microphone using `arecord` (ALSA, the Pi
default) or SoX `rec` (macOS/dev). No Python audio dependencies, so it runs on a minimal image.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import AsyncIterator, List, Optional

from aura.core.logger import logger

CHUNK_BYTES = 1280  # 40 ms @ 16 kHz, 16-bit mono


def build_capture_command(sample_rate: int = 16000, device: Optional[str] = None) -> Optional[List[str]]:
    if shutil.which("arecord"):
        cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(sample_rate), "-c", "1"]
        if device:
            cmd += ["-D", device]
        return cmd
    if shutil.which("rec"):
        return ["rec", "-q", "-t", "raw", "-b", "16", "-e", "signed-integer", "-c", "1",
                "-r", str(sample_rate), "-"]
    return None


class MicCapture:
    """Async iterator over fixed-size PCM chunks. Restarts the recorder if it dies."""

    def __init__(self, sample_rate: int = 16000, device: Optional[str] = None) -> None:
        self.sample_rate = sample_rate
        self.device = device
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._stopped = False

    @property
    def available(self) -> bool:
        return build_capture_command(self.sample_rate, self.device) is not None

    async def chunks(self) -> AsyncIterator[bytes]:
        backoff = 1.0
        while not self._stopped:
            cmd = build_capture_command(self.sample_rate, self.device)
            if cmd is None:
                logger.error("No audio capture tool found (install alsa-utils: arecord).")
                return
            self._proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
            assert self._proc.stdout is not None
            got_data = False
            try:
                while not self._stopped:
                    data = await self._proc.stdout.readexactly(CHUNK_BYTES)
                    got_data = True
                    backoff = 1.0
                    yield data
            except asyncio.IncompleteReadError:
                pass
            finally:
                self._kill()
            if self._stopped:
                return
            logger.warning(f"Microphone stream ended{'' if got_data else ' immediately'}; retrying in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15.0)

    def _kill(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass

    def stop(self) -> None:
        self._stopped = True
        self._kill()
