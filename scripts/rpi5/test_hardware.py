#!/usr/bin/env python3
"""
AURA OS — Raspberry Pi 5 Hardware Diagnostics & Environment Verifier
Validates audio, camera, thermals, sandboxing, and IPC prerequisites.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_header(title: str) -> None:
    print(f"\n\033[1;36m=== {title} ===\033[0m")


def check_ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m {msg}")


def check_warn(msg: str) -> None:
    print(f"  \033[33m⚠\033[0m {msg}")


def check_fail(msg: str) -> None:
    print(f"  \033[31m✗\033[0m {msg}")


def check_platform() -> bool:
    print_header("System & Architecture")
    machine = platform.machine()
    system = platform.system()
    print(f"  OS: {system} | Machine Architecture: {machine} | Python: {platform.python_version()}")

    if machine in ("aarch64", "arm64"):
        check_ok(f"ARM64 architecture verified ({machine})")
    else:
        check_warn(f"Running on {machine}. Production target is aarch64 (Raspberry Pi 5).")

    # Check device tree for Raspberry Pi model
    dt_model = Path("/proc/device-tree/model")
    if dt_model.exists():
        try:
            model_name = dt_model.read_text(encoding="utf-8").strip("\x00")
            check_ok(f"Board Model: {model_name}")
            if "Raspberry Pi 5" in model_name:
                check_ok("Confirmed Raspberry Pi 5 hardware.")
        except Exception as e:
            check_warn(f"Could not read device tree model: {e}")
    else:
        check_warn("Not running directly on bare-metal Raspberry Pi or /proc/device-tree not exposed.")

    # Check Thermal Temperature
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        try:
            temp_c = int(temp_path.read_text().strip()) / 1000.0
            if temp_c < 70.0:
                check_ok(f"SoC Temperature: {temp_c:.1f}°C (Normal operating range)")
            elif temp_c < 82.0:
                check_warn(f"SoC Temperature: {temp_c:.1f}°C (Elevated, Active Cooler recommended)")
            else:
                check_fail(f"SoC Temperature: {temp_c:.1f}°C (Thermal throttling zone!)")
        except Exception:
            pass

    return True


def check_audio() -> bool:
    print_header("Audio Subsystem (PipeWire / ALSA)")
    pw_cli = shutil.which("pw-cli")
    arecord = shutil.which("arecord")
    aplay = shutil.which("aplay")

    if pw_cli:
        check_ok("PipeWire command line tools available.")
    else:
        check_warn("pw-cli not found. Ensure pipewire packages are installed.")

    # Check capture devices
    if arecord:
        try:
            res = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=3)
            if "card" in res.stdout:
                check_ok("Audio capture devices detected (Microphone available):")
                for line in res.stdout.strip().splitlines()[:4]:
                    print(f"    {line}")
            else:
                check_warn("No recording audio cards found! Note: Pi 5 requires a USB mic, I2S HAT, or USB webcam.")
        except Exception as e:
            check_warn(f"Could not query audio capture devices: {e}")

    # Check playback devices
    if aplay:
        try:
            res = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=3)
            if "card" in res.stdout:
                check_ok("Audio playback devices detected (Speaker/HDMI available):")
                for line in res.stdout.strip().splitlines()[:4]:
                    print(f"    {line}")
            else:
                check_warn("No playback audio devices found. Check HDMI or USB audio.")
        except Exception as e:
            check_warn(f"Could not query playback devices: {e}")

    return True


def check_cameras() -> bool:
    print_header("Vision Subsystem (Camera)")
    video_devices = list(Path("/dev").glob("video*"))
    if video_devices:
        check_ok(f"Found {len(video_devices)} video node(s): {[str(d) for d in video_devices]}")
        # Test OpenCV video capture if installed
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    check_ok("OpenCV successfully grabbed a frame from /dev/video0.")
                else:
                    check_warn("Opened /dev/video0 but failed to read frame.")
            else:
                check_warn("Could not open /dev/video0 via OpenCV.")
        except ImportError:
            check_ok("OpenCV not yet imported in current env. Ensure 'opencv-python-headless' is installed.")
        except Exception as e:
            check_warn(f"Camera test note: {e}")
    else:
        check_warn("No /dev/video* devices found. Connect a USB webcam or enable Pi Camera Module in config.txt.")

    return True


def check_security_sandbox() -> bool:
    print_header("Sandboxing (Bubblewrap)")
    bwrap = shutil.which("bwrap")
    if bwrap:
        check_ok("bubblewrap binary is present.")
        try:
            res = subprocess.run([bwrap, "--version"], capture_output=True, text=True, timeout=2)
            check_ok(f"Bubblewrap version: {res.stdout.strip()}")
            # Simple test to confirm unprivileged user namespaces
            test_run = subprocess.run(
                [bwrap, "--ro-bind", "/usr", "/usr", "--proc", "/proc", "--dev", "/dev", "true"],
                capture_output=True,
                timeout=3,
            )
            if test_run.returncode == 0:
                check_ok("Bubblewrap unprivileged sandboxing works correctly.")
            else:
                check_warn(f"Bubblewrap test failed (code {test_run.returncode}). Check kernel unprivileged userns.")
        except Exception as e:
            check_warn(f"Could not execute bubblewrap test: {e}")
    else:
        check_warn("bwrap not installed. Install via: sudo apt install bubblewrap")

    return True


def check_aura_daemon() -> None:
    print_header("AURA OS Daemon & IPC Socket")
    from aura.core.config import get_default_socket_path
    sock = get_default_socket_path()
    print(f"  Target socket: {sock}")
    if sock.exists():
        check_ok("aurad socket exists and is active.")
    else:
        check_warn("aurad socket does not exist. (Start the daemon via: systemctl --user start aura-core)")


def main() -> int:
    print("\033[1m========================================================\033[0m")
    print("\033[1m     AURA OS — Raspberry Pi 5 Hardware Diagnostics      \033[0m")
    print("\033[1m========================================================\033[0m")

    check_platform()
    check_audio()
    check_cameras()
    check_security_sandbox()
    check_aura_daemon()

    print("\n\033[1;32mDiagnostics scan completed.\033[0m\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
