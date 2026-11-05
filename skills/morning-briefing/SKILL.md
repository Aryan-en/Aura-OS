---
name: morning-briefing
description: Spoken start-of-day briefing with time, system health and your latest report
triggers: ["morning briefing", "good morning", "brief me", "start my day"]
tier: 1
actions:
  - tool: system.time
  - tool: system.status
  - tool: ui.open_view
    params: {view: home}
speak: "Good morning. It's {time} on {date}. The system is healthy, CPU at {cpu} percent."
---
Deterministic skill: no AI call is made. Extend `actions` to add more steps.
