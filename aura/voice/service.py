"""
AURA OS — Voice Service
Always-on pipeline: mic -> wake word -> VAD -> STT -> Brain -> TTS, with half-duplex echo
protection, follow-up questions, voice confirmation of risky actions, and HUD events.
"""

from __future__ import annotations

import asyncio
import re
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from aura.agents.brain import Brain
from aura.agents.manager import AgentManager
from aura.agents.permissions import parse_decision
from aura.core.config import AuraConfig
from aura.core.events import bus
from aura.core.logger import logger
from aura.voice.buffer import AudioRingBuffer
from aura.voice.stt import SpeechToText
from aura.voice.tts import TextToSpeech
from aura.voice.vad import VoiceActivityDetector
from aura.voice.wakeword import WakeWordDetector

_STOP = re.compile(r"^\s*(?:stop|quiet|be quiet|shut up|silence|enough|never mind|cancel that)\W*$", re.I)
BYTES_PER_SEC = 16000 * 2


class VoiceState(str, Enum):
    WAIT_WAKE = "WAIT_WAKE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"


class VoiceService:
    def __init__(
        self,
        agent_manager: Optional[AgentManager] = None,
        config: Optional[AuraConfig] = None,
        brain: Optional[Brain] = None,
    ) -> None:
        cfg = (config or AuraConfig.load()).voice
        self.cfg = cfg
        self.state = VoiceState.WAIT_WAKE
        self.ring_buffer = AudioRingBuffer()
        self.wakeword = WakeWordDetector(keyword=cfg.wake_word, backend=cfg.wake_backend)
        self.wake_phrases = list(dict.fromkeys(
            WakeWordDetector.default_phrases(cfg.wake_word) + [p.lower() for p in cfg.wake_phrases]
        ))
        self.vad = VoiceActivityDetector(
            energy_threshold=cfg.energy_threshold, silence_timeout_ms=cfg.vad_silence_ms
        )
        self.stt = SpeechToText(model_name=cfg.stt_model, backend=cfg.stt_backend, sample_rate=cfg.sample_rate)
        self.tts = TextToSpeech(voice=cfg.tts_voice, backend=cfg.tts_backend if cfg.tts_backend != "auto" else None,
                                output_device=cfg.output_device)
        self.agents = agent_manager or AgentManager()
        self.brain = brain or Brain(self.agents)
        self.speech_accumulator = bytearray()
        self.on_state_change: Optional[Callable[[VoiceState], None]] = None
        self.history: List[Dict[str, Any]] = []
        self._listen_deadline = 0.0
        self._cooldown_until = 0.0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._preroll = int(0.4 * BYTES_PER_SEC)
        self._max_bytes = int(cfg.max_utterance_sec * BYTES_PER_SEC)
        bus.subscribe(self._on_bus_event)

    # ------------------------------------------------------------------ state
    def _set_state(self, new_state: VoiceState) -> None:
        if new_state != self.state:
            self.state = new_state
            bus.emit("voice.state", state=new_state.value)
            if self.on_state_change:
                self.on_state_change(new_state)

    def _spawn(self, coro: Any) -> "asyncio.Task[Any]":
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def get_status(self) -> Dict[str, Any]:
        from aura.voice.capture import build_capture_command

        gate = self.agents.gate
        return {
            "state": self.state.value,
            "wake_word": self.wakeword.keyword,
            "wake_backend": self.wakeword.backend,
            "vad_silence_ms": self.vad.silence_timeout_ms,
            "vad_threshold": round(self.vad.threshold, 1),
            "is_speaking": self.tts.is_speaking,
            "stt_backend": self.stt.backend,
            "stt_model": self.stt.model_name,
            "tts_backend": self.tts.backend,
            "tts_voice": self.tts.voice,
            "mic_available": build_capture_command() is not None,
            "buffer_bytes": len(self.ring_buffer.buffer),
            "pending_confirmation": gate.pending if gate else None,
            "recent_interactions": self.history[-10:],
        }

    def start_listening(self, window_sec: float = 8.0) -> None:
        self.speech_accumulator.clear()
        self.vad.reset()
        self._listen_deadline = time.time() + window_sec
        self._set_state(VoiceState.LISTENING)

    def _on_bus_event(self, ev: Dict[str, Any]) -> None:
        """Speak confirmation prompts and open the mic for the answer."""
        if ev["type"] == "confirm.request" and ev.get("voice"):
            try:
                self._spawn(self._ask_confirmation(ev["description"], float(ev.get("timeout", 30))))
            except RuntimeError:
                pass  # no running loop (sync tests)

    async def _ask_confirmation(self, description: str, timeout: float) -> None:
        await self._say(f"Do you want me to {description.split(' (')[0]}? Say confirm or cancel.")
        if self.agents.gate.pending:
            self.start_listening(window_sec=timeout)

    # ------------------------------------------------------------------ speaking
    async def _say(self, text: str) -> None:
        self._set_state(VoiceState.SPEAKING)
        bus.emit("voice.speaking", text=text)
        try:
            await self.tts.speak(text)
        finally:
            self._cooldown_until = time.time() + 0.5  # ignore speaker tail / room echo
            self._set_state(VoiceState.WAIT_WAKE)

    async def speak_text(self, text: str) -> None:
        await self._say(text)

    # ------------------------------------------------------------------ interaction
    async def respond(self, text: str, speak: bool = True) -> Dict[str, Any]:
        """Run text through the brain and (optionally) speak the reply."""
        self._set_state(VoiceState.PROCESSING)
        bus.emit("voice.thinking", text=text)
        try:
            out = await self.brain.handle(text)
        except Exception as e:  # never let one bad request kill the listener
            logger.exception(f"Brain error: {e}")
            out = {"success": False, "reply": "Something went wrong while handling that.", "source": "error"}
        reply = out["reply"]
        entry = {"timestamp": time.time(), "prompt": text, "response": reply,
                 "success": out["success"], "source": out.get("source")}
        self.history.append(entry)
        self.history = self.history[-50:]
        bus.emit("voice.reply", **entry)

        if speak:
            await self._say(reply)
            if reply.rstrip().endswith("?") and self.state == VoiceState.WAIT_WAKE:
                self.start_listening(window_sec=7.0)  # follow-up without wake word
        else:
            self._set_state(VoiceState.WAIT_WAKE)
        return {"event": "GOAL_COMPLETED", "prompt": text, "response": reply,
                "result": out.get("result", out), "transcript": text}

    async def interact(self, prompt: str, speak: bool = True) -> Dict[str, Any]:
        return await self.respond(prompt, speak=speak)

    async def _handle_utterance(self, pcm: bytes, pre_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        self._set_state(VoiceState.PROCESSING)
        text = pre_text if pre_text is not None else await asyncio.to_thread(self.stt.transcribe, pcm)
        text = (text or "").strip()
        bus.emit("voice.transcript", text=text)
        if not text:
            self._set_state(VoiceState.WAIT_WAKE)
            return None
        logger.info(f'User said: "{text}"')

        gate = self.agents.gate
        if gate and gate.pending:
            decision = parse_decision(text)
            if decision is not None:
                gate.resolve(decision, source="voice")
                self._set_state(VoiceState.PROCESSING)
                return {"event": "CONFIRMATION", "approved": decision}
            self.start_listening(window_sec=15.0)  # not a yes/no: keep waiting
            return None
        if _STOP.match(text):
            self.tts.stop()
            self._set_state(VoiceState.WAIT_WAKE)
            return {"event": "STOPPED"}
        return await self.respond(text)

    # ------------------------------------------------------------------ audio path
    def _wake(self) -> Dict[str, Any]:
        logger.info("Wake word detected.")
        self.start_listening()
        bus.emit("voice.wake")
        return {"event": "WAKE_DETECTED"}

    def _collect(self, chunk: bytes) -> bool:
        """Accumulate audio around speech; True when an utterance finished."""
        self.speech_accumulator.extend(chunk)
        ended = self.vad.process_chunk(chunk)
        if not self.vad.is_speaking and not ended and len(self.speech_accumulator) > self._preroll:
            del self.speech_accumulator[: len(self.speech_accumulator) - self._preroll]
        return ended or len(self.speech_accumulator) >= self._max_bytes

    async def process_audio_chunk(self, chunk: bytes) -> Optional[Dict[str, Any]]:
        """Feed a 16 kHz mono PCM chunk. Returns an event dict when something notable happens."""
        self.ring_buffer.write(chunk)
        now = time.time()
        if self.state in (VoiceState.PROCESSING, VoiceState.SPEAKING) or now < self._cooldown_until:
            return None  # half-duplex: never listen to ourselves

        if self.state == VoiceState.WAIT_WAKE:
            if self.wakeword.process_chunk(chunk):
                return self._wake()
            if not self.wakeword.uses_transcript or self.stt.backend == "none":
                return None
            if not self._collect(chunk):
                return None
            pcm, self.speech_accumulator = bytes(self.speech_accumulator), bytearray()
            self.vad.reset()
            if not (0.5 * BYTES_PER_SEC <= len(pcm) <= 6 * BYTES_PER_SEC):
                return None
            text = await asyncio.to_thread(self.stt.transcribe, pcm)
            rest = WakeWordDetector.match_phrase(text or "", self.wake_phrases)
            if rest is None:
                return None
            if not rest:
                return self._wake()
            bus.emit("voice.wake")
            self._spawn(self._handle_utterance(b"", pre_text=rest))
            return {"event": "WAKE_WITH_COMMAND", "transcript": rest}

        # LISTENING
        if not self.vad.is_speaking and now > self._listen_deadline and len(self.speech_accumulator) <= self._preroll:
            self.speech_accumulator.clear()
            self._set_state(VoiceState.WAIT_WAKE)
            return {"event": "LISTEN_TIMEOUT"}
        if self._collect(chunk):
            pcm, self.speech_accumulator = bytes(self.speech_accumulator), bytearray()
            self.vad.reset()
            task = self._spawn(self._handle_utterance(pcm))
            return {"event": "UTTERANCE_CAPTURED", "task": task}
        return None

    async def run(self, capture: Any) -> None:
        """Main loop: pump microphone chunks through the pipeline until cancelled."""
        logger.info(f"Voice online (wake={self.wakeword.backend}, stt={self.stt.backend}, tts={self.tts.backend})")
        bus.emit("voice.state", state=self.state.value)
        async for chunk in capture.chunks():
            await self.process_audio_chunk(chunk)

    def emergency_pause(self) -> None:
        """Silence TTS and reset to idle (open-palm gesture / HUD button)."""
        logger.warning("Emergency voice pause triggered!")
        self.tts.stop()
        self.speech_accumulator.clear()
        self._set_state(VoiceState.WAIT_WAKE)
