# Aura as an Agentic OS: three layers + a router

| Layer | What it is in Aura | Where |
| :--- | :--- | :--- |
| 1. Visual interface | The HUD on your TV: voice orb, captions, **Vault** and **Skills & Router** screens | `aura/ui/` |
| 2. Memory | An Obsidian-compatible markdown vault: `raw/` (captures) → `wiki/` (organised articles) → `outputs/` (deliverables) | `aura/vault/`, `~/AuraVault` |
| 3. Skill backbone | `SKILL.md` files (frontmatter + instructions), a log audit and a voice-dump mapper that draft new skills | `aura/skills/`, `skills/` |
| Router | Tier 1 instant / Tier 2 fast model / Tier 3 worker agent | `aura/agents/router.py` |

## Memory vault
Open `~/AuraVault` in Obsidian (or any editor); Aura reads and writes the same plain files.
- "Aura, **note that** the Pi needs a USB mic" → `raw/` (no AI, instant).
- "**Update my wiki**" → Gemini turns new raw captures into linked wiki articles and marks them `compiled`.
  Without a key, raw notes are left alone (never silently copied into the wiki).
- "**Search my notes for** microphone", "**read my latest report**" → answered from the vault, no AI.
- Tier-2 answers automatically get the top matching wiki/raw notes as context.

## Skills
```
skills/<name>/SKILL.md        # shipped with Aura
~/.config/aura/skills/<name>/ # yours (overrides shipped ones)
```
`triggers` fire the skill instantly with **no AI call**. `actions` are fixed tool steps (they still pass the
permission gate); without `actions` the body is instructions run at `tier` 2 or 3. See
`skills/morning-briefing/SKILL.md`. Say "what can you do" to hear your skills.

**Finding what to automate (HUD → Skills & Router):**
1. *Audit last 30 days* mines every request Aura handled (stored in the `interactions` table) for repeats and,
   with a Gemini key, drafts skills for them.
2. *Describe your workday*: paste or dictate 10-20 minutes of what you do; Aura drafts skills from it.
Both only create **drafts**. Nothing runs until you press Approve. Drafts can only use tools that exist.

## Router
| Tier | Handles | Cost |
| :--- | :--- | :--- |
| 1 | skill triggers, vault capture/search/report, device commands (time, volume, open screens, power) | none, ~ms |
| 2 | everything else conversational, with vault context + tools. Model: `router.fast_model` (default `gemini-2.5-flash-lite`) | cheap |
| 3 | build/implement/refactor/long research/report requests, or when tier 2 sets `escalate` | heavy |

Tier 3 hands the task to a worker CLI (`claude -p` or `codex exec`, auto-detected; set `router.tier3_command`),
in `router.tier3_workspace`. It **asks for approval first**, runs in the background, saves the result to
`outputs/` and speaks when finished. With no worker installed it falls back to the tool planner.
The HUD shows live tier counts. Config (`~/.config/aura/aura.yaml`):
```yaml
router: {fast_model: gemini-2.5-flash-lite, tier3_command: auto, tier3_args: [], tier3_workspace: ~/aura-workspace}
vault:  {path: ~/AuraVault}
```
**Hardware note:** the Pi 3B+ (1 GB) can't realistically run Claude Code/Codex; use the planner fallback there,
or point tier 3 at a stronger machine later.

## Fully local voice (Pi 4/5 or a PC)
`pip install '.[rpi]'` for Whisper STT (already used when installed). For neural local TTS:
```bash
pip install '.[kokoro]'
mkdir -p ~/.local/share/kokoro && cd ~/.local/share/kokoro
# download kokoro-v1.0.onnx and voices-v1.0.bin from the kokoro-onnx releases
```
TTS order in `auto`: Kokoro → Piper → espeak. Voice: `AURA_KOKORO_VOICE` (default `af_heart`).
