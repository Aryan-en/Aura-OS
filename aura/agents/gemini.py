"""
AURA OS — Google Gemini Model Gateway
Cloud reasoning, conversation, and speech-to-text via the Gemini REST API.
Uses only the standard library so it runs on minimal (1 GB) boards.
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from aura.core.logger import logger

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"


def pcm_to_wav(pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw 16-bit little-endian PCM in a minimal WAV container."""
    byte_rate = sample_rate * channels * 2
    header = (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, channels * 2, 16)
        + b"data" + struct.pack("<I", len(pcm))
    )
    return header + pcm


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text, flags=re.MULTILINE).strip()


class GeminiClient:
    """Client for the Google Gemini REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or self._cfg("api_key")
        self.model = model or self._cfg("model") or DEFAULT_MODEL
        self.timeout_sec = timeout_sec

    @staticmethod
    def _cfg(field: str) -> Optional[str]:
        try:
            from aura.core.config import AuraConfig

            return getattr(AuraConfig.load().gemini, field, None) or None
        except Exception:
            return None

    def is_configured(self) -> bool:
        if os.environ.get("AURA_OFFLINE") == "1":
            return False
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    # ------------------------------------------------------------------ transport
    def _generate(
        self,
        contents: List[Dict[str, Any]],
        system: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """POST generateContent and return the first candidate's text. Raises on failure."""
        if not self.is_configured():
            raise RuntimeError("No Gemini API key configured.")
        gen_cfg: Dict[str, Any] = {"temperature": temperature}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        if max_tokens:
            gen_cfg["maxOutputTokens"] = max_tokens
        payload: Dict[str, Any] = {"contents": contents, "generationConfig": gen_cfg}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        req = urllib.request.Request(
            f"{API_ROOT}/{self.model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            # Key travels in a header, never in the URL (URLs end up in logs).
            headers={"Content-Type": "application/json", "x-goog-api-key": str(self.api_key)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"Gemini HTTP {e.code}: {body}") from None
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()

    # ------------------------------------------------------------------ features
    def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "No Gemini API key provided or configured."}
        try:
            text = self._generate(
                [{"role": "user", "parts": [{"text": "Reply with the single word: PONG"}]}],
                temperature=0.0,
                max_tokens=10,
            )
            return {
                "success": True,
                "model": self.model,
                "response": text,
                "message": f"Successfully connected to Gemini API ({self.model})",
            }
        except Exception as e:
            logger.error(f"Gemini connection error: {e}")
            return {"success": False, "error": str(e)}

    def generate_text(self, prompt: str, system: Optional[str] = None, json_mode: bool = False,
                      max_tokens: int = 2048) -> str:
        """One-shot text generation (used by the vault compiler and skill audit). Raises on failure."""
        return self._generate([{"role": "user", "parts": [{"text": prompt}]}], system=system,
                              json_mode=json_mode, temperature=0.3, max_tokens=max_tokens)

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> str:
        """Cloud speech-to-text for a raw PCM utterance. Returns '' if no speech."""
        wav = pcm_to_wav(pcm, sample_rate)
        text = self._generate(
            [{
                "role": "user",
                "parts": [
                    {"text": "Transcribe this audio verbatim in English. Output ONLY the spoken words. "
                             "If there is no intelligible speech, output nothing."},
                    {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav).decode()}},
                ],
            }],
            temperature=0.0,
            max_tokens=256,
        )
        return text.strip().strip('"')

    def chat_json(
        self,
        history: List[Dict[str, str]],
        user_text: str,
        system: str,
    ) -> Optional[Dict[str, Any]]:
        """Conversational turn that must return a JSON object. None on failure."""
        contents = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["text"]}]}
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        try:
            raw = self._generate(contents, system=system, json_mode=True, temperature=0.4, max_tokens=600)
            parsed = json.loads(_strip_fences(raw))
            return parsed if isinstance(parsed, dict) else None
        except Exception as e:
            logger.warning(f"Gemini chat failed: {e}")
            return None

    def plan_goal(
        self,
        goal_prompt: str,
        available_tools: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Decompose a goal into an ordered list of tool tasks. None if planning failed."""
        if not self.is_configured():
            return None
        tools_str = "\n".join(
            f"- {t.get('name')}: {t.get('description')} | parameters: {json.dumps(t.get('parameters', {}))}"
            for t in available_tools
        )
        system = (
            "You are the goal planner for AURA OS, an AI-native Linux environment.\n"
            "Decompose the user's goal into an ordered list of tasks using ONLY these tools:\n"
            f"{tools_str}\n\n"
            "Expand '~' to user directories. Return ONLY a JSON array of objects:\n"
            '[{"title": "...", "tool_name": "exact.tool_name", "params": {}, "dependencies": []}]'
        )
        try:
            raw = self._generate(
                [{"role": "user", "parts": [{"text": f"User Goal: {goal_prompt}"}]}],
                system=system,
                json_mode=True,
                temperature=0.1,
            )
            parsed = json.loads(_strip_fences(raw))
        except Exception as e:
            logger.warning(f"Gemini goal planning failed: {e}")
            return None
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("tasks"), list):
            return parsed["tasks"]
        return None
