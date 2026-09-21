# AURA Development Progress
> **Autonomous Unified Runtime Architecture**
> Live Project State Machine & Continuous Engineering Ledger

---

## AI Agent Instructions

> [!IMPORTANT]
> **MANDATORY PROTOCOL FOR AI CODING AGENTS**:
> Whenever an AI coding agent completes meaningful work on AURA OS, it **MUST** update this file before ending its session.
> 
> You must:
> 1. Mark completed tasks from `🟡 In Progress` to `🟢 Complete`.
> 2. Add newly discovered tasks, edge cases, or bugs under the appropriate subsystem prefix.
> 3. Update the `Last Updated` timestamp and `Overall Completion` percentage.
> 4. Record any blockers (`🔴 Blocked`) or architectural pivots.
> 5. Log changes in the `Recent Changes` changelog and define goals for the `Next Session`.
>
> This file is the **persistent project state** across all human and agent interactions. Do not skip updating it!

---

## Executive Status Dashboard

| Metric | Current State |
| :--- | :--- |
| **Current Version** | `v0.0.1-prealpha` |
| **Current Phase** | **Phase 0 — Foundation & Environment Setup** |
| **Current Milestone**| **M0 — Initial Baseline** |
| **Overall Completion**| **4%** |
| **Last Updated** | `2026-09-21` |
| **Active Focus** | Bootstrapping UTM ARM64 VM environment & core daemon skeleton |

### Subsystem Status Matrix

| Subsystem | Prefix | Status | Completion | Lead Technology |
| :--- | :---: | :---: | :---: | :--- |
| **Linux Foundation & Daemons** | `SYS` | 🟡 In Progress | 25% | Debian 12 / systemd / Python 3.12 |
| **Voice Subsystem** | `VOICE` | 🔵 Planned | 0% | PipeWire / openWakeWord / faster-whisper |
| **Agent Runtime** | `AGENT` | 🔵 Planned | 0% | Asyncio / Pydantic / Task DAG |
| **Unified Memory Engine** | `MEM` | 🔵 Planned | 0% | SQLite 3 / sqlite-vec |
| **Context Engine** | `CTX` | 🔵 Planned | 0% | Wayland toplevel / wl-clipboard |
| **Tool & Skill Registry** | `TOOL` | 🔵 Planned | 0% | Native Python / MCP Client |
| **Permission Engine** | `SEC` | 🔵 Planned | 0% | Policy Engine / Capability Tokens |
| **Native Wayland Shell** | `UI` | 🔵 Planned | 0% | Rust / GTK4 / Layer-Shell |
| **Packaging & Distribution** | `PKG` | 🔵 Planned | 0% | UTM / Live-Build / Plymouth |

*Status Legend: ⚪ Not Started | 🔵 Planned | 🟡 In Progress | 🟢 Complete | 🔴 Blocked*

---

## Sprint Board: Current Sprint (Sprint 0 — Project Bootstrap)

### Active Focus
- Establishing core repository architecture and canonical documentation.
- Setting up the UTM ARM64 development environment.
- Writing initial systemd user unit templates and Python entry point.

### Sprint Breakdown
- **Completed**:
  - `SYS-001`: Initialize Git repository and project file tree.
  - `SYS-002`: Author authoritative architectural specification (`ARCHITECTURE.md`).
  - `SYS-003`: Author complete engineering phase plan (`PLAN.md`).
  - `SYS-004`: Author canonical UI component registry (`UI-REGISTRY.md`).
- **In Progress**:
  - `SYS-005`: Implement `aurad` core daemon entry point and basic Unix Domain Socket server.
  - `SYS-006`: Configure automated UTM VM bootstrap Makefile targets.
- **Next Up**:
  - `VOICE-001`: Set up PipeWire audio capture stream in Python.
  - `VOICE-002`: Integrate `openWakeWord` with "Aura" detection model.
- **Blocked**:
  - None currently.

---

## Master Task Registry

