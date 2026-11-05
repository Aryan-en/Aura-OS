# Running Aura OS on a Raspberry Pi → TV

Aura is a Linux userspace OS layer (not a custom kernel): Raspberry Pi OS Lite provides the kernel and
drivers; Aura adds the voice daemon, brain and a fullscreen HUD that boots straight to HDMI.

## Which profile?

| Board | Profile | How it works |
| :--- | :--- | :--- |
| **Pi 3B+ (1 GB)** | `lite` | Mic + wake + VAD local. **Speech-to-text and reasoning in the cloud (Gemini).** Flat HUD (no blur). No hand tracking. |
| Pi 4 (≥4 GB) / **Pi 5** | `full` | Local Whisper + Piper, MediaPipe gestures, Gemini optional for harder questions. |

The installer detects the board. Override with `AURA_PROFILE=lite|full`.

**Lite needs internet and a Gemini key** (free tier works: https://aistudio.google.com/apikey). Your speech
audio is sent to Google for transcription. With the built-in transcript wake word, *every* speech burst heard
while idle is sent too; install openWakeWord (say "Hey Jarvis") to keep idle audio local.

## Hardware checklist

- Pi 3B+, **official 5 V / 2.5 A+ supply** (under-voltage causes freezes), 16 GB+ A1/A2 microSD, heatsink.
- **A USB microphone** — the Pi 3B+ has no mic input. A USB webcam with a mic works.
- HDMI to the TV. Audio plays through the TV (HDMI) by default; the 3.5 mm jack also works.
- Wi-Fi/Ethernet. (Pi 3B+ shares USB 2.0 with Ethernet; keep USB devices minimal.)

## Install (≈15 min)

1. Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In the ⚙ settings set hostname, user, Wi-Fi, enable SSH.
   *(Do not use the Ubuntu desktop ISO in this repo — that is for the UTM VM and is too heavy for 1 GB.)*
2. Boot, SSH in, then:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   git clone https://github.com/Aryan-en/Aura-OS.git && cd Aura-OS
   bash scripts/pi/install.sh        # asks for your Gemini key
   sudo reboot
   ```
3. The TV shows the Aura HUD. Say **"Aura, what time is it?"** (or press the orb).

If sound goes to the wrong output: `aplay -l`, then set `voice.output_device: "plughw:0,1"` in
`~/.config/aura/aura.yaml` and `sudo systemctl restart aura-core`.

## Voice commands that work out of the box (no cloud needed)

"what time is it", "what's the date", "open files / settings / system / terminal / home …",
"volume up/down/set volume to 40", "mute", "system status", "reboot", "shut down".
With a Gemini key anything else is answered conversationally and can run tools
("create a folder called Notes in Documents"). **Shell commands, deletions and power actions ask first:**
say "confirm" / "cancel", or use the on-screen buttons.

## Operating it

```bash
make rpi-doctor                    # mic, speakers, Gemini, services, temperature, throttling
journalctl -u aura-core -f         # live voice pipeline log
sudo systemctl restart aura-core aura-ui aura-kiosk
```

Reach the HUD from your laptop (off by default; HUD is loopback-only): set `ui.host: 0.0.0.0` in
`~/.config/aura/aura.yaml`, restart `aura-ui`, then open the `?token=…` URL printed by
`journalctl -u aura-ui`. The terminal panel stays off unless `ui.allow_terminal: true`.

## Known limits (honest list)

- Not yet exercised on physical Pi hardware by the author of this change; first boot may need tuning
  (mic gain → `voice.energy_threshold`, HDMI device name). Run `make rpi-doctor` first.
- Half-duplex: Aura doesn't listen while it speaks, so you can't interrupt by voice (use the orb or open palm on Pi 5).
- Wake word: built-in openWakeWord phrase is "Hey Jarvis"; "Aura" uses transcript matching until a custom model is trained.
- No camera/gesture loop yet (`BUG-007`). Several HUD panels (smart home, automations) are still static demos.
- Chromium on 1 GB is tight. If the HUD reloads/blanks, enable zram (installer does) or try a lighter kiosk browser (`cog`).
