"""
AURA OS — Wake Word
Two strategies:
  * openWakeWord (local, tiny ONNX model, runs continuously) — built-in phrase is "hey jarvis".
  * transcript matching — each speech burst is transcribed and checked for a wake phrase
    (works for any phrase such as "aura", but sends idle speech to the STT backend).
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence

from aura.core.logger import logger


class WakeWordDetector:
    def __init__(self, keyword: str = "aura", sensitivity: float = 0.5, backend: str = "auto") -> None:
        self.keyword = keyword.lower()
        self.sensitivity = sensitivity
        self.requested_backend = backend
        self._activated = False
        self._oww: Any = None
        self._buf = bytearray()
        self._resolved: Optional[str] = None

    @property
    def backend(self) -> str:
        """openwakeword | transcript | none."""
        if self._resolved is None:
            want = self.requested_backend
            self._resolved = "transcript" if want in ("auto", "transcript") else "none"
            if want in ("auto", "openwakeword"):
                try:
                    import openwakeword
                    from openwakeword.model import Model

                    self._oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
                    self._resolved = "openwakeword"
                    if self.keyword not in ("jarvis", "hey_jarvis", "hey jarvis"):
                        logger.info("openWakeWord ships 'hey jarvis'; say that to wake (custom 'aura' needs training).")
                    del openwakeword
                except Exception as e:
                    if want == "openwakeword":
                        logger.warning(f"openWakeWord unavailable: {e}")
        return self._resolved

    @property
    def uses_transcript(self) -> bool:
        return self.backend == "transcript"

    def process_chunk(self, pcm_chunk: bytes) -> bool:
        """Streaming detection (openWakeWord) or synthetic injection. True when triggered."""
        if self._activated:
            self._activated = False
            return True
        if self._resolved is None:
            _ = self.backend
        if self._oww is None:
            return False
        import numpy as np

        self._buf.extend(pcm_chunk)
        frame = 1280 * 2  # openWakeWord expects 80 ms frames
        hit = False
        while len(self._buf) >= frame:
            samples = np.frombuffer(bytes(self._buf[:frame]), dtype=np.int16)
            del self._buf[:frame]
            scores = self._oww.predict(samples)
            if any(v >= max(0.5, self.sensitivity) for v in scores.values()):
                hit = True
                self._oww.reset()
        return hit

    def inject_trigger(self) -> None:
        self._activated = True

    @staticmethod
    def match_phrase(text: str, phrases: Sequence[str]) -> Optional[str]:
        """If `text` starts with a wake phrase return the remaining command ('' if none), else None."""
        cleaned = re.sub(r"[^\w\s']", " ", text.lower()).split()
        joined = " ".join(cleaned)
        for phrase in sorted(phrases, key=len, reverse=True):
            p = phrase.lower().strip()
            if joined == p or joined.startswith(p + " "):
                return joined[len(p):].strip()
        # Allow a leading filler word ("okay aura ...", "hey there aura ...").
        for i in range(1, min(3, len(cleaned))):
            rest = " ".join(cleaned[i:])
            for phrase in phrases:
                p = phrase.lower().strip()
                if rest == p or rest.startswith(p + " "):
                    return rest[len(p):].strip()
        return None

    @staticmethod
    def default_phrases(keyword: str) -> List[str]:
        k = keyword.lower()
        return [k, f"hey {k}", f"ok {k}", f"okay {k}"]
