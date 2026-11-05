"""
AURA OS — Hardware Detection
Identifies the host board and picks a resource profile ("lite" for 1 GB-class boards,
"full" for boards able to run local speech and vision models).
"""

from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class HardwareInfo:
    model: str          # e.g. "Raspberry Pi 3 Model B Plus Rev 1.3" or "Darwin arm64"
    board: str          # "rpi3" | "rpi4" | "rpi5" | "generic"
    ram_mb: int
    cores: int
    arch: str

    @property
    def profile(self) -> str:
        """'lite' = cloud-assisted, no local ML; 'full' = local-first."""
        if self.board in ("rpi3", "rpi2", "rpi1", "rpizero"):
            return "lite"
        if self.ram_mb and self.ram_mb < 3000:
            return "lite"
        return "full"

    @property
    def config_name(self) -> str:
        return {"rpi3": "rpi3.yaml", "rpi5": "rpi5.yaml"}.get(
            self.board, "rpi3.yaml" if self.profile == "lite" else "rpi5.yaml"
        )


def _read_ram_mb() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    try:  # macOS / other POSIX
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return int(pages * size / (1024 * 1024))
    except (ValueError, OSError, AttributeError):
        return 0


def _classify(model: str) -> str:
    m = model.lower()
    if "raspberry pi 5" in m:
        return "rpi5"
    if "raspberry pi 4" in m or "raspberry pi 400" in m:
        return "rpi4"
    if re.search(r"raspberry pi 3", m):
        return "rpi3"
    if "raspberry pi zero" in m:
        return "rpizero"
    if "raspberry pi 2" in m:
        return "rpi2"
    if "raspberry pi" in m:
        return "rpi1"
    return "generic"


def detect_hardware(model_path: Optional[Path] = None) -> HardwareInfo:
    """Detect the current board. `AURA_PROFILE=lite|full` overrides the profile choice."""
    path = model_path or Path("/proc/device-tree/model")
    model = ""
    try:
        model = path.read_bytes().replace(b"\0", b"").decode("utf-8", "replace").strip()
    except OSError:
        pass
    if not model:
        model = f"{platform.system()} {platform.machine()}"

    info = HardwareInfo(
        model=model,
        board=_classify(model),
        ram_mb=_read_ram_mb(),
        cores=os.cpu_count() or 1,
        arch=platform.machine(),
    )
    override = os.environ.get("AURA_PROFILE", "").lower()
    if override in ("lite", "full"):
        board = "rpi3" if override == "lite" else "rpi5"
        return HardwareInfo(info.model, board, info.ram_mb, info.cores, info.arch)
    return info
