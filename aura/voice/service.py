"""
AURA OS — Voice Subsystem Coordination Service
Integrates audio stream, wake-word detector, VAD, STT, and TTS with Agent runtime.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, Optional
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

    def _set_state(self, new_state: VoiceState) -> None:
        self.state = new_state
        logger.debug(f"Voice state transitioned to: {new_state.value}")
        if self.on_state_change:
            self.on_state_change(new_state)

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
                response_text = f"Completed: {transcript}" if exec_result["success"] else "I encountered an error executing that task."
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
