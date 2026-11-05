---
name: capture-inbox
description: Show the vault inbox of unprocessed captures
triggers: ["show my inbox", "open my inbox", "what's in my inbox"]
tier: 1
actions:
  - tool: ui.open_view
    params: {view: notebook}
speak: "Here is your vault. Say 'update my wiki' to organise new captures."
---
Opens the vault view where raw/ captures wait to be compiled into the wiki.
