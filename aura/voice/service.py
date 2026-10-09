"""
AURA OS — Voice Subsystem Coordination Service
Integrates audio stream, wake-word detector, VAD, STT, and TTS with Agent runtime.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from aura.agents.manager import AgentManager
from aura.core.logger import logger
from aura.voice.buffer import AudioRingBuffer
from aura.voice.stt import SpeechToText
from aura.voice.tts import TextToSpeech
from aura.voice.vad import VoiceActivityDetector
from aura.voice.wakeword import WakeWordDetector


class VoiceState(str, Enum):
    WAIT_WAKE = "WAIT_WAKE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"


class VoiceService:
    """Manages the full voice interaction pipeline."""

    def __init__(self, agent_manager: Optional[AgentManager] = None) -> None:
        self.state = VoiceState.WAIT_WAKE
        self.ring_buffer = AudioRingBuffer()
        self.wakeword = WakeWordDetector(keyword="aura")
        self.vad = VoiceActivityDetector(silence_timeout_ms=300)
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.agents = agent_manager or AgentManager()
        self.speech_accumulator = bytearray()
        self.on_state_change: Optional[Callable[[VoiceState], None]] = None
        self.history: List[Dict[str, Any]] = []

    def _set_state(self, new_state: VoiceState) -> None:
        self.state = new_state
        logger.debug(f"Voice state transitioned to: {new_state.value}")
        if self.on_state_change:
            self.on_state_change(new_state)

    def get_status(self) -> Dict[str, Any]:
        """Return operational telemetry of the voice pipeline."""
        return {
            "state": self.state.value,
            "wake_word": self.wakeword.keyword,
            "vad_silence_ms": self.vad.silence_timeout_ms,
            "is_speaking": self.tts.is_speaking,
            "stt_model": self.stt.model_name,
            "tts_voice": self.tts.voice,
            "buffer_bytes": len(self.ring_buffer.buffer),
            "recent_interactions": self.history[-10:],
        }

    def start_listening(self) -> None:
        """Explicitly switch to listening state."""
        self.speech_accumulator.clear()
        self.vad.reset()
        self._set_state(VoiceState.LISTENING)

    async def speak_text(self, text: str) -> None:
        """Synthesize and speak arbitrary text aloud."""
        self._set_state(VoiceState.SPEAKING)
        try:
            await self.tts.speak(text)
        finally:
            self._set_state(VoiceState.WAIT_WAKE)

    async def interact(self, prompt: str, speak: bool = True) -> Dict[str, Any]:
        """Process a spoken or dictated prompt, execute agents, and speak back."""
        self._set_state(VoiceState.PROCESSING)
        logger.info(f"Voice interaction initiated: \"{prompt}\"")

        exec_result = await self.agents.execute_goal(prompt)

        if exec_result.get("success"):
            response_text = f"Done: {prompt}."
        else:
            err = exec_result.get("error", "execution error")
            response_text = f"I encountered an error executing that: {err}."

        interaction_entry = {
            "timestamp": time.time(),
            "prompt": prompt,
            "response": response_text,
            "success": exec_result.get("success", False),
            "dag": exec_result.get("dag"),
        }
        self.history.append(interaction_entry)

        if speak:
            self._set_state(VoiceState.SPEAKING)
            try:
                await self.tts.speak(response_text)
            finally:
                self._set_state(VoiceState.WAIT_WAKE)
        else:
            self._set_state(VoiceState.WAIT_WAKE)

        return {
            "event": "GOAL_COMPLETED",
            "prompt": prompt,
            "response": response_text,
            "result": exec_result,
        }

    async def process_audio_chunk(self, chunk: bytes) -> Optional[Dict[str, Any]]:
        """Feed a 16kHz PCM audio chunk into the voice pipeline."""
        self.ring_buffer.write(chunk)

        if self.state == VoiceState.WAIT_WAKE:
            if self.wakeword.process_chunk(chunk):
                logger.info("Wake word detected! Listening for user command...")
                self.speech_accumulator.clear()
                self.vad.reset()
                self._set_state(VoiceState.LISTENING)
                return {"event": "WAKE_DETECTED"}

        elif self.state == VoiceState.LISTENING:
            self.speech_accumulator.extend(chunk)
            speech_ended = self.vad.process_chunk(chunk)
            if speech_ended:
                logger.info("Speech end detected. Processing goal...")
                self._set_state(VoiceState.PROCESSING)

                # Transcribe speech
                transcript = self.stt.transcribe(bytes(self.speech_accumulator))
                logger.info(f"User requested: \"{transcript}\"")

                # Execute goal through AgentManager
                exec_result = await self.agents.execute_goal(transcript)

                # Formulate and speak response
                response_text = (
                    f"Completed: {transcript}"
                    if exec_result["success"]
                    else "I encountered an error executing that task."
                )
                self.history.append({
                    "timestamp": time.time(),
                    "prompt": transcript,
                    "response": response_text,
                    "success": exec_result["success"],
                })

                self._set_state(VoiceState.SPEAKING)
                await self.tts.speak(response_text)

                self._set_state(VoiceState.WAIT_WAKE)
                return {
                    "event": "GOAL_COMPLETED",
                    "transcript": transcript,
                    "result": exec_result,
                    "response": response_text,
                }

        return None

    def emergency_pause(self) -> None:
        """Instantly silence TTS and halt speech interactions (e.g. on Open Palm GEST-003)."""
        logger.warning("Emergency voice pause triggered!")
        self.tts.stop()
        self._set_state(VoiceState.WAIT_WAKE)
        self.speech_accumulator.clear()
