---
name: focus-mode
description: Mute audio and show the notes vault for deep work
triggers: ["focus mode", "start focus", "let me focus"]
tier: 1
actions:
  - tool: system.set_volume
    params: {level: mute}
  - tool: ui.open_view
    params: {view: notebook}
speak: "Focus mode on. I'll stay quiet."
---
Mutes output and opens the vault. Say "unmute" to end it.
