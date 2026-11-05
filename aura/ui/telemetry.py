"""AURA OS — Host telemetry (CPU, RAM, disk, temperature) for the HUD and system tools."""

from __future__ import annotations

import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_START = time.time()
_last_cpu: Optional[Tuple[int, int]] = None


def _cpu_percent() -> float:
    """CPU utilisation since the previous call (from /proc/stat); load-average fallback."""
    global _last_cpu
    try:
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        vals = [int(x) for x in fields]
        idle, total = vals[3] + vals[4], sum(vals)
        prev, _last_cpu = _last_cpu, (idle, total)
        if prev and total > prev[1]:
            return round(100.0 * (1 - (idle - prev[0]) / (total - prev[1])), 1)
        return 0.0
    except (OSError, ValueError, IndexError):
        try:
            return min(100.0, round(os.getloadavg()[0] / (os.cpu_count() or 1) * 100, 1))
        except OSError:
            return 0.0


def _ram_percent() -> float:
    try:
        mem: Dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            mem[k] = int(v.split()[0])
        return round(100.0 * (1 - mem.get("MemAvailable", mem["MemFree"]) / mem["MemTotal"]), 1)
    except (OSError, ValueError, KeyError):
        pass
    try:  # macOS
        import subprocess

        out = subprocess.check_output(["vm_stat"], text=True, timeout=2)
        page = int(out.split("page size of ")[1].split()[0])
        stats = {ln.split(":")[0]: int(ln.split(":")[1].strip(" .")) for ln in out.splitlines()[1:] if ":" in ln}
        free = (stats.get("Pages free", 0) + stats.get("Pages inactive", 0)
                + stats.get("Pages speculative", 0)) * page
        total = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        return round(100.0 * (1 - free / total), 1)
    except Exception:
        return 0.0


def _temperature_c() -> Optional[float]:
    try:
        return round(int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000, 1)
    except (OSError, ValueError):
        return None


def get_system_telemetry() -> Dict[str, Any]:
    disk = shutil.disk_usage(os.path.expanduser("~"))
    return {
        "cpu": _cpu_percent(),
        "ram": _ram_percent(),
        "disk": round(disk.used / disk.total * 100, 1),
        "temp_c": _temperature_c(),
        "platform": f"{platform.system()} {platform.machine()}",
        "uptime": round(time.time() - _START, 1),
    }