### 1. Linux Foundation & System Daemons (`SYS`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `SYS-001` | Initialize Git repo, `.gitignore`, and base directory structure | 🟢 Complete | P0 | None | Base layout established |
| `SYS-002` | Author authoritative system architecture specification | 🟢 Complete | P0 | `SYS-001` | See `ARCHITECTURE.md` |
| `SYS-003` | Author comprehensive phased engineering plan | 🟢 Complete | P0 | `SYS-002` | See `PLAN.md` |
| `SYS-004` | Author canonical UI and voice interaction registry | 🟢 Complete | P0 | `SYS-002` | See `UI-REGISTRY.md` |
| `SYS-005` | Implement `aurad` daemon entrypoint and UDS IPC server | 🟡 In Progress | P0 | `SYS-001` | `aura/core/main.py` |
| `SYS-006` | Create UTM ARM64 VM provisioning scripts & Makefile targets | 🟡 In Progress | P1 | `SYS-001` | Target Ubuntu 24.04 / Debian 12 |
| `SYS-007` | Create systemd user service unit (`aura-core.service`) | 🔵 Planned | P1 | `SYS-005` | `services/systemd/` |
| `SYS-008` | Implement structured JSON logging with `journald` bridge | 🔵 Planned | P1 | `SYS-005` | `aura/core/logger.py` |
| `SYS-009` | Implement `aura-cli` developer utility for ping and status | 🔵 Planned | P2 | `SYS-005` | Command line client |
| `SYS-010` | Implement D-Bus session bus service (`org.auraos.Core`) | 🔵 Planned | P1 | `SYS-005` | Using `sdbus` or `pydbus` |

### 2. Voice Subsystem (`VOICE`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `VOICE-001` | Implement PipeWire asynchronous PCM audio capture loop | 🔵 Planned | P0 | `SYS-006` | 16kHz, 16-bit mono |
| `VOICE-002` | Integrate `openWakeWord` with "Aura" activation model | 🔵 Planned | P0 | `VOICE-001` | Target <1% CPU overhead |
| `VOICE-003` | Integrate WebRTC Voice Activity Detection (VAD) | 🔵 Planned | P0 | `VOICE-001` | 300ms silence cut-off |
| `VOICE-004` | Implement circular audio ring buffer for pre-roll capture | 🔵 Planned | P1 | `VOICE-002` | 200ms pre-wake audio |
| `VOICE-005` | Integrate `faster-whisper` (CTranslate2 INT8) STT pipeline | 🔵 Planned | P0 | `VOICE-003` | Local ARM64 transcription |
| `VOICE-006` | Integrate `Piper TTS` for local low-latency speech synthesis | 🔵 Planned | P0 | `SYS-005` | PipeWire direct sink |
| `VOICE-007` | Implement real-time audio barge-in / interruption engine | 🔵 Planned | P1 | `VOICE-003`, `VOICE-006` | Mutes audio on user speech |
| `VOICE-008` | Build streaming text token emitter over D-Bus | 🔵 Planned | P2 | `VOICE-005` | Signal `TranscriptUpdated` |
| `VOICE-009` | Optimize whisper and Piper models with ARM NEON SIMD | 🔵 Planned | P2 | `VOICE-005` | Benchmark on Apple Silicon |
| `VOICE-010` | Acoustic Echo Cancellation (AEC) filter configuration | 🔵 Planned | P2 | `VOICE-001` | Prevents self-triggering |

