"""
Unit tests for AURA OS Voice Subsystem.
"""

import asyncio
from aura.voice.buffer import AudioRingBuffer
from aura.voice.service import VoiceService, VoiceState


def test_audio_ring_buffer_write_and_recent() -> None:
    buf = AudioRingBuffer(capacity_bytes=100)
    data = b"\x01\x02\x03\x04\x05"
    buf.write(data)
    assert buf.get_recent(5) == data

    # Overflow buffer
    long_data = bytes([i % 256 for i in range(150)])
    buf.write(long_data)
    assert len(buf.get_recent(100)) == 100
    assert buf.get_recent(10) == long_data[-10:]


def test_rms_calculation() -> None:
    silent = b"\x00" * 320
    assert AudioRingBuffer.calculate_rms(silent) == 0.0

    loud_sample = (1000).to_bytes(2, byteorder="little", signed=True) * 160
    rms = AudioRingBuffer.calculate_rms(loud_sample)
    assert rms > 0.0


def test_voice_pipeline_full_cycle() -> None:
    async def _run() -> None:
        service = VoiceService()
        assert service.state == VoiceState.WAIT_WAKE

        # 1. Trigger wake word
        service.wakeword.inject_trigger()
        silent_chunk = b"\x00" * 320
        res = await service.process_audio_chunk(silent_chunk)
        assert res is not None
        assert res["event"] == "WAKE_DETECTED"
        assert service.state == VoiceState.LISTENING

        # 2. Inject loud speech audio chunks
        loud_chunk = (2000).to_bytes(2, byteorder="little", signed=True) * 160
        for _ in range(5):
            await service.process_audio_chunk(loud_chunk)
        assert service.state == VoiceState.LISTENING

        # 3. Simulate speech pause (VAD silence > 300ms)
        service.stt.set_mock_transcript("create a folder called VoiceTest on my Desktop")
        # Advance time by setting last speech time in past
        service.vad.last_speech_time = service.vad.last_speech_time - 0.5 if service.vad.last_speech_time else 0.0

        res_done = await service.process_audio_chunk(silent_chunk)
        assert res_done is not None
        assert res_done["event"] == "GOAL_COMPLETED"
        assert res_done["transcript"] == "create a folder called VoiceTest on my Desktop"
        assert service.state == VoiceState.WAIT_WAKE

        # 4. Emergency pause
        service.emergency_pause()
        assert service.tts.is_speaking is False

    asyncio.run(_run())
