# AURA OS — Implementation Roadmap & Execution Plan
> **Autonomous Unified Runtime Architecture**
> Version: 0.1.0-draft | Status: Approved Roadmap | Critical Path: Voice MVP ➔ Agent Runtime ➔ Memory ➔ Desktop Shell

---

## Executive Summary

This document translates the authoritative technical architecture defined in [ARCHITECTURE.md](file:///Users/aryansingh/Documents/Aura-OS/context/ARCHITECTURE.md) into a phased, chronological engineering roadmap. It establishes strict acceptance gates, automated test requirements, risk mitigations, and demo scenarios for each phase of AURA OS development.

---

## Roadmap Overview & Milestone Hierarchy

```mermaid
gantt
    title AURA OS Engineering Roadmap
    dateFormat  YYYY-MM-DD
    section Core Foundations
    Phase 0: Foundation Setup (M0)           :done,    p0, 2026-09-01, 2026-09-30
    Phase 1: Voice MVP Slice (M1)            :active,  p1, 2026-10-01, 2026-11-15
    section Agentic Architecture
    Phase 2: Agent Runtime & Tasks (M2)      :         p2, 2026-11-16, 2026-12-31
    Phase 3: Unified Memory Engine (M3)      :         p3, 2027-01-01, 2027-02-15
    Phase 4: Context Engine & Grounding (M4) :         p4, 2027-02-16, 2027-03-31
    Phase 4B: Vision & Spatial Gestures (M4.5):        p4b, 2027-04-01, 2027-04-30
    Phase 5: Multi-Agent Supervision (M5)    :         p5, 2027-05-01, 2027-05-31
    section Native Environment
    Phase 6: Native Wayland Shell (M6)       :         p6, 2027-06-01, 2027-07-15
    Phase 7: Advanced OS Integration (M7)    :         p7, 2027-07-16, 2027-08-31
    Phase 8: Security & Sandboxing (M8)      :         p8, 2027-09-01, 2027-10-15
    section Hardening & Distribution
    Phase 9: 100% Local AI Offline (M9)      :         p9, 2027-10-16, 2027-11-30
    Phase 10: Distributable ISO & Images (M10):        p10, 2027-12-01, 2027-12-31
```

| Milestone | Target Version | Phase Title | Primary Focus |
| :--- | :--- | :--- | :--- |
| **M0** | `v0.0.1-prealpha` | **Phase 0: Foundation** | ARM64 Linux UTM VM, Python 3.12, systemd units, basic UDS IPC |
| **M1** | `v0.1.0-alpha` | **Phase 1: Voice MVP** | Vertical slice: Wake word ➔ STT ➔ Folder Creation ➔ TTS |
| **M2** | `v0.2.0-alpha` | **Phase 2: Agent Runtime** | Single-agent autonomous loops, Task DAGs, Tool Registry |
| **M3** | `v0.3.0-alpha` | **Phase 3: Memory Engine** | SQLite episodic journal + `sqlite-vec` semantic memory |
| **M4** | `v0.4.0-alpha` | **Phase 4: Context Engine** | Wayland window tracking, active app, clipboard, "fix this" |
| **M4.5**| `v0.4.5-alpha` | **Phase 4B: Vision & Spatial Gestures**| 21-pt hand pose tracking, raycast reticle, multimodal fusion |
| **M5** | `v0.5.0-beta` | **Phase 5: Multi-Agent System**| Parent-child agent spawning, parallel tasks, supervisor, critic |
| **M6** | `v0.6.0-beta` | **Phase 6: Native Desktop** | Rust/GTK4 Wayland overlay, Aura Orb (`UI-001`), Voice Overlay |
| **M7** | `v0.7.0-beta` | **Phase 7: OS Integration** | D-Bus system bus, notification center, systemd service control |
| **M8** | `v0.8.0-rc` | **Phase 8: Security & Sandbox**| Bubblewrap isolation, capability tokens, immutable audit trail |
| **M9** | `v0.9.0-rc` | **Phase 9: Local AI** | 100% offline stack: faster-whisper, Piper, llama.cpp GGUF |
| **M10**| `v1.0.0` | **Phase 10: Distribution** | Bootable ARM64 ISO, live installer, Plymouth splash screen |

---

## Detailed Phase Roadmaps

---

### PHASE 0 — Foundation & Environment Setup
- **Milestone**: `M0` (`v0.0.1-prealpha`)
- **Objective**: Establish the repeatable ARM64 virtual development environment, configure system services, logging, and baseline inter-process communication.

#### Deliverables
1. Automated VM provisioning scripts for Ubuntu 24.04 / Debian 12 on UTM (Apple Silicon).
2. Python 3.12+ project skeleton with `pyproject.toml`, dependency lockfile, and linting (`ruff`, `mypy`).
3. Core daemon launcher (`python -m aura.core.main`) managed via `systemd` user service (`aura-core.service`).
4. Structured JSON logging subsystem writing to stdout and `journald`.
5. Basic IPC prototype using Unix Domain Sockets (UDS) for ping/pong heartbeats.

#### Dependencies
- Apple Silicon Host running macOS 14+ with UTM installed.
- ARM64 minimal Linux ISO.

#### Definition of Done (DoD)
- [ ] `make vm-init` boots a clean ARM64 Linux VM inside UTM with audio input/output passthrough verified.
- [ ] `systemctl --user status aura-core.service` reports active/running.
- [ ] Running `aura-cli ping` over UDS returns `pong` and latency under 5ms.
- [ ] 100% of unit tests pass with zero type check errors.

#### Tests
- **Automated**: `pytest tests/unit/test_core_ipc.py` verifies socket connection and heartbeat round-trip.
- **Manual**: Reboot the VM and verify `aurad` starts automatically via systemd.

#### Demo Scenario
Developer opens VM terminal, runs `systemctl --user start aura-core`, and executes `aura-cli status`. Terminal displays green operational metrics and daemon uptime.

#### Risks & Mitigations
- *Risk*: Audio passthrough distortion in UTM on Apple Silicon.
- *Mitigation*: Force VirtIO Sound driver in UTM configuration with 48kHz sampling rate.

---

### PHASE 1 — Voice MVP Slice
- **Milestone**: `M1` (`v0.1.0-alpha`)
- **Objective**: Deliver a complete end-to-end vertical slice proving the voice-to-action paradigm without complex multi-agent overhead.

#### Deliverables
1. PipeWire microphone streaming capture loop via Python.
2. Local wake-word detection using `openWakeWord` ("Aura").
3. Voice Activity Detection (WebRTC VAD) with 300ms silence threshold.
4. Streaming Speech-to-Text (STT) via `faster-whisper` (base.en quantized).
5. Simple deterministic intent parser mapping speech to `filesystem.mkdir`.
6. Permission check gate allowing Desktop folder creation.
7. Verification loop checking that directory exists on filesystem.
8. Local Text-to-Speech (TTS) via `Piper` replying: *"Created folder Test on your Desktop."*

#### Dependencies
- Phase 0 Foundation complete.
- PipeWire and ALSA development headers installed.

#### Definition of Done (DoD)
- [ ] System continuously runs in background with <2% idle CPU usage.
- [ ] User speaks *"Aura"*; system transitions to `LISTENING` state in <150ms.
- [ ] User says *"Create a folder called Test on my Desktop"*; directory `~/Desktop/Test` is created.
- [ ] Piper speaks confirmation within 1.2s of speech termination.

#### Tests
- **Automated**: Mock audio injection test feeding WAV audio of *"Aura, create a folder called Test"* into the pipeline and asserting folder existence.
- **Manual**: Speak the command verbally across the room into the microphone.

#### Demo Scenario
User says aloud: *"Aura, create a folder called Test on my Desktop."* The folder appears immediately on the desktop, and Aura verbally confirms: *"Created folder Test on your Desktop."*

#### Risks & Mitigations
- *Risk*: Speech transcription hallucinating file names.
- *Mitigation*: Constrain initial intent grammar and log confidence scores.

---

### PHASE 2 — Agent Runtime & Task Scheduling
- **Milestone**: `M2` (`v0.2.0-alpha`)
- **Objective**: Implement the formal single-agent execution loop, Task DAG models, tool registries, and state recovery.

#### Deliverables
1. `BaseAgent` class implementing process model attributes (ID, budget, state).
2. `TaskManager` handling task creation, state transitions, and cancellation.
3. `ToolRegistry` with strict schema validation and execution wrappers.
4. Core toolset: `filesystem.read`, `filesystem.write`, `filesystem.search`, `terminal.execute`.
5. Basic single-agent LLM reasoning loop with tool calling and retry budget.
6. Execution state persistence in SQLite (`~/.local/share/aura/aura.db`).

#### Dependencies
- Phase 1 Voice MVP.

#### Definition of Done (DoD)
- [ ] An agent can autonomously solve a 3-step task (e.g. read file, find syntax error, write fix).
- [ ] If a tool returns an error, the agent attempts up to 3 self-healing retries before failing.
- [ ] Killing `aurad` mid-task and restarting restores the agent state from SQLite.

#### Tests
- **Automated**: Integration test where an agent is instructed to find a specific string in a mock repository and output the line count.
- **Manual**: Trigger a long-running terminal task and issue `aura-cli cancel <task-id>` to verify graceful termination.

#### Demo Scenario
User says: *"Aura, read the file notes.txt in my home directory, count how many lines mention 'meeting', and save the answer to meeting_count.txt."* Aura plans, executes the tools, and speaks the result.

#### Risks & Mitigations
- *Risk*: Infinite agent tool-call loops draining token budgets.
- *Mitigation*: Hard-cap maximum tool steps per task to 10 by default.

---

### PHASE 3 — Unified Memory Engine
- **Milestone**: `M3` (`v0.3.0-alpha`)
- **Objective**: Provide working, episodic, and semantic memory layers enabling context persistence across sessions.

#### Deliverables
1. Episodic memory journal schema in SQLite tracking all goals, runs, and outcomes.
2. Integration of `sqlite-vec` extension for local vector similarity searches.
3. Background embedding pipeline converting completed tasks and indexed documents into vector embeddings.
4. Semantic search tool (`filesystem.semantic_search`).
5. Working memory scratchpad injected dynamically into agent system prompts.

#### Dependencies
- Phase 2 Agent Runtime.

#### Definition of Done (DoD)
- [ ] Episodic events are committed within 10ms of task state changes.
- [ ] Vector similarity query across 10,000 document chunks returns relevant results in <50ms.
- [ ] An agent can recall facts stated in previous conversations (e.g. *"What did I name that project yesterday?"*).

#### Tests
- **Automated**: `pytest tests/unit/test_memory.py` testing episodic insertion, vector indexing, and cosine similarity retrieval.
- **Manual**: Ask Aura to remember a custom preference, restart the service, and verify Aura respects it in a subsequent task.

#### Demo Scenario
User says: *"Aura, remember that my favorite compiler flag is -O3."* Later: *"Aura, compile main.c."* Aura recalls the preference from memory and uses `-O3`.

#### Risks & Mitigations
- *Risk*: SQLite database file locking under concurrent daemon access.
- *Mitigation*: Enforce SQLite WAL (Write-Ahead Logging) mode and busy timeout handlers.

---

### PHASE 4 — Context Engine & Desktop Grounding
- **Milestone**: `M4` (`v0.4.0-alpha`)
- **Objective**: Grant AURA real-time awareness of active Wayland windows, focused text, clipboards, and terminal state.

#### Deliverables
1. Wayland window tracking daemon querying toplevel surfaces.
2. Clipboard watcher capturing recent clipboard contents (with privacy filtering).
3. Shell integration script for bash/zsh capturing terminal command history and exit codes.
4. Workspace root detector identifying active Git repositories.
5. Context resolver handling demonstrative pronouns ("this", "that").

#### Dependencies
- Phase 3 Memory Engine.
- Wayland compositor supporting `wlr-foreign-toplevel` or GNOME Mutter D-Bus.

#### Definition of Done (DoD)
- [ ] Switching active windows emits a D-Bus signal (`org.auraos.Context.WindowChanged`) within 50ms.
- [ ] User highlights code in editor, says *"Aura, explain this"*, and Aura explains the exact selected snippet.

#### Tests
- **Automated**: Mock context feeder simulating active terminal error and asserting that intent resolution picks up the failing command.
- **Manual**: Trigger a compiler error in a terminal, say *"Aura, fix this"*, and observe Aura reading the terminal buffer directly.

#### Demo Scenario
User runs a failing Python script in a terminal. Without copying anything, user says: *"Aura, why did this fail?"* Aura inspects the terminal output and explains the `IndexError`.

#### Risks & Mitigations
- *Risk*: Inadvertently capturing sensitive passwords from clipboard.
- *Mitigation*: Ignore clipboard buffers with MIME types indicating password managers (`x-kde-passwordManagerHint`).

---

### PHASE 4B — Vision & Spatial Gesture Engine
- **Milestone**: `M4.5` (`v0.4.5-alpha`)
- **Objective**: Implement camera-based real-time 3D hand tracking, canonical gesture recognition, and multimodal fusion to enable Jarvis-like spatial control.

#### Deliverables
1. PipeWire & V4L2 camera capture loop in Python (`aura/vision/camera.py`).
2. Quantized ONNX 21-point hand landmark pose estimator (`aura/vision/hand_tracker.py`).
3. Kinematic gesture classification engine (`GESTURE_POINT`, `GESTURE_PINCH`, `GESTURE_PAUSE`, `GESTURE_SWIPE`, `GESTURE_PUSH`, `GESTURE_FRAME`).
4. 3D-to-2D screen coordinate raycasting engine with 1-Euro jitter smoothing filter.
5. Multimodal Fusion Engine (`aura-fusion`) temporally synchronizing speech tokens and pointing vectors.
6. Spatial Reticle overlay component (`UI-021`) integrated with `aura-shell`.

#### Dependencies
- Phase 1 Voice MVP.
- Phase 4 Context Engine.
- V4L2 kernel device `/dev/video0` or PipeWire camera portal.

#### Definition of Done (DoD)
- [ ] Real-time hand landmark inference runs at $\ge 30\,\text{FPS}$ with $<8\%$ single-core CPU usage on ARM64.
- [ ] Raising an open palm triggers `GESTURE_PAUSE` within 50ms, halting TTS playback and tool execution.
- [ ] Pointing at a window and saying *"Aura, focus this"* correctly activates that Wayland surface.
- [ ] In-air push gesture reliably selects and authorizes the Permission Dialog (`UI-007`).
- [ ] Zero video frame retention verified: raw pixel buffers are overwritten in-memory and never written to disk.

#### Tests
- **Automated**: Mock landmark stream test feeding synthetic 3D coordinates into `GestureClassifier` and verifying event classification accuracy.
- **Manual**: Run interactive webcam tracking script inside UTM; verify hand skeleton overlay and raycast accuracy.

#### Demo Scenario
Developer points an index finger at a terminal running failing tests and verbally says: *"Aura, fix that error."* The system draws a subtle cyan reticle around the targeted terminal, parses the error, and begins autonomous repair.

#### Risks & Mitigations
- *Risk*: Continuous camera inference draining battery / CPU when user is idle.
- *Mitigation*: Dynamically drop camera capture to 10 FPS when no hand is in frame, ramping back to 60 FPS within 1 frame of hand detection.

---

### PHASE 5 — Multi-Agent Runtime & Dynamic Supervision
- **Milestone**: `M5` (`v0.5.0-beta`)
- **Objective**: Support parent/child agent hierarchies, parallel task execution, and specialized critic agents.

#### Deliverables
1. `AgentFactory` for dynamic agent composition based on requested capabilities.
2. Parent-child agent relationship manager with resource inheritance.
3. Parallel task scheduler executing independent DAG nodes concurrently.
4. Critic/Verification agent validating code changes and test outputs before completion.
5. Watchdog supervisor terminating stuck or runaway agents.

#### Dependencies
- Phase 4 Context Engine.

#### Definition of Done (DoD)
- [ ] A parent agent can spawn two child agents to work in parallel on separate sub-tasks.
- [ ] If a child agent fails or exceeds its budget, the parent is notified and can replan.
- [ ] Verification agent successfully catches an intentional regression introduced by a coding agent.

#### Tests
- **Automated**: Parallel execution test verifying two independent file-search tasks complete in `max(t1, t2)` rather than `t1 + t2`.
- **Manual**: Assign a multi-step project refactor and watch the agent hierarchy collaborate in real-time logs.

#### Demo Scenario
User says: *"Aura, audit my project for security vulnerabilities and format all Python files."* Aura spawns a `SecurityAuditor` and a `CodeFormatter` simultaneously, verifies both, and speaks the consolidated report.

#### Risks & Mitigations
- *Risk*: Deadlocks in task DAG dependencies.
- *Mitigation*: Implement cycle detection during DAG planning phase.

---

### PHASE 6 — Native Ambient Desktop Shell
- **Milestone**: `M6` (`v0.6.0-beta`)
- **Objective**: Replace terminal logging with a sleek, native Wayland desktop shell written in Rust/GTK4.

#### Deliverables
1. `aura-shell` executable using GTK4 and `gtk4-layer-shell`.
2. **Aura Orb** (`UI-001`): Ambient, glowing orb reflecting real-time voice and agent states.
3. **Voice Overlay** (`UI-002`): Non-intrusive heads-up display showing live transcription and thoughts.
4. **Agent Monitor** (`UI-004`): Floating HUD showing active agent DAGs, token usage, and progress bars.
5. **Permission Dialog** (`UI-007`): Interactive modal for approving consequential operations.

#### Dependencies
- Phase 5 Multi-Agent Runtime.
- Rust toolchain and GTK4 development libraries.

#### Definition of Done (DoD)
- [ ] `aura-shell` runs at steady 60fps with <50MB resident memory.
- [ ] Voice state transitions trigger smooth visual animations without lag or stutter.
- [ ] Permission dialog blocks tool execution until physical user confirmation.

#### Tests
- **Automated**: Headless Wayland tests validating window creation and D-Bus signal consumption.
- **Manual**: Interact with the desktop using voice and verify UI components animate smoothly.

#### Demo Scenario
User says *"Aura"*; the Aura Orb pulses with a cyan glow, the voice overlay appears, speech is transcribed in real-time, an agent card appears on screen tracking progress, and disappears smoothly when finished.

#### Risks & Mitigations
- *Risk*: Wayland layer-shell protocol incompatibilities across different compositors.
- *Mitigation*: Target standard wlroots/GNOME Mutter protocol specifications.

---

### PHASE 7 — Advanced OS Integration & D-Bus Bus
- **Milestone**: `M7` (`v0.7.0-beta`)
- **Objective**: Deep integration with Linux systemd, notification daemons, application launchers, and filesystem monitoring.

#### Deliverables
1. Full D-Bus interface implementation (`org.auraos.Core`, `org.auraos.AgentManager`, `org.auraos.Voice`).
2. Native desktop notification server (`org.freedesktop.Notifications`).
3. Application launcher service reading `.desktop` files.
4. Systemd control tool enabling agents to inspect and restart user services.
5. Filesystem event watcher (inotify) triggering proactive agent assistance.

#### Dependencies
- Phase 6 Native Desktop Shell.

#### Definition of Done (DoD)
- [ ] Aura can launch, inspect, and close desktop applications via voice.
- [ ] System notifications are routed seamlessly into Aura's memory and voice channels.

#### Tests
- **Automated**: D-Bus protocol compliance tests using `pydbus` and `dbus-send`.
- **Manual**: Tell Aura to launch a text editor, verify it opens, and ask Aura to inspect its window status.

#### Demo Scenario
User says: *"Aura, open Firefox and search for Linux kernel documentation."* Aura launches Firefox directly to the URL without simulating mouse clicks.

#### Risks & Mitigations
- *Risk*: Race conditions when managing systemd units via D-Bus.
- *Mitigation*: Enforce synchronous unit state polling with timeouts.

---

### PHASE 8 — Security Hardening & Sandboxing
- **Milestone**: `M8` (`v0.8.0-rc`)
- **Objective**: Enforce strict isolation for all agent executions using Bubblewrap and Linux namespaces.

#### Deliverables
1. Bubblewrap execution sandbox wrapper for all terminal and tool operations.
2. Read-only filesystem bind mounts for `/usr`, `/bin`, `/lib`, and `/etc`.
3. Ephemeral workspace mounting with network isolation by default.
4. Cryptographic capability token generator for tool authorization.
5. Append-only, tamper-evident audit log for all system modifications.

#### Dependencies
- Phase 7 OS Integration.
- `bubblewrap` package installed.

#### Definition of Done (DoD)
- [ ] An agent instructed to run `rm -rf /` or modify `/etc/passwd` is completely blocked by the sandbox.
- [ ] Unauthorized outbound network requests in sandboxed tools fail with `ENETUNREACH`.
- [ ] 100% of tool invocations produce verified entries in `permissions_log`.

#### Tests
- **Automated**: Security penetration test suite attempting sandbox escapes, privilege escalation, and unauthorized file reads.
- **Manual**: Attempt to delete a file via voice without confirming on `UI-007`; verify deletion is denied.

#### Demo Scenario
User gives an agent a script containing a rogue `cat /etc/shadow` command. The sandbox intercepts the syscall, logs the violation, and Aura warns the user.

#### Risks & Mitigations
- *Risk*: Overly restrictive sandboxes breaking standard developer tools (e.g. compilers needing `/tmp`).
- *Mitigation*: Provide well-tuned sandbox profiles (`developer`, `isolated`, `readonly`).

---

### PHASE 9 — 100% Local AI Autonomy
- **Milestone**: `M9` (`v0.9.0-rc`)
- **Objective**: Ensure the entire operating environment functions with zero external internet dependencies.

#### Deliverables
1. Embedded `llama.cpp` / CTranslate2 local LLM inference engine.
2. Quantized GGUF models (3B to 8B parameter models) pre-cached in `~/.local/share/aura/models/`.
3. Local embeddings engine for semantic memory without cloud API keys.
4. Seamless offline model router switching automatically on network loss.

#### Dependencies
- Phase 8 Security & Sandboxing.

#### Definition of Done (DoD)
- [ ] Disconnecting the VM network interface allows all voice commands, planning, and file tools to continue operating without error.
- [ ] Local model inference achieves >25 tokens/sec on ARM64 Apple Silicon virtualization.

#### Tests
- **Automated**: Run full integration test suite with networking disabled via `ip link set eth0 down`.
- **Manual**: Unplug host internet and conduct a complete voice interaction session.

#### Demo Scenario
Airplane mode demonstration: With no network connection, user says: *"Aura, summarize today's notes and organize my workspace."* Aura runs fully offline on local silicon and completes the task.

#### Risks & Mitigations
- *Risk*: High RAM consumption causing OOM kills on 8GB VMs.
- *Mitigation*: Use 4-bit (Q4_K_M) quantizations and aggressive model unloading when idle.

---

### PHASE 10 — Distribution, Packaging & Bootable ISO
- **Milestone**: `M10` (`v1.0.0`)
- **Objective**: Package AURA OS into a distributable, bootable ARM64 ISO and pre-configured UTM appliance.

#### Deliverables
1. Custom Plymouth boot splash theme featuring the animated Aura Orb.
2. Live installer ISO build scripts based on Debian live-build.
3. Pre-configured UTM `.utm` bundle for one-click import on macOS Apple Silicon.
4. Out-of-the-Box Experience (OOBE) setup wizard (`UI-020`) for microphone calibration and model downloading.
5. Complete user and developer documentation.

#### Dependencies
- Phases 0 through 9 complete and verified.

#### Definition of Done (DoD)
- [ ] Booting the generated ISO inside UTM reaches the AURA voice-ready desktop without manual intervention.
- [ ] OOBE wizard successfully guides the user through initial voice calibration.
- [ ] Clean install takes less than 10 minutes on standard Apple Silicon hardware.

#### Tests
- **Automated**: Automated VM smoke test using headless QEMU to verify clean boot and shutdown.
- **Manual**: Fresh install test on a secondary Mac without developer tools pre-installed.

#### Demo Scenario
User downloads `AuraOS-arm64.utm`, double-clicks it on macOS, clicks Start, sees the animated boot splash, and is greeted by voice: *"Welcome to AURA. I am ready."*

#### Risks & Mitigations
- *Risk*: Large ISO file sizes due to model weights.
- *Mitigation*: Ship base system with minimal models (~2GB) and offer post-install model downloads in OOBE.

---

## Critical Path & Dependency Matrix

The absolute critical path to reach a functional product is:
$$\text{Phase 0 (Foundation)} \longrightarrow \text{Phase 1 (Voice MVP)} \longrightarrow \text{Phase 2 (Agent Runtime)} \longrightarrow \text{Phase 3 (Memory)} \longrightarrow \text{Phase 6 (Desktop Shell)} \longrightarrow \text{Phase 8 (Security)}$$

Non-critical paths that can proceed in parallel once Phase 2 is complete:
- Context Engine (Phase 4)
- Local AI Optimization (Phase 9)
- Packaging & Distribution (Phase 10)

---

## Cross-Document References

- High-level vision & features: [README.md](file:///Users/aryansingh/Documents/Aura-OS/README.md)
- Deep technical architecture: [ARCHITECTURE.md](file:///Users/aryansingh/Documents/Aura-OS/context/ARCHITECTURE.md)
- Active sprint tasks & progress dashboard: [PROGRESS-TRACKER.md](file:///Users/aryansingh/Documents/Aura-OS/context/PROGRESS-TRACKER.md)
- UI components, screens & voice states: [UI-REGISTRY.md](file:///Users/aryansingh/Documents/Aura-OS/context/UI-REGISTRY.md)