### 3. Agent Runtime & Scheduling (`AGENT`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `AGENT-001` | Implement `BaseAgent` class and process lifecycle model | 🔵 Planned | P0 | `SYS-005` | `aura/agents/base.py` |
| `AGENT-002` | Implement `TaskManager` and task DAG dependency scheduler | 🔵 Planned | P0 | `AGENT-001` | Directed acyclic graphs |
| `AGENT-003` | Build single-agent autonomous execution loop | 🔵 Planned | P0 | `AGENT-001` | ReAct pattern execution |
| `AGENT-004` | Implement state recovery and checkpointing to SQLite | 🔵 Planned | P1 | `AGENT-002` | Resumes after crash |
| `AGENT-005` | Implement dynamic `AgentFactory` capability composer | 🔵 Planned | P1 | `AGENT-001` | Avoid hardcoding agent classes |
| `AGENT-006` | Build Supervisor agent for watchdog and orphan cleanup | 🔵 Planned | P1 | `AGENT-005` | Terminates runaway loops |
| `AGENT-007` | Implement parent-child agent spawning and delegation | 🔵 Planned | P2 | `AGENT-005` | Parallel execution |
| `AGENT-008` | Implement Critic/Verification agent feedback loop | 🔵 Planned | P1 | `AGENT-003` | Validates outcomes |
| `AGENT-009` | Implement token and cost budget tracker per agent process | 🔵 Planned | P1 | `AGENT-001` | Prevents API overages |
| `AGENT-010` | Add task cancellation and signal propagation handler | 🔵 Planned | P1 | `AGENT-002` | User interrupt handling |

### 4. Unified Memory Engine (`MEM`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `MEM-001` | Create SQLite schema for episodic memory and task history | 🔵 Planned | P0 | `SYS-005` | `~/.local/share/aura/aura.db` |
| `MEM-002` | Integrate `sqlite-vec` extension for local vector indexing | 🔵 Planned | P0 | `MEM-001` | Zero-dependency vector DB |
| `MEM-003` | Implement local text chunking and embedding pipeline | 🔵 Planned | P1 | `MEM-002` | Sentence-transformers local |
| `MEM-004` | Implement in-memory Working Memory scratchpad buffer | 🔵 Planned | P0 | `AGENT-001` | Injected into agent context |
| `MEM-005` | Build Procedural Memory prompt and workflow template store | 🔵 Planned | P2 | `MEM-001` | Reusable skill templates |
| `MEM-006` | Implement filesystem artifact storage and snapshot manager | 🔵 Planned | P1 | `MEM-001` | `~/.local/share/aura/artifacts` |
| `MEM-007` | Implement episodic memory search tool for agents | 🔵 Planned | P1 | `MEM-001` | Queries past experiences |
| `MEM-008` | Build memory retention and automatic summarization policy | 🔵 Planned | P3 | `MEM-001` | Pruning old raw logs |

### 5. Context Engine (`CTX`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `CTX-001` | Implement Wayland toplevel active window tracking client | 🔵 Planned | P0 | `SYS-006` | `wlr-foreign-toplevel` |
| `CTX-002` | Build clipboard buffer inspector with privacy filtering | 🔵 Planned | P1 | `SYS-005` | Filters password hints |
| `CTX-003` | Create shell integration script (OSC 7 / OSC 133) | 🔵 Planned | P1 | `SYS-005` | Captures terminal errors |
| `CTX-004` | Implement project root and workspace context detector | 🔵 Planned | P1 | `SYS-005` | Discovers `.git` / `Cargo.toml` |
| `CTX-005` | Build demonstrative pronoun ("this", "that") resolver | 🔵 Planned | P0 | `CTX-001`, `CTX-003` | Resolves "Aura, fix this" |
| `CTX-006` | Implement recent file and document change tracker | 🔵 Planned | P2 | `CTX-004` | Inotify tracking |
| `CTX-007` | Expose Context D-Bus service (`org.auraos.Context`) | 🔵 Planned | P1 | `CTX-001` | Emits context signals |
| `CTX-008` | Implement screen pixel capture tool (Wayland screencopy) | 🔵 Planned | P3 | `CTX-001` | Visual multimodal grounding |

