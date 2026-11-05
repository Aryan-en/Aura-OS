"""Tests for hardware detection, wake phrases, VAD, STT selection, permission gate and the Brain."""

import asyncio
import tempfile
from pathlib import Path

from aura.agents.brain import Brain
from aura.agents.gemini import pcm_to_wav
from aura.agents.manager import AgentManager
from aura.agents.permissions import PermissionGate, parse_decision
from aura.core.events import bus
from aura.core.hardware import detect_hardware
from aura.voice.capture import build_capture_command
from aura.voice.stt import SpeechToText
from aura.voice.vad import VoiceActivityDetector
from aura.voice.wakeword import WakeWordDetector


def _model_file(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    f = d / "model"
    f.write_bytes(text.encode() + b"\0")
    return f


def test_hardware_detects_pi3_as_lite() -> None:
    hw = detect_hardware(_model_file("Raspberry Pi 3 Model B Plus Rev 1.3"))
    assert hw.board == "rpi3" and hw.profile == "lite" and hw.config_name == "rpi3.yaml"


def test_hardware_detects_pi5_as_full() -> None:
    hw = detect_hardware(_model_file("Raspberry Pi 5 Model B Rev 1.0"))
    assert hw.board == "rpi5"
    assert hw.config_name == "rpi5.yaml"


def test_wake_phrase_matching() -> None:
    phrases = ["aura", "hey aura", "jarvis"]
    m = WakeWordDetector.match_phrase
    assert m("Aura", phrases) == ""
    assert m("Hey Aura, open files!", phrases) == "open files"
    assert m("okay aura what time is it", phrases) == "what time is it"
    assert m("the aurora borealis", phrases) is None
    assert m("laura is here", phrases) is None


def test_decision_parsing() -> None:
    assert parse_decision("Yes, do it") is True
    assert parse_decision("confirm") is True
    assert parse_decision("cancel that") is False
    assert parse_decision("open files") is None


def test_vad_ignores_clicks_and_ends_real_speech() -> None:
    vad = VoiceActivityDetector(energy_threshold=500, silence_timeout_ms=300)
    loud = (3000).to_bytes(2, "little", signed=True) * 160
    quiet = b"\x00" * 320
    vad.process_chunk(loud)  # instantaneous click
    vad.last_speech_time -= 0.5
    assert vad.process_chunk(quiet) is False  # too short to count as speech
    vad.process_chunk(loud)
    vad.speech_start_time -= 1.0
    vad.last_speech_time -= 0.5
    assert vad.process_chunk(quiet) is True


def test_stt_without_backend_returns_empty_not_canned_text() -> None:
    stt = SpeechToText(backend="gemini")  # AURA_OFFLINE=1 -> not configured
    assert stt.transcribe(b"\x00" * 3200) == ""
    assert stt.backend == "none"


def test_wav_header() -> None:
    wav = pcm_to_wav(b"\x00" * 100)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE" and len(wav) == 144


def test_capture_command_is_optional() -> None:
    cmd = build_capture_command()
    assert cmd is None or cmd[0] in ("arecord", "rec")


def test_gate_denies_on_timeout_and_approves_on_resolve() -> None:
    async def _run() -> None:
        gate = PermissionGate(timeout_sec=0.05)
        assert await gate.request("do a thing") is False
        gate = PermissionGate(timeout_sec=5)
        task = asyncio.create_task(gate.request("do a thing"))
        await asyncio.sleep(0.01)
        assert gate.pending is not None
        assert gate.resolve(True)
        assert await task is True

    asyncio.run(_run())


def test_terminal_goal_requires_confirmation() -> None:
    async def _run() -> None:
        manager = AgentManager(gate=PermissionGate(timeout_sec=0.05))
        res = await manager.execute_goal("run command 'echo hi'")
        assert res["success"] is False  # timed out waiting for approval -> denied
        task = next(iter(res["tasks"].values()))
        assert task["status"] == "CANCELLED"

    asyncio.run(_run())


def test_brain_local_intents_offline() -> None:
    async def _run() -> None:
        brain = Brain(AgentManager())
        start = bus.last_id
        r = await brain.handle("what time is it?")
        assert r["source"] == "local" and r["reply"].startswith("It's")
        r = await brain.handle("open the files")
        assert r["reply"] == "Opening files."
        assert any(e["type"] == "ui.view" and e["view"] == "files" for e in bus.since(start))
        r = await brain.handle("tell me a joke about quantum physics")
        assert r["success"] is False and "offline" in r["reply"]

    asyncio.run(_run())


def test_planner_fallback_never_shells_user_text() -> None:
    from aura.agents.planner import GoalPlanner

    dag = GoalPlanner.plan("hello '; rm -rf ~ #")
    assert all(t.tool_name is None for t in dag.tasks.values())


def test_event_bus_reserved_keys_cannot_be_overwritten() -> None:
    ev = bus.emit("x", id="job-1", type="evil", ts="no")
    assert isinstance(ev["id"], int) and ev["type"] == "x" and isinstance(ev["ts"], float)
