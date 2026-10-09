"""
AURA OS — Google Gemini Model Gateway
Provides high-parameter reasoning and dynamic goal decomposition via Google Gemini API.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from aura.core.logger import logger


class GeminiClient:
    """Client for Google Gemini REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: float = 20.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or self._load_key_from_config()
        self.model = model or self._load_model_from_config() or "gemini-3.8-flash"
        self.timeout_sec = timeout_sec

    @staticmethod
    def _load_key_from_config() -> Optional[str]:
        try:
            from aura.core.config import AuraConfig

            cfg = AuraConfig.load()
            if hasattr(cfg, "gemini") and cfg.gemini.api_key:
                return cfg.gemini.api_key
        except Exception:
            pass
        return None

    @staticmethod
    def _load_model_from_config() -> Optional[str]:
        try:
            from aura.core.config import AuraConfig

            cfg = AuraConfig.load()
            if hasattr(cfg, "gemini") and cfg.gemini.model:
                return cfg.gemini.model
        except Exception:
            pass
        return None

    def is_configured(self) -> bool:
        """Returns True if an API key is present."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def test_connection(self) -> Dict[str, Any]:
        """Test API key validity with a lightweight verification prompt."""
        if not self.is_configured():
            return {"success": False, "error": "No Gemini API key provided or configured."}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": "Reply with the single word: PONG"}]}],
            "generationConfig": {
                "maxOutputTokens": 10,
                "temperature": 0.0,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    return {
                        "success": True,
                        "model": self.model,
                        "response": text,
                        "message": f"Successfully connected to Gemini API ({self.model})",
                    }
                return {"success": False, "error": "No candidate response returned from Gemini API."}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"Gemini API HTTP Error {e.code}: {err_body}")
            return {"success": False, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            logger.error(f"Gemini API connection error: {e}")
            return {"success": False, "error": str(e)}

    def plan_goal(
        self,
        goal_prompt: str,
        available_tools: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Use Google Gemini to decompose natural language user goals into a structured Task DAG.
        Returns a list of task specifications or None if planning failed.
        """
        if not self.is_configured():
            return None

        tools_summary = []
        for t in available_tools:
            name = t.get("name")
            desc = t.get("description")
            params = t.get("parameters", {})
            tools_summary.append(f"- {name}: {desc} | parameters: {json.dumps(params)}")
        tools_str = "\n".join(tools_summary)

        system_instruction = (
            "You are the central autonomous goal planner for AURA OS, an AI-native Linux operating environment.\n"
            "Given the user's goal, decompose it into an ordered list of tasks to execute using the available system tools.\n"
            f"Available Tools in Capability Registry:\n{tools_str}\n\n"
            "Rules:\n"
            "1. ONLY use tools listed in the Capability Registry above.\n"
            "2. For creating folders, use filesystem.mkdir.\n"
            "3. For writing files, use filesystem.write_file.\n"
            "4. For reading files, use filesystem.read_file.\n"
            "5. For running terminal commands, use terminal.run_command.\n"
            "6. Expand '~' paths cleanly into user directories (e.g. ~/Desktop/...). \n"
            "7. Return ONLY a valid JSON array of objects conforming to:\n"
            "[\n"
            "  {\n"
            '    "title": "Clear description of step",\n'
            '    "tool_name": "exact.tool_name",\n'
            '    "params": {"param_key": "param_value"},\n'
            '    "dependencies": []\n'
            "  }\n"
            "]"
        )

        user_content = f"User Goal: {goal_prompt}"

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": f"{system_instruction}\n\n{user_content}"}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if not candidates:
                    return None
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

                text_clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
                text_clean = re.sub(r"\s*```$", "", text_clean, flags=re.MULTILINE).strip()

                parsed = json.loads(text_clean)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "tasks" in parsed and isinstance(parsed["tasks"], list):
                    return parsed["tasks"]
                return None
        except Exception as e:
            logger.warning(f"Gemini goal planning call failed: {e}")
            return None
