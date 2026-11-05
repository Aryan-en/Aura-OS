"""
AURA OS — Skill discovery
  * audit_history(): mine the last N days of interactions for repeated requests worth turning into skills.
  * from_voice_dump(): turn a 10-20 minute spoken description of your workday into draft skills.
Both only ever produce DRAFTS; nothing runs until you approve it.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional

from aura.memory.db import MemoryDB
from aura.skills.registry import SkillRegistry

LLM = Callable[[str, str], str]  # (system, prompt) -> text

_SKILL_SYSTEM = """You design automation skills for a voice-first OS. A skill is:
{"name": "kebab-case", "description": "one line", "triggers": ["short spoken phrases"],
 "tier": 1|2|3, "actions": [{"tool": "<tool>", "params": {}}], "speak": "optional template", "instructions": "markdown"}
Tiers: 1 = fixed tool steps with no AI, 2 = quick thinking with a small model, 3 = complex multi-step work
by a coding/research agent. Only use these tools in `actions`: {tools}.
Prefer tier 1 whenever the task is repeatable and fixed. Return ONLY a JSON array of skills."""


def _pattern_key(text: str) -> str:
    t = re.sub(r"\d+", "#", re.sub(r"[^\w\s#']", " ", text.lower()))
    return " ".join(t.split()[:4])


def audit_history(db: MemoryDB, days: int = 30, llm: Optional[LLM] = None,
                  tools: Optional[List[str]] = None, min_count: int = 2) -> Dict[str, Any]:
    rows = db.list_interactions(since_ts=time.time() - days * 86400)
    groups: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        groups[_pattern_key(r["text"])].append(r["text"])
    repeated = [{"pattern": k, "count": len(v), "examples": list(dict.fromkeys(v))[:3]}
                for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])) if len(v) >= min_count]
    tiers = Counter(r["tier"] for r in rows)
    failures = [r["text"] for r in rows if not r["success"]][:10]
    report: Dict[str, Any] = {
        "days": days, "interactions": len(rows), "by_tier": dict(tiers),
        "repeated": repeated[:15], "failed_requests": failures, "suggestions": [],
    }
    if llm and repeated:
        report["suggestions"] = _ask_for_skills(
            llm, "These requests repeat often. Propose skills that would automate them:\n"
                 + json.dumps(repeated[:10]), tools or [])
    elif not llm:
        report["note"] = "Add a Gemini key to get AI-drafted skill suggestions."
    return report


def _ask_for_skills(llm: LLM, prompt: str, tools: List[str]) -> List[Dict[str, Any]]:
    try:
        raw = llm(_SKILL_SYSTEM.replace("{tools}", ", ".join(tools) or "none"), prompt)
        data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
        return [d for d in data if isinstance(d, dict) and d.get("name")] if isinstance(data, list) else []
    except Exception:
        return []


def from_voice_dump(text: str, llm: Optional[LLM], registry: SkillRegistry,
                    tools: Optional[List[str]] = None) -> Dict[str, Any]:
    if not llm:
        return {"drafts": [], "error": "Mapping a voice dump to skills needs a Gemini key."}
    if len(text.split()) < 20:
        return {"drafts": [], "error": "Describe your workday in more detail (at least a few sentences)."}
    skills = _ask_for_skills(llm, "Describe-your-day transcript:\n" + text[:20000], tools or [])
    saved = []
    for s in skills[:12]:
        valid_tools = set(tools or [])
        actions = [a for a in s.get("actions", []) if isinstance(a, dict) and a.get("tool") in valid_tools]
        registry.save_draft(
            str(s["name"]), str(s.get("description", "")),
            [str(t) for t in s.get("triggers", [])], str(s.get("instructions", "")),
            actions=actions, tier=1 if actions else int(s.get("tier", 2)) if str(s.get("tier", 2)).isdigit() else 2)
        saved.append(str(s["name"]))
    return {"drafts": saved}
