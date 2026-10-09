"""
Unit tests for AURA OS Configuration Subsystem.
"""

from pathlib import Path

from aura.core.config import AuraConfig, get_default_socket_path


def test_default_socket_path() -> None:
    path = get_default_socket_path()
    assert isinstance(path, Path)
    assert path.name == "aura.sock"


def test_default_config() -> None:
    config = AuraConfig()
    assert config.version == "0.1.0-prealpha"
    assert config.socket.max_payload_bytes == 10 * 1024 * 1024
    assert config.voice.sample_rate == 16000
    assert config.voice.wake_word == "aura"
    assert config.vision.target_fps == 30
    assert config.security.enforce_voice_confirmation is True
    assert config.security.allow_root_execution is False


def test_custom_config_override() -> None:
    config = AuraConfig(
        environment="production",
        voice={"sample_rate": 48000, "wake_word": "jarvis"},  # type: ignore[arg-type]
        vision={"camera_backend": "libcamera"},  # type: ignore[arg-type]
    )
    assert config.environment == "production"
    assert config.voice.sample_rate == 48000
    assert config.voice.wake_word == "jarvis"
    assert config.vision.camera_backend == "libcamera"


def test_load_rpi5_config_file() -> None:
    rpi_cfg_file = Path(__file__).parent.parent.parent / "config" / "rpi5.yaml"
    if rpi_cfg_file.exists():
        config = AuraConfig.load(config_path=rpi_cfg_file)
        assert config.environment == "rpi5"
        assert config.voice.stt_model == "base.en"
        assert config.vision.target_fps == 30
        assert config.vision.camera_backend == "v4l2"