### 6. Tool & Skill Registry (`TOOL`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `TOOL-001` | Implement safe filesystem tools (`read`, `write`, `search`)| 🔵 Planned | P0 | `SYS-005` | Path validation enforced |
| `TOOL-002` | Implement sandboxed terminal execution tool (`terminal.exec`)| 🔵 Planned | P0 | `SYS-005` | PTY with timeout |
| `TOOL-003` | Implement `ToolRegistry` with Pydantic schema validation | 🔵 Planned | P0 | `SYS-005` | Strict argument checking |
| `TOOL-004` | Implement Model Context Protocol (MCP) client bridge | 🔵 Planned | P1 | `TOOL-003` | Stdio / SSE transports |
| `TOOL-005` | Build system inspection tool (`system.inspect`, CPU, RAM) | 🔵 Planned | P1 | `TOOL-003` | Inspects `/proc` and cgroups |
| `TOOL-006` | Implement application launcher tool (`apps.launch`) | 🔵 Planned | P2 | `TOOL-003` | Parses `.desktop` files |
| `TOOL-007` | Implement clipboard read/write tool | 🔵 Planned | P2 | `TOOL-003` | Manipulates Wayland clipboard |
| `TOOL-008` | Implement pre-modification file rollback snapshot tool | 🔵 Planned | P1 | `TOOL-001` | Ephemeral backups in `/tmp` |
| `TOOL-009` | Implement semantic file search tool via `sqlite-vec` | 🔵 Planned | P1 | `MEM-002`, `TOOL-001` | Vector similarity |
| `TOOL-010` | Implement headless browser tool via Playwright/Chromium | 🔵 Planned | P3 | `TOOL-003` | Optional research tool |

### 7. Permission Engine & Security (`SEC`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `SEC-001` | Implement policy engine (`ALLOW`, `DENY`, `ASK_*`) | 🔵 Planned | P0 | `SYS-005` | Default `DENY` |
| `SEC-002` | Enforce Voice Barrier Rule (voice cannot authorize root/del) | 🔵 Planned | P0 | `SEC-001` | Requires UI confirmation |
| `SEC-003` | Build Bubblewrap (`bwrap`) container execution sandbox | 🔵 Planned | P0 | `TOOL-002` | Unshares namespaces |
| `SEC-004` | Implement cryptographic capability token generator | 🔵 Planned | P1 | `SEC-001` | Scoped single-use tokens |
| `SEC-005` | Implement append-only SQLite `permissions_log` audit table | 🔵 Planned | P0 | `SEC-001` | Immutable audit trail |
| `SEC-006` | Build network egress filter and allowlist proxy | 🔵 Planned | P2 | `SEC-003` | Blocks untrusted outbound |
| `SEC-007` | Implement file path jail validator (blocks `~/.ssh`, `/etc`) | 🔵 Planned | P0 | `TOOL-001` | Path canonicalization |
| `SEC-008` | Create cgroups v2 resource slice for agent memory limits | 🔵 Planned | P1 | `SEC-003` | Prevents OOM of host |

### 8. Native Wayland Desktop Shell (`UI`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `UI-001` | Implement Aura Orb widget in Rust / GTK4 layer-shell | 🔵 Planned | P0 | `SYS-006` | Ambient voice status indicator |
| `UI-002` | Implement Voice Overlay HUD with live audio waveform | 🔵 Planned | P0 | `UI-001` | Slides in during speech |
| `UI-003` | Implement Command Transcript streaming text viewer | 🔵 Planned | P1 | `UI-002` | Shows live STT tokens |
| `UI-004` | Implement floating Agent Monitor HUD | 🔵 Planned | P1 | `UI-001` | Displays active tasks & DAGs |
| `UI-005` | Implement Agent Card widget | 🔵 Planned | P1 | `UI-004` | Per-agent status and metrics |
| `UI-006` | Implement Task Graph DAG visualizer | 🔵 Planned | P2 | `UI-004` | Interactive node graph |
| `UI-007` | Implement Permission Request modal dialog | 🔵 Planned | P0 | `SEC-001` | Physical approval modal |
| `UI-008` | Implement Semantic Search omnibar overlay | 🔵 Planned | P2 | `MEM-002` | Quick-search HUD |
| `UI-009` | Implement Notification Toast widget | 🔵 Planned | P1 | `UI-001` | Transient alerts |
| `UI-010` | Implement Context Inspector developer overlay | 🔵 Planned | P2 | `CTX-007` | Inspects active window/buffer |

