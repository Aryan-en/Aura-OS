"""
AURA OS — Core System Configuration
Authoritative settings container adhering to Pydantic v2 specifications.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


def get_default_socket_path() -> Path:
    """
    Derive the secure default Unix Domain Socket path.
    Prefers $XDG_RUNTIME_DIR/aura/aura.sock (Linux /run/user/<uid>/aura/aura.sock),
    then ~/.local/share/aura/aura.sock,
    then /tmp/aura-<user>/aura.sock.
    """
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        return Path(xdg_runtime) / "aura" / "aura.sock"

    home = Path.home()
    user = getpass.getuser()
    local_share = home / ".local" / "share" / "aura"
    try:
        local_share.mkdir(parents=True, exist_ok=True, mode=0o700)
        return local_share / "aura.sock"
    except Exception:
        fallback_dir = Path(f"/tmp/aura-{user}")
        fallback_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        return fallback_dir / "aura.sock"


class SocketConfig(BaseModel):
    """Unix Domain Socket IPC configuration."""
    socket_path: Path = Field(default_factory=get_default_socket_path)
    max_payload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    client_timeout_sec: float = Field(default=30.0, gt=0.0)


class VoiceConfig(BaseModel):
    """Voice subsystem configuration."""
    sample_rate: int = Field(default=16000, description="Audio sampling rate in Hz")
    channels: int = Field(default=1, description="Audio channels (mono)")
    vad_silence_ms: int = Field(default=300, description="VAD silence cutoff in milliseconds")
    wake_word: str = Field(default="aura", description="Wake word activation string")
    stt_model: str = Field(default="base.en", description="Speech-to-text model identifier")
    tts_voice: str = Field(default="en_US-lessac-medium", description="Piper TTS voice model")


class VisionConfig(BaseModel):
    """Vision & Hand Gesture subsystem configuration."""
    camera_index: int = Field(default=0, description="Video capture device index")
    target_fps: int = Field(default=30, ge=15, le=60)
    detection_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    tracking_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    raycast_fov_deg: float = Field(default=68.0, description="Camera horizontal field of view")


class AgentConfig(BaseModel):
    """Agent runtime execution configuration."""
    max_retry_budget: int = Field(default=3, ge=1, le=10)
    default_timeout_sec: float = Field(default=60.0, gt=0.0)
    sqlite_db_path: Path = Field(
        default_factory=lambda: Path.home() / ".local" / "share" / "aura" / "aura.db"
    )


class SecurityConfig(BaseModel):
    """System security and permission policies."""
    enforce_voice_confirmation: bool = Field(default=True)
    allow_root_execution: bool = Field(default=False)
    isolate_processes_bubblewrap: bool = Field(default=True)


class AuraConfig(BaseModel):
    """Root configuration for AURA OS."""
    environment: str = Field(default="development")
    version: str = Field(default="0.1.0-prealpha")
    socket: SocketConfig = Field(default_factory=SocketConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AuraConfig:
        """
        Load configuration from YAML file or environment overrides.
        Falls back securely to standard defaults if file does not exist.
        """
        if config_path and config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return cls(**data)
        return cls()
