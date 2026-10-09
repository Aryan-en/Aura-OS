# Running AURA OS on Raspberry Pi 5

This guide provides the authoritative, end-to-end instructions for deploying and running **AURA OS** natively on a **Raspberry Pi 5** single-board computer.

---

## 1. Hardware Overview & Compatibility

The Raspberry Pi 5 is the first Raspberry Pi generation with sufficient multi-core ARM64 compute power and memory bandwidth to run AURA OS's multimodal voice, gesture tracking, and local reasoning pipelines concurrently.

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **SBC Model** | Raspberry Pi 5 (4GB RAM) | Raspberry Pi 5 (8GB or 16GB RAM) |
| **SoC** | Broadcom BCM2712 Quad-Core Cortex-A76 @ 2.4GHz | Broadcom BCM2712 Quad-Core @ 2.4GHz (or overclocked to 2.8GHz) |
| **Cooling** | Passive Heatsink | **Official Raspberry Pi Active Cooler** *(Mandatory for continuous neural inference)* |
| **Storage** | 32GB Class A2 MicroSD card | **PCIe M.2 NVMe SSD** (via Raspberry Pi M.2 HAT+) |
| **Audio Input** | USB microphone or USB webcam microphone | ReSpeaker USB Mic Array or USB Conference Boundary Mic |
| **Audio Output** | HDMI audio to monitor / TV speakers | USB DAC / USB speaker dongle or Bluetooth A2DP |
| **Camera** | Standard UVC USB Webcam (1080p / 720p) | USB Webcam or Raspberry Pi Camera Module 3 (via CSI-2) |
| **Power Supply** | Official 27W USB-C Power Supply (5.1V / 5A) | Official 27W USB-C Power Supply |

> [!IMPORTANT]
> **Crucial Raspberry Pi 5 Audio Note**: The Raspberry Pi 5 does **not** include an analog 3.5mm TRRS audio jack. For voice recognition and Piper speech synthesis, you **must** use a USB audio device (USB microphone + USB speaker or USB DAC), HDMI monitor speakers, or a Bluetooth audio sink.

---

## 2. Operating System Selection

AURA OS requires a **64-bit ARM Linux operating system** (ARM64 / `aarch64`):

1. **Raspberry Pi OS 64-bit (Debian 12 Bookworm)** *(Recommended)*:
   - Includes native PipeWire and WirePlumber audio stack.
   - Default Wayland compositor (Wayfire / Labwc) with OpenGL ES 3.1 & Vulkan 1.2 VideoCore VII hardware acceleration.
2. **Ubuntu 24.04 LTS Desktop/Server for Raspberry Pi (ARM64)**:
   - Upstream Linux 6.8 kernel with systemd and modern Python 3.12 runtime.

Flash your chosen image using the **Raspberry Pi Imager** tool, ensuring the 64-bit version is selected.

---

## 3. Quick-Start Setup (Automated)

### Step 1: Clone the Repository on the Raspberry Pi
Log into your Raspberry Pi via SSH or local terminal:

```bash
git clone https://github.com/Aryan-en/Aura-OS.git
cd Aura-OS
```

### Step 2: Run Automated Provisioning
Run the automated Raspberry Pi 5 setup script or Makefile target:

```bash
make rpi-setup
```

This automated script performs:
1. Architecture validation (`aarch64` check).
2. Installation of all Debian/Ubuntu prerequisites (`pipewire`, `wireplumber`, `bubblewrap`, `libasound2-dev`, `v4l-utils`, `libgl1`, `sqlite3`).
3. User group assignment (`audio`, `video`, `input`).
4. PipeWire user service activation.
5. Systemd user linger enablement (`loginctl enable-linger $USER`) so daemons persist across SSH disconnects.
6. Creation of Python virtual environment (`.venv`) with ARM-optimized packages (`faster-whisper`, `piper-tts`, `openwakeword`, `mediapipe`, `opencv-python-headless`).
7. Installation of systemd user services (`aura-core.service` and `aura-ui.service`).

---

## 4. Hardware Verification & Diagnostics

Before launching the daemons, run the hardware diagnostic script to verify your audio devices, camera nodes, temperature, and sandboxing:

```bash
make rpi-hwcheck
```