### 9. Packaging & Distribution (`PKG`)

| Task ID | Description | Status | Priority | Dependencies | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `PKG-001` | Create automated UTM VM configuration bundle (`.utm`) | 🔵 Planned | P1 | `SYS-006` | Ready-to-import VM |
| `PKG-002` | Design Plymouth boot splash screen with animated Orb | 🔵 Planned | P2 | `UI-001` | Custom boot screen |
| `PKG-003` | Build live Debian/Ubuntu ARM64 root filesystem image | 🔵 Planned | P2 | `SYS-006` | Using `live-build` |
| `PKG-004` | Implement Out-of-the-Box Experience (OOBE) setup wizard | 🔵 Planned | P2 | `UI-001` | Microphone calibration |
| `PKG-005` | Generate bootable ARM64 ISO image | 🔵 Planned | P3 | `PKG-003` | Distributable ISO |
| `PKG-006` | Implement atomic A/B system update script | 🔵 Planned | P3 | `PKG-003` | Safe system upgrades |

---

## Known Bugs & Issues

| Bug ID | Subsystem | Description | Severity | Status | Workaround |
| :--- | :--- | :--- | :---: | :---: | :--- |
| *None* | — | No bugs identified at baseline bootstrap. | — | — | — |

---

## Technical Debt & Refactoring Queue

| Debt ID | Subsystem | Description | Impact | Target Phase |
| :--- | :--- | :--- | :---: | :---: |
| `DEBT-001` | Core | Consolidated Python daemon used for V0 instead of compiled Rust daemon | Low (acceptable for rapid iteration) | Phase 6 |
| `DEBT-002` | Audio | Initial audio capture relies on standard ALSA/PipeWire loopback rather than native PipeWire C API | Medium (adds ~15ms latency) | Phase 1 |

---

## Architectural Decisions Needed (Pending ADRs)

| Decision ID | Topic | Options Considered | Status |
| :--- | :--- | :--- | :---: |
| `ADR-001` | D-Bus Python Binding Library | `pydbus` vs `sdbus-python` vs `dasbus` | Proposed: `dasbus` (pure asyncio compatibility) |
| `ADR-002` | Local LLM Inference Engine | `llama.cpp` Python bindings vs `Ollama` daemon | Proposed: `llama-cpp-python` (in-process, zero external server) |
| `ADR-003` | Wayland Compositor Selection | Sway (wlroots) vs GNOME Mutter vs Labwc | Proposed: `Labwc` (lightweight, wlroots layer-shell native) |

---

## Active Experiments

| Experiment ID | Hypothesis | Success Metric | Status |
| :--- | :--- | :--- | :---: |
| `EXP-001` | `openWakeWord` inference on Apple Silicon VM runs at <1% single-core CPU | CPU utilization < 1.0% during silence | 🔵 Planned |
| `EXP-002` | `sqlite-vec` extension provides sub-30ms retrieval across 50,000 embedded code chunks | Latency < 30ms on ARM64 | 🔵 Planned |

---

## Performance Targets vs Actuals

| Metric | Target | Current Actual | Status |
| :--- | :---: | :---: | :---: |
| **Wake-Word Latency** | < 150ms | Untested | ⚪ Baseline |
| **STT Time-to-First-Token** | < 300ms | Untested | ⚪ Baseline |
| **Intent Parsing Latency** | < 400ms | Untested | ⚪ Baseline |
| **TTS First Audio Chunk** | < 200ms | Untested | ⚪ Baseline |
| **Total End-to-End Voice Turnaround** | < 1200ms | Untested | ⚪ Baseline |
| **Idle System CPU Usage (All Daemons)**| < 2.5% | Untested | ⚪ Baseline |
| **Idle System RAM Usage** | < 350 MB | Untested | ⚪ Baseline |

---

## Milestone Progress

