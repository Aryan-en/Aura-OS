#!/usr/bin/env python3
"""AURA OS — Pi doctor: checks everything between the microphone and the TV, and says what to fix."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

G, R, Y, X = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m⚠\033[0m", ""
problems = 0


def out(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return ""


def check(ok: bool, good: str, bad: str, warn_only: bool = False) -> None:
    global problems
    if ok:
        print(f"  {G} {good}")
    else:
        print(f"  {Y if warn_only else R} {bad}")
        problems += 0 if warn_only else 1


from aura.core.config import AuraConfig  # noqa: E402
from aura.core.hardware import detect_hardware  # noqa: E402

hw = detect_hardware()
cfg = AuraConfig.load()
print(f"\nBoard      : {hw.model}  ({hw.ram_mb} MB, {hw.cores} cores) -> profile '{hw.profile}'")
check(hw.arch in ("aarch64", "arm64", "x86_64"), f"architecture {hw.arch}", "32-bit OS: install 64-bit Raspberry Pi OS")

print("\nAudio in (microphone)")
cap = out(["arecord", "-l"])
check("card" in cap, "capture device found", "no microphone found: plug in a USB mic/webcam (Pi 3B+ has no mic input)")
if cap:
    print("    " + "\n    ".join(l for l in cap.splitlines() if l.startswith("card")))

print("\nAudio out (speakers / HDMI)")
play = out(["aplay", "-l"])
check("card" in play, "playback device found", "no playback device: check HDMI cable / set voice.output_device")
if play:
    print("    " + "\n    ".join(l for l in play.splitlines() if l.startswith("card")))
check(bool(shutil.which("espeak-ng") or shutil.which("piper")), "text-to-speech engine present",
      "no TTS engine: sudo apt install espeak-ng")

print("\nSpeech / reasoning")
from aura.agents.gemini import GeminiClient  # noqa: E402

g = GeminiClient()
check(g.is_configured(), f"Gemini key present (model {g.model})",
      f"no Gemini key: put GEMINI_API_KEY=... in {Path.home()}/.config/aura/secrets.env",
      warn_only=hw.profile == "full")
if g.is_configured():
    r = g.test_connection()
    check(r["success"], "Gemini reachable", f"Gemini call failed: {r.get('error', '')[:120]}")
try:
    import faster_whisper  # noqa: F401
    check(True, "faster-whisper installed (local STT)", "")
except ImportError:
    check(hw.profile == "lite", "cloud STT in use (lite profile)",
          "faster-whisper not installed and profile is 'full': pip install '.[rpi]'", warn_only=True)

print("\nServices")
for unit in ("aura-core", "aura-ui", "aura-kiosk"):
    state = out(["systemctl", "is-active", unit]).strip() or "unknown"
    check(state == "active", f"{unit}: active", f"{unit}: {state}  (journalctl -u {unit} -n 30)", warn_only=unit == "aura-kiosk")
try:
    urllib.request.urlopen("http://127.0.0.1:8765/api/telemetry", timeout=3)
    check(True, "HUD answers on :8765", "")
except Exception as e:
    check(False, "", f"HUD not reachable: {e}")

print("\nHealth")
vc = out(["vcgencmd", "get_throttled"]).strip()
if vc:
    val = int(vc.split("=")[1], 16)
    check(val == 0, "no under-voltage/throttling", f"throttled flags {hex(val)}: use a 5V/2.5A+ supply, add cooling")
try:
    t = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    check(t < 75, f"temperature {t:.0f}°C", f"temperature {t:.0f}°C is high: add a heatsink/fan")
except OSError:
    pass

print(f"\n{'All good.' if not problems else f'{problems} problem(s) found — fix the ✗ lines above.'}\n")
sys.exit(1 if problems else 0)
