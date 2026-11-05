"""
AURA OS — Skill Backbone (Layer 3)
A skill is a folder with a SKILL.md: YAML frontmatter + markdown instructions.

    ---
    name: morning-briefing
    description: Spoken start-of-day briefing
    triggers: ["morning briefing", "good morning"]   # phrases that fire it with NO AI call (tier 1)
    tier: 1                                          # 1 = deterministic, 2 = fast model, 3 = worker agent
    actions:                                         # optional deterministic tool steps
      - tool: system.time
      - tool: ui.open_view
        params: {view: home}
    speak: "Good morning. It is {time}."             # {placeholders} come from tool results; {args} = rest of request
    ---
    Free-form instructions used when there are no `actions` (tier 2/3).

Skill sources: <repo>/skills, ~/.config/aura/skills. Drafts proposed by the audit live in
~/.config/aura/skills/_drafts and do nothing until approved.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from aura.core.logger import logger

REPO_SKILLS = Path(__file__).resolve().parents[2] / "skills"
USER_SKILLS = Path.home() / ".config" / "aura" / "skills"


@dataclass
class Skill:
    name: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    tier: int = 2
    actions: List[Dict[str, Any]] = field(default_factory=list)
    speak: str = ""
    body: str = ""
    path: Optional[Path] = None
    draft: bool = False

    def public(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "triggers": self.triggers,
                "tier": self.tier, "steps": len(self.actions), "draft": self.draft}


class _Safe(dict):  # type: ignore[type-arg]
    def __missing__(self, key: str) -> str:
        return ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.lower())).strip()


def parse_skill(path: Path, draft: bool = False) -> Optional[Skill]:
    try:
        raw = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
        if not m:
            return None
        meta = yaml.safe_load(m.group(1)) or {}
        name = str(meta["name"]).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", name):
            return None
        return Skill(
            name=name, description=str(meta.get("description", "")),
            triggers=[_norm(t) for t in meta.get("triggers", []) if str(t).strip()],
            tier=int(meta.get("tier", 1 if meta.get("actions") else 2)),
            actions=[a for a in meta.get("actions", []) if isinstance(a, dict) and a.get("tool")],
            speak=str(meta.get("speak", "")), body=m.group(2).strip(), path=path, draft=draft,
        )
    except Exception as e:
        logger.warning(f"Skipping invalid skill {path}: {e}")
        return None


class SkillRegistry:
    def __init__(self, dirs: Optional[List[Path]] = None) -> None:
        self.dirs = dirs if dirs is not None else [REPO_SKILLS, USER_SKILLS]
        self.skills: Dict[str, Skill] = {}
        self.reload()

    @property
    def drafts_dir(self) -> Path:
        return self.dirs[-1] / "_drafts"

    def reload(self) -> None:
        self.skills = {}
        for d in self.dirs:
            for f in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
                s = parse_skill(f)
                if s:
                    self.skills[s.name] = s  # later dirs (user) override repo skills

    def list(self, drafts: bool = False) -> List[Dict[str, Any]]:
        if drafts:
            return [s.public() for s in self.list_drafts()]
        return [s.public() for s in self.skills.values()]

    def list_drafts(self) -> List[Skill]:
        d = self.drafts_dir
        found = [parse_skill(f, draft=True) for f in sorted(d.glob("*/SKILL.md"))] if d.is_dir() else []
        return [s for s in found if s]

    def match(self, text: str) -> Optional[Tuple[Skill, str]]:
        """Exact trigger phrase (optionally with a wake/filler prefix or trailing args). Longest trigger wins."""
        t = _norm(text)
        best: Optional[Tuple[Skill, str, int]] = None
        for s in self.skills.values():
            for trig in s.triggers:
                if t == trig or t.startswith(trig + " "):
                    if best is None or len(trig) > best[2]:
                        best = (s, t[len(trig):].strip(), len(trig))
        return (best[0], best[1]) if best else None

    def get(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    # ---- drafts ----
    def save_draft(self, name: str, description: str, triggers: List[str], body: str,
                   actions: Optional[List[Dict[str, Any]]] = None, tier: int = 2) -> Path:
        name = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:48] or "skill"
        folder = self.drafts_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        meta: Dict[str, Any] = {"name": name, "description": description, "triggers": triggers, "tier": tier}
        if actions:
            meta["actions"] = actions
        f = folder / "SKILL.md"
        f.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()}\n---\n\n{body.strip()}\n")
        return f

    def approve(self, name: str) -> bool:
        src = self.drafts_dir / name
        if not (src / "SKILL.md").is_file() or not re.fullmatch(r"[a-z0-9-]+", name):
            return False
        dst = self.dirs[-1] / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))
        self.reload()
        return True

    def reject(self, name: str) -> bool:
        src = self.drafts_dir / name
        if re.fullmatch(r"[a-z0-9-]+", name) and src.is_dir():
            shutil.rmtree(src)
            return True
        return False

    @staticmethod
    def format_speak(skill: Skill, ctx: Dict[str, Any], args: str) -> str:
        return skill.speak.format_map(_Safe({**ctx, "args": args})).strip() if skill.speak else ""
