"""
AURA OS — Brain
Turns a spoken/typed sentence into an action and a short spoken reply.
Order: (1) deterministic device intents (fast, offline, no cloud) -> (2) Gemini conversation
with tool use -> (3) offline rule planner.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from aura.agents.gemini import GeminiClient
from aura.agents.manager import AgentManager
from aura.agents.task import Task, TaskDAG
from aura.core.logger import logger
from aura.tools.registry import registry
from aura.tools.system import VIEWS

_VIEW_ALIASES = {
    "files": "files", "file": "files", "file manager": "files", "documents": "files",
    "terminal": "terminal", "console": "terminal", "command line": "terminal",
    "settings": "settings", "preferences": "settings", "configuration": "settings",
    "home": "home", "dashboard": "home", "main screen": "home", "desktop": "home",
    "agents": "agents", "agent": "agents",
    "system": "system", "system monitor": "system", "stats": "system", "status": "system",
    "browser": "browser", "web": "browser", "internet": "browser",
    "notes": "notebook", "notebook": "notebook",
    "smart home": "smarthome", "lights": "smarthome", "home automation": "smarthome",
    "automation": "automation", "automations": "automation", "routines": "automation",
    "research": "research", "apps": "applications", "applications": "applications",
}

_SYSTEM_PROMPT = """You are Aura, a voice assistant running as the operating system of a living-room TV.
Everything you say is spoken aloud: answer in one or two short plain sentences, no markdown, no lists.
You can act on the device with tools. Respond with ONLY a JSON object:
{{"reply": "<what to say>", "actions": [{{"tool": "<tool name>", "params": {{}}}}]}}
Use "actions": [] when no device action is needed. Only use these tools:
{tools}
HUD screens for ui.open_view: {views}.
Shell commands and deletions will ask the user to confirm first. Never invent tool names.
Current local time: {now}."""


class Brain:
    def __init__(self, agents: AgentManager, gemini: Optional[GeminiClient] = None) -> None:
        self.agents = agents
        self.gemini = gemini or GeminiClient(timeout_sec=20.0)
        self.history: List[Dict[str, str]] = []

    # ------------------------------------------------------------------ helpers
    async def _tool(self, name: str, **params: Any) -> Dict[str, Any]:
        return await registry.execute(name, **params)

    async def _run_actions(self, actions: List[Dict[str, Any]]) -> Optional[str]:
        """Run model-chosen tool calls through the permission-gated loop. Returns an error string."""
        dag = TaskDAG(goal_prompt="voice actions")
        prev: Optional[str] = None
        for a in actions[:5]:
            name = str(a.get("tool", ""))
            if registry.get_definition(name) is None:
                logger.warning(f"Model asked for unknown tool '{name}', ignoring.")
                continue
            params = a.get("params") if isinstance(a.get("params"), dict) else {}
            t = Task(title=f"{name} {params}"[:120], tool_name=name, params=params,
                     dependencies=[prev] if prev else [], max_retries=0)
            dag.add_task(t)
            prev = t.id
        if not dag.tasks:
            return None
        result = await self.agents.loop.run_dag(dag)
        if result["success"]:
            return None
        failed = [t for t in result["tasks"].values() if t["error"]]
        return failed[0]["error"] if failed else "an action failed"

    # ------------------------------------------------------------------ local intents
    async def _local_intent(self, text: str) -> Optional[Dict[str, Any]]:
        t = re.sub(r"[^\w\s%']", " ", text.lower()).strip()
        t = re.sub(r"\s+", " ", t)

        if re.search(r"\bwhat(?:'s| is)? (?:the )?time\b|\bcurrent time\b|\btime is it\b", t):
            r = (await self._tool("system.time"))["data"]
            return {"reply": f"It's {r['time']}."}
        if re.search(r"\bwhat(?:'s| is)? (?:the )?(?:date|day)\b|\btoday's date\b|\bwhat day\b", t):
            r = (await self._tool("system.time"))["data"]
            return {"reply": f"Today is {r['date']}."}

        if m := re.search(r"\b(?:set )?volume (?:to )?(\d{1,3})\b|\b(\d{1,3}) percent volume\b", t):
            lvl = m.group(1) or m.group(2)
            return await self._volume(lvl, f"Volume set to {min(100, int(lvl))} percent.")
        if re.search(r"\b(?:volume up|louder|turn it up|turn up the volume)\b", t):
            return await self._volume("up", "Turning it up.")
        if re.search(r"\b(?:volume down|quieter|turn it down|turn down the volume)\b", t):
            return await self._volume("down", "Turning it down.")
        if re.search(r"\bunmute\b", t):
            return await self._volume("unmute", "Unmuted.")
        if re.search(r"\bmute\b", t):
            return await self._volume("mute", "Muted.")

        if re.search(r"\b(?:system status|how(?:'s| is) the system|system health|how are you doing|cpu|temperature)\b", t):
            s = (await self._tool("system.status"))["data"]
            temp = f" Temperature is {s['temp_c']} degrees." if s.get("temp_c") else ""
            await self._tool("ui.open_view", view="system")
            return {"reply": f"CPU is at {s['cpu']:.0f} percent, memory {s['ram']:.0f} percent, "
                             f"disk {s['disk']:.0f} percent.{temp}"}

        if m := re.search(r"\b(?:open|show|go to|take me to|launch|switch to|display)(?: me)?(?: the)? ([a-z ]+?)(?: app| screen| view| page)?$", t):
            target = m.group(1).strip()
            view = _VIEW_ALIASES.get(target) or next(
                (v for k, v in _VIEW_ALIASES.items() if k == target.replace("my ", "")), None)
            if view:
                await self._tool("ui.open_view", view=view)
                return {"reply": f"Opening {view}."}

        if re.search(r"\b(?:go home|go back home|home screen)\b", t):
            await self._tool("ui.open_view", view="home")
            return {"reply": "Going home."}

        if re.search(r"\b(?:reboot|restart)\b.*\b(?:system|pi|computer|device|tv|yourself)\b", t):
            err = await self._run_actions([{"tool": "system.power", "params": {"action": "reboot"}}])
            return {"reply": "Rebooting now." if not err else "Okay, I won't reboot."}
        if re.search(r"\b(?:shut ?down|power off|turn off)\b.*\b(?:system|pi|computer|device|yourself)\b", t):
            err = await self._run_actions([{"tool": "system.power", "params": {"action": "shutdown"}}])
            return {"reply": "Shutting down. Goodbye." if not err else "Okay, I'll stay on."}
        return None

    async def _volume(self, level: str, reply: str) -> Dict[str, Any]:
        res = await self._tool("system.set_volume", level=level)
        return {"reply": reply} if res["success"] else {"reply": "I can't control the volume on this device.", "error": res["error"]}

    # ------------------------------------------------------------------ main entry
    async def handle(self, text: str) -> Dict[str, Any]:
        """Returns {reply, success, source}."""
        text = text.strip()
        local = await self._local_intent(text)
        if local is not None:
            return {"success": "error" not in local, "source": "local", **local}

        if self.gemini.is_configured():
            import asyncio

            system = _SYSTEM_PROMPT.format(
                tools="\n".join(f"- {d.name}: {d.description} params={list(d.parameters)}"
                                for d in registry.get_definitions()),
                views=", ".join(VIEWS),
                now=time.strftime("%A %d %B %Y, %I:%M %p"),
            )
            out = await asyncio.to_thread(self.gemini.chat_json, self.history[-8:], text, system)
            if out and isinstance(out.get("reply"), str):
                err = None
                actions = out.get("actions")
                if isinstance(actions, list) and actions:
                    err = await self._run_actions([a for a in actions if isinstance(a, dict)])
                self.history += [{"role": "user", "text": text}, {"role": "model", "text": out["reply"]}]
                self.history = self.history[-16:]
                reply = out["reply"] if not err else f"Sorry, that didn't work: {err}"
                return {"success": err is None, "source": "gemini", "reply": reply}
            logger.warning("Gemini unavailable for this request; using offline planner.")

        result = await self.agents.execute_goal(text)
        tasks = list(result.get("tasks", {}).values())
        had_tools = any(t.get("result") is not None for t in tasks)
        if result["success"] and had_tools:
            return {"success": True, "source": "planner", "reply": "Done.", "result": result}
        if not result["success"]:
            errs = [t["error"] for t in tasks if t.get("error")]
            return {"success": False, "source": "planner", "result": result,
                    "reply": "I couldn't do that." if not errs else f"I couldn't do that: {errs[0]}"}
        offline = "" if self.gemini.is_configured() else " I'm offline, so I only understand device commands."
        return {"success": False, "source": "none", "result": result,
                "reply": f"Sorry, I didn't understand that.{offline} Try 'open files' or 'what time is it'."}
