"""
AURA OS — Speech-To-Text
Backends: faster-whisper (local, 'full' profile) or Gemini (cloud, 'lite' profile).
`auto` prefers local Whisper when installed, then Gemini, else disabled.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from aura.core.logger import logger


class SpeechToText:
    def __init__(
        self,
        model_name: str = "base.en",
        backend: str = "auto",
        sample_rate: int = 16000,
    ) -> None:
        self.model_name = model_name
        self.requested_backend = backend
        self.sample_rate = sample_rate
        self._mock_transcript: Optional[str] = None
        self._whisper: Any = None
        self._gemini: Any = None
        self._backend: Optional[str] = None

    # -- test / simulation hook
    def set_mock_transcript(self, transcript: str) -> None:
        self._mock_transcript = transcript

    def _gemini_client(self) -> Any:
        if self._gemini is None:
            from aura.agents.gemini import GeminiClient

            self._gemini = GeminiClient(timeout_sec=25.0)
        return self._gemini

    @property
    def backend(self) -> str:
        """Resolved backend name: whisper | gemini | none."""
        if self._backend is None:
            want = self.requested_backend
            if want in ("auto", "whisper"):
                try:
                    import faster_whisper  # noqa: F401

                    self._backend = "whisper"
                except ImportError:
                    self._backend = "none"
                    if want == "whisper":
                        logger.warning("stt_backend=whisper but faster-whisper is not installed.")
            if self._backend in (None, "none") and want in ("auto", "gemini"):
                self._backend = "gemini" if self._gemini_client().is_configured() else "none"
            self._backend = self._backend or "none"
            logger.info(f"STT backend: {self._backend}")
        return self._backend

    def transcribe(self, pcm_bytes: bytes) -> str:
        """Blocking transcription of raw 16 kHz mono PCM. Returns '' if nothing was recognised."""
        if self._mock_transcript is not None:
            text, self._mock_transcript = self._mock_transcript, None
            return text
        try:
            if self.backend == "whisper":
                return self._transcribe_whisper(pcm_bytes)
            if self.backend == "gemini":
                return self._gemini_client().transcribe(pcm_bytes, self.sample_rate)
        except Exception as e:
            logger.warning(f"STT failed ({self.backend}): {e}")
        return ""

    def _transcribe_whisper(self, pcm: bytes) -> str:
        import numpy as np
        from faster_whisper import WhisperModel

        if self._whisper is None:
            self._whisper = WhisperModel(
                self.model_name, device="cpu", compute_type="int8",
                cpu_threads=int(os.environ.get("AURA_STT_THREADS", "4")),
            )
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._whisper.transcribe(audio, language="en", beam_size=1, vad_filter=False)
        return " ".join(s.text.strip() for s in segments).strip()