| Milestone | Target Version | Total Tasks | Completed | Progress | Target Date |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **M0: Foundation** | `v0.0.1-prealpha` | 10 | 4 | 40% | 2026-09-30 |
| **M1: Voice MVP** | `v0.1.0-alpha` | 10 | 0 | 0% | 2026-11-15 |
| **M2: Agent Runtime** | `v0.2.0-alpha` | 10 | 0 | 0% | 2026-12-31 |
| **M3: Memory Engine** | `v0.3.0-alpha` | 8 | 0 | 0% | 2027-02-15 |
| **M4: Context Engine** | `v0.4.0-alpha` | 8 | 0 | 0% | 2027-03-31 |
| **M5: Multi-Agent System**| `v0.5.0-beta` | 10 | 0 | 0% | 2027-05-15 |
| **M6: Native Desktop** | `v0.6.0-beta` | 10 | 0 | 0% | 2027-06-30 |
| **M7: OS Integration** | `v0.7.0-beta` | 8 | 0 | 0% | 2027-08-15 |
| **M8: Security Sandbox** | `v0.8.0-rc` | 8 | 0 | 0% | 2027-09-30 |
| **M9: Local AI** | `v0.9.0-rc` | 6 | 0 | 0% | 2027-11-15 |
| **M10: Distribution ISO** | `v1.0.0` | 6 | 0 | 0% | 2027-12-31 |

---

## Release Checklist (`v0.1.0-alpha` — Voice MVP)

- [ ] `SYS-005`: `aurad` launches cleanly and responds to heartbeat ping.
- [ ] `SYS-007`: `systemd` user service starts automatically on boot.
- [ ] `VOICE-001`: PipeWire audio stream captures mic input without buffer overrun.
- [ ] `VOICE-002`: Wake word "Aura" activates with >95% accuracy in quiet room.
- [ ] `VOICE-005`: `faster-whisper` transcribes command *"Create a folder called Test on my Desktop"*.
- [ ] `TOOL-001`: Folder `~/Desktop/Test` is created with verified filesystem existence.
- [ ] `VOICE-006`: `Piper TTS` audibly speaks confirmation.
- [ ] Zero unhandled python exceptions in `journalctl -u aura-core.service`.

---

## Recent Changes Log

| Date | Author | Task ID | Summary of Changes |
| :--- | :--- | :--- | :--- |
| 2026-09-21 | AI Architect | `SYS-001` | Initialized repository structure and directory hierarchy. |
| 2026-09-21 | AI Architect | `SYS-002` | Created authoritative technical specification ([ARCHITECTURE.md](file:///Users/aryansingh/Documents/Aura-OS/ARCHITECTURE.md)). |
| 2026-09-21 | AI Architect | `SYS-003` | Created 11-phase implementation plan ([PLAN.md](file:///Users/aryansingh/Documents/Aura-OS/PLAN.md)). |
| 2026-09-21 | AI Architect | `SYS-004` | Created canonical UI component registry ([UI-REGISTRY.md](file:///Users/aryansingh/Documents/Aura-OS/UI-REGISTRY.md)). |
| 2026-09-21 | AI Architect | `SYS-000` | Established live progress tracking system ([PROGRESS-TRACKER.md](file:///Users/aryansingh/Documents/Aura-OS/PROGRESS-TRACKER.md)). |

---

## Important Lessons Learned

1. **Virtualization Audio**: Under UTM on Apple Silicon, pass-through audio requires explicitly selecting VirtIO Sound with 48kHz native rate to avoid high-frequency distortion during speech recognition.
2. **Permission Boundaries**: Autonomous agents must never have ambient root access. The voice barrier rule (forcing interactive UI confirmation for destructive actions) must be hardcoded at the lowest IPC level.

---

## Next Session Objectives

1. Complete `SYS-005`: Implement `aura/core/main.py` entrypoint with asyncio event loop and UDS socket server.
2. Implement `SYS-006`: Write Makefile targets for VM provisioning and environment bootstrap (`make dev-setup`).
3. Begin `VOICE-001`: Write the audio capture module binding to PipeWire.