Example diagnostics output:
```text
=== System & Architecture ===
  OS: Linux | Machine Architecture: aarch64 | Python: 3.11.2
  ✓ ARM64 architecture verified (aarch64)
  ✓ Board Model: Raspberry Pi 5 Model B Rev 1.0
  ✓ SoC Temperature: 46.2°C (Normal operating range)

=== Audio Subsystem (PipeWire / ALSA) ===
  ✓ PipeWire command line tools available.
  ✓ Audio capture devices detected (Microphone available):
    card 1: Device [USB PnP Audio Device], device 0: USB Audio [USB Audio]
  ✓ Audio playback devices detected (Speaker/HDMI available):
    card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM vc4-hdmi-hifi-0 []

=== Vision Subsystem (Camera) ===
  ✓ Found 2 video node(s): ['/dev/video0', '/dev/video1']
  ✓ OpenCV successfully grabbed a frame from /dev/video0.

=== Sandboxing (Bubblewrap) ===
  ✓ bubblewrap binary is present.
  ✓ Bubblewrap unprivileged sandboxing works correctly.

=== AURA OS Daemon & IPC Socket ===
  Target socket: /run/user/1000/aura/aura.sock
```

---

## 5. Running AURA OS on the Pi

### Option A: Running Interactively in the Terminal

1. **Start the Core Daemon (`aurad`)**:
   ```bash
   make rpi-daemon
   ```
   *Uses the optimized `config/rpi5.yaml` configuration profile.*

2. **Test Communication via CLI** (in a second terminal):
   ```bash
   # Ping daemon and measure UDS latency:
   aura ping

   # Inspect runtime subsystems:
   aura status

   # Submit a natural language task:
   aura goal "create a directory called workspace on my Desktop"
   ```

3. **Launch the Desktop HUD Web Simulator**:
   ```bash
   make rpi-ui
   ```
   The HUD binds to `0.0.0.0:8765`. Open your browser on any computer or phone connected to the same local network:
   `http://<raspberry-pi-ip>:8765`

---

### Option B: Running as Persistent Systemd Background Services

To have AURA OS start automatically on boot and restart if interrupted:

```bash
# Install and enable the user services
make rpi-services-install
systemctl --user enable aura-core aura-ui

# Start both services
make rpi-services-start

# Inspect status
make rpi-services-status
```

#### Monitoring Real-Time Logs
```bash
journalctl --user -u aura-core -f
```

---

## 6. Raspberry Pi 5 Optimization Tuning

The hardware profile is located at `config/rpi5.yaml`. You can customize it to suit your specific hardware:

```yaml
environment: "rpi5"

voice:
  sample_rate: 16000
  channels: 1
  vad_silence_ms: 300
  wake_word: "aura"

  # Models for Raspberry Pi 5:
  # - "tiny.en": Ultra-fast (<150ms transcription latency on Pi 5)
  # - "base.en": Optimal balance between accuracy and latency (~350ms)
  stt_model: "base.en"
  tts_voice: "en_US-lessac-medium"

vision:
  camera_index: 0
  # 30 FPS target for 21-point hand tracking
  target_fps: 30
  detection_confidence: 0.7
  tracking_confidence: 0.6
  camera_backend: "v4l2" # Use "v4l2" for USB webcams, "libcamera" for Pi Camera Module 3
```

### Pi Camera Module 3 (CSI-2 Ribbon Cable) Note
If using the official Raspberry Pi Camera Module 3 instead of a USB webcam:
1. Ensure the camera is enabled in `/boot/firmware/config.txt` (`camera_auto_detect=1`).
2. Run `rpicam-hello -t 2000` to verify camera detection.
3. For OpenCV V4L2 compatibility, launch services using `libcamerify`:
   ```bash
   libcamerify python3 -m aura.core.main --config config/rpi5.yaml
   ```

---

## 7. Adding Local LLM Reasoning (Offline JARVIS Mode)

For Raspberry Pi 5 units with **8GB or 16GB of RAM**, you can run small language models locally without cloud API dependencies:

1. **Install Ollama for ARM64 Linux**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. **Download a lightweight reasoning model**:
   ```bash
   # Ultra-compact (0.5B parameters, ~40 tokens/s on Pi 5):
   ollama pull qwen2.5:0.5b

   # Recommended smart model (1.5B parameters, ~22 tokens/s on Pi 5):
   ollama pull qwen2.5:1.5b

   # Meta Llama 3.2 (1B parameters, ~25 tokens/s on Pi 5):
   ollama pull llama3.2:1b
   ```
3. AURA OS can query `http://127.0.0.1:11434/api/generate` locally for autonomous task decomposition.

---

## 8. Summary of Makefile Commands

| Command | Action |
| :--- | :--- |
| `make rpi-setup` | Automated package installation, user groups, venv, and dependencies |
| `make rpi-hwcheck` | Run system diagnostics (SoC thermals, PipeWire audio, V4L2 camera, sandbox) |
| `make rpi-daemon` | Start `aurad` in the foreground with the Pi 5 configuration profile |
| `make rpi-ui` | Start Desktop HUD server on `0.0.0.0:8765` for local network access |
| `make rpi-services-install` | Deploy systemd user services to `~/.config/systemd/user/` |
| `make rpi-services-start` | Start background services |
| `make rpi-services-status` | View background service health |
| `make rpi-services-stop` | Stop background services |
