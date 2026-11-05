"""
AURA OS — Three-tier request router
  Tier 1  instant, no AI:   skill triggers, vault capture/search/report retrieval, device commands
  Tier 2  quick thinking:   small fast model (e.g. gemini-flash-lite) with vault context + tools
  Tier 3  heavy work:       a worker agent (Claude Code `claude -p` / Codex `codex exec`) in a workspace,
                            run in the background after you approve it; falls back to the planner
Every request is logged to the interaction table, which feeds the skill audit.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from aura.agents.brain import Brain
from aura.agents.gemini import GeminiClient
from aura.agents.manager import AgentManager
from aura.agents.task import Task, TaskDAG
from aura.core.config import RouterConfig
from aura.core.events import bus
from aura.core.logger import logger
from aura.memory.db import MemoryDB
from aura.skills.registry import Skill, SkillRegistry
from aura.tools.registry import registry
from aura.vault.vault import Vault

_HEAVY = re.compile(
    r"\b(build|implement|refactor|debug|write (?:me )?(?:a|an|the) (?:script|program|app|function|report|essay|"
    r"article|deck|slides|plan|proposal)|create (?:a|an) (?:app|website|project|presentation|slide deck|report)|"
    r"research (?:and|into)|deep dive|analy[sz]e (?:my|the) (?:repo|codebase|project|data)|"
    r"(?:fix|review) (?:the|my) (?:code|bug|tests?|repo))\b", re.I)

_NOTE = re.compile(r"^(?:take a note|note|remember|save (?:a )?note|jot down|capture)(?: that| this| to my notes)?[:,]?\s+(.+)$", re.I)
_SEARCH = re.compile(r"^(?:search|look up|find)(?: my)?(?: notes| vault| wiki)?(?: for| about)?\s+(.+)$|"
                     r"^what (?:do|did) my (?:notes|wiki|vault) (?:say|have)(?: about)?\s+(.+)$|"
                     r"^what do i know about\s+(.+)$", re.I)
_COMPILE = re.compile(r"\b(?:update|compile|organi[sz]e|process|sync) (?:my )?(?:wiki|notes|inbox|vault)\b", re.I)
_REPORT = re.compile(r"\b(?:read|show|open|play)(?: me)?(?: my| the)?(?: latest| last| newest)? (?:report|brief|output|deliverable)\b", re.I)
_SKILLS = re.compile(r"\b(?:what can you do|list (?:my )?skills|what skills)\b", re.I)


class Router:
    def __init__(self, agents: AgentManager, vault: Vault, skills: SkillRegistry,
                 memory: Optional[MemoryDB], cfg: Optional[RouterConfig] = None,
                 gemini: Optional[GeminiClient] = None, fast: Optional[GeminiClient] = None) -> None:
        self.agents, self.vault, self.skills, self.memory = agents, vault, skills, memory
        self.cfg = cfg or RouterConfig()
        self.gemini = gemini or GeminiClient(timeout_sec=30.0)
        self.fast = fast or GeminiClient(model=self.cfg.fast_model, timeout_sec=15.0)
        self.brain = Brain(agents, gemini=self.fast)
        self.counts: Counter[int] = Counter()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._bg: set[asyncio.Task[Any]] = set()

    @property
    def clients(self) -> List[GeminiClient]:
        return [self.gemini, self.fast, self.brain.gemini]

    # ------------------------------------------------------------------ entry
    async def handle(self, text: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        text = text.strip()
        out = await self._tier1(text)
        tier = 1
        if out is None:
            ctx = self._vault_context(text)
            if _HEAVY.search(text):
                tier, out = 3, await self._tier3(text)
            else:
                tier, out = 2, await self.brain.handle(text, context=ctx, skip_local=True)
                if out.get("escalate"):
                    tier, out = 3, await self._tier3(text, ack=out["reply"])
        out.setdefault("success", True)
        out["tier"] = tier
        self.counts[tier] += 1
        ms = (time.perf_counter() - t0) * 1000
        handler = out.get("source", "?")
        bus.emit("router.decision", tier=tier, handler=handler, ms=round(ms))
        if self.memory:
            try:
                self.memory.record_interaction(text, tier, handler, bool(out["success"]), ms)
            except Exception as e:  # logging must never break the reply
                logger.warning(f"interaction log failed: {e}")
        return out

    def stats(self) -> Dict[str, Any]:
        return {"by_tier": dict(self.counts), "jobs": list(self.jobs.values())[-10:],
                "tier3_worker": self._worker_name() or "planner fallback",
                "fast_model": self.fast.model, "main_model": self.gemini.model}

    # ------------------------------------------------------------------ tier 1
    async def _tier1(self, text: str) -> Optional[Dict[str, Any]]:
        m = self.skills.match(text)
        if m:
            return await self.run_skill(m[0], m[1])
        t = text.strip().rstrip("?.!")
        if mm := _NOTE.match(t):
            note = mm.group(1).strip()
            path = self.vault.add_raw(note[:50], note, source="voice")
            return {"success": True, "source": "vault", "reply": "Saved to your inbox.", "path": path}
        if _COMPILE.search(t):
            return await self.compile_wiki()
        if _REPORT.search(t):
            doc = self.vault.latest("outputs")
            if not doc:
                return {"success": True, "source": "vault", "reply": "You don't have any reports yet."}
            await registry.execute("ui.open_view", view="notebook")
            return {"success": True, "source": "vault", "reply": f"{doc['title']}. {doc['body'][:400]}"}
        if mm := _SEARCH.match(t):
            q = next(g for g in mm.groups() if g)
            hits = self.vault.search(q, 3)
            if not hits:
                return {"success": True, "source": "vault", "reply": f"I found nothing about {q} in your vault."}
            top = hits[0]
            snip = top["snippet"][:240]
            said = snip if top["title"].lower()[:30] in snip.lower() else f"From {top['title']}: {snip}"
            return {"success": True, "source": "vault", "reply": said, "results": hits}
        if _SKILLS.search(t):
            names = ", ".join(s.name.replace("-", " ") for s in self.skills.skills.values())
            return {"success": True, "source": "skills", "reply": f"My skills are: {names}."}
        return await self.brain.try_local(text)

    # ------------------------------------------------------------------ skills
    async def run_skill(self, skill: Skill, args: str = "") -> Dict[str, Any]:
        bus.emit("skill.run", name=skill.name)
        if skill.actions:
            dag = TaskDAG(goal_prompt=f"skill:{skill.name}")
            prev: Optional[str] = None
            for a in skill.actions:
                params = a.get("params") if isinstance(a.get("params"), dict) else {}
                t = Task(title=f"{skill.name}: {a['tool']}", tool_name=str(a["tool"]), params=params,
                         dependencies=[prev] if prev else [], max_retries=0)
                dag.add_task(t)
                prev = t.id
            result = await self.agents.loop.run_dag(dag)
            ctx: Dict[str, Any] = {}
            for t in result["tasks"].values():
                if isinstance(t.get("result"), dict):
                    ctx.update(t["result"])
            if result["success"]:
                reply = SkillRegistry.format_speak(skill, ctx, args) or "Done."
                return {"success": True, "source": f"skill:{skill.name}", "reply": reply}
            err = next((t["error"] for t in result["tasks"].values() if t.get("error")), "a step failed")
            return {"success": False, "source": f"skill:{skill.name}", "reply": f"The {skill.name} skill stopped: {err}."}
        prompt = f"{skill.body}\n\nUser request: {args or skill.description}"
        if skill.tier >= 3:
            out = await self._tier3(prompt, title=skill.name)
        else:
            out = await self.brain.handle(prompt, context=self._vault_context(prompt), skip_local=True)
        out["source"] = f"skill:{skill.name}"
        return out

    # ------------------------------------------------------------------ vault helpers
    def _vault_context(self, text: str) -> str:
        try:
            hits = self.vault.search(text, 3, areas=("wiki", "raw"))
        except Exception:
            return ""
        return "\n".join(f"- [{h['title']}] {h['snippet']}" for h in hits)

    def _llm(self) -> Optional[Any]:
        if not self.gemini.is_configured():
            return None
        return lambda system, prompt: self.gemini.generate_text(prompt, system=system, json_mode=True, max_tokens=4096)

    async def compile_wiki(self) -> Dict[str, Any]:
        res = await asyncio.to_thread(self.vault.compile_raw, self._llm())
        if res["compiled"]:
            reply = f"Organised {res['compiled']} new note{'s' if res['compiled'] != 1 else ''} into your wiki."
        else:
            reply = res.get("note") or "I couldn't organise those notes."
        return {"success": res["compiled"] > 0 or res["pending"] == 0, "source": "vault", "reply": reply, "result": res}

    # ------------------------------------------------------------------ tier 3
    def _worker_name(self) -> Optional[str]:
        want = self.cfg.tier3_command
        if want == "none":
            return None
        for name in ([want] if want != "auto" else ["claude", "codex"]):
            if shutil.which(name):
                return name
        return None

    def _worker_cmd(self, name: str, task: str) -> List[str]:
        base = ["claude", "-p", task] if name == "claude" else ["codex", "exec", task]
        return base + list(self.cfg.tier3_args)

    async def _tier3(self, task: str, ack: Optional[str] = None, title: str = "task") -> Dict[str, Any]:
        worker = self._worker_name()
        if worker is None:
            # No worker CLI: use the planner (main model) for tool-level work.
            res = await self.agents.execute_goal(task)
            ok = res["success"]
            return {"success": ok, "source": "planner",
                    "reply": "Done." if ok else "I couldn't do that without a coding agent installed."}
        approved = await self.agents.gate.request(f"hand this to {worker}: {task[:90]}", tool="agent.tier3")
        if not approved:
            return {"success": False, "source": "tier3", "reply": "Okay, I won't start that."}
        job_id = uuid.uuid4().hex[:6]
        self.jobs[job_id] = {"id": job_id, "title": task[:80], "worker": worker, "status": "running",
                             "started": time.time()}
        bt = asyncio.get_running_loop().create_task(self._run_worker(job_id, worker, task, title))
        self._bg.add(bt)
        bt.add_done_callback(self._bg.discard)
        bus.emit("job.started", job=job_id, worker=worker, title=task[:80])
        return {"success": True, "source": "tier3",
                "reply": (ack or "On it.") + " I'll tell you when it's done.", "job": job_id}

    async def _run_worker(self, job_id: str, worker: str, task: str, title: str) -> None:
        job = self.jobs[job_id]
        ws = Path(self.cfg.tier3_workspace).expanduser()
        ws.mkdir(parents=True, exist_ok=True)
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._worker_cmd(worker, task), cwd=str(ws),
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            try:
                out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=self.cfg.tier3_timeout_sec)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError(f"timed out after {int(self.cfg.tier3_timeout_sec)}s") from None
            out = out_b.decode("utf-8", "replace").strip()[-20000:]
            if proc.returncode != 0:
                raise RuntimeError(out[-300:] or f"exit code {proc.returncode}")
            path = self.vault.write("outputs", title if title != "task" else task[:50], out or "(no output)",
                                    {"source": f"tier3:{worker}", "task": task[:300]})
            job.update(status="done", output=path)
            summary = re.sub(r"\s+", " ", out)[:200]
            bus.emit("job.done", job=job_id, ok=True, reply=f"Finished. {summary}", output=path)
        except Exception as e:
            job.update(status="failed", error=str(e)[:300])
            bus.emit("job.done", job=job_id, ok=False, reply=f"The background task failed: {str(e)[:120]}")
