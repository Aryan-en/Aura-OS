"""Tests for the vault, skill backbone, skill audit and the three-tier router."""

import asyncio
import json
import os
import stat
import tempfile
import time
from pathlib import Path

import pytest

from aura.agents.manager import AgentManager
from aura.agents.permissions import PermissionGate
from aura.agents.router import Router
from aura.core.config import RouterConfig
from aura.core.events import bus
from aura.memory.db import MemoryDB
from aura.skills.audit import audit_history, from_voice_dump
from aura.skills.registry import REPO_SKILLS, SkillRegistry
from aura.vault import set_vault
from aura.vault.vault import Vault


def tmp() -> Path:
    return Path(tempfile.mkdtemp())


# ---------------------------------------------------------------- vault
def test_vault_layout_and_capture_search() -> None:
    v = Vault(tmp() / "vault")
    assert {p.name for p in v.root.iterdir() if p.is_dir()} == {"raw", "wiki", "outputs"}
    rel = v.add_raw("Pi kiosk idea", "Use cage and chromium kiosk for the HDMI display on the Raspberry Pi")
    assert rel.startswith("raw/")
    hits = v.search("what do my notes say about chromium kiosk")
    assert hits and hits[0]["path"] == rel
    assert v.read(rel)["meta"]["status"] == "new"
    assert v.search("zebra") == []


def test_vault_rejects_path_escape() -> None:
    v = Vault(tmp() / "vault")
    for bad in ("../secret.md", "/etc/passwd", "raw/../../x.md", "README.md"):
        with pytest.raises((ValueError, FileNotFoundError)):
            v.read(bad)
    with pytest.raises(ValueError):
        v.write("raw", "x", "y")


def test_vault_compile_raw_to_wiki_needs_llm_and_marks_status() -> None:
    v = Vault(tmp() / "vault")
    rel = v.add_raw("meeting", "decided to ship the lite profile first")
    assert v.compile_raw(None)["compiled"] == 0  # no LLM: raw is left alone
    assert v.list("wiki") == []

    def fake_llm(system: str, prompt: str) -> str:
        return json.dumps({"title": "Lite Profile Decision", "article": "We ship **lite** first.", "tags": ["pi"]})

    res = v.compile_raw(fake_llm)
    assert res["compiled"] == 1
    assert v.read(rel)["meta"]["status"] == "compiled"
    assert v.read("wiki/lite-profile-decision.md")["meta"]["sources"] == [rel]
    assert v.compile_raw(fake_llm)["pending"] == 0


# ---------------------------------------------------------------- skills
def test_builtin_skills_parse_and_match() -> None:
    reg = SkillRegistry(dirs=[REPO_SKILLS, tmp()])
    assert {"morning-briefing", "focus-mode", "weekly-review"} <= set(reg.skills)
    skill, args = reg.match("Good morning!")  # type: ignore[misc]
    assert skill.name == "morning-briefing" and args == ""
    assert reg.match("good morning to you") is not None  # trigger + trailing words
    assert reg.match("goodmorning") is None
    assert reg.skills["weekly-review"].tier == 3


def test_skill_drafts_require_approval() -> None:
    user = tmp()
    reg = SkillRegistry(dirs=[REPO_SKILLS, user])
    reg.save_draft("Do Thing!", "desc", ["do the thing"], "body", actions=[{"tool": "system.time"}])
    assert "do-thing" not in reg.skills and reg.match("do the thing") is None  # inert until approved
    assert [d["name"] for d in reg.list(drafts=True)] == ["do-thing"]
    assert reg.approve("do-thing") and reg.match("do the thing")
    assert not reg.approve("../../etc")


def test_audit_finds_repeats_and_voice_dump_makes_drafts_only() -> None:
    db = MemoryDB(tmp() / "t.db")
    for _ in range(3):
        db.record_interaction("send my standup update 1", 2, "gemini", True, 10)
    db.record_interaction("what time is it", 1, "local", True, 1)
    rep = audit_history(db, 30, llm=None)
    assert rep["repeated"][0]["count"] == 3 and rep["by_tier"] == {2: 3, 1: 1}

    reg = SkillRegistry(dirs=[tmp(), tmp()])
    llm = lambda s, p: json.dumps([{"name": "standup", "description": "d", "triggers": ["standup"],  # noqa: E731
                                    "actions": [{"tool": "system.time"}, {"tool": "rm.everything"}]}])
    out = from_voice_dump("I start my day by checking email then I write a standup update for the team " * 2,
                          llm, reg, tools=["system.time"])
    assert out["drafts"] == ["standup"]
    assert [a["tool"] for a in reg.list_drafts()[0].actions] == ["system.time"]  # unknown tool dropped
    assert reg.skills == {}
    assert from_voice_dump("short", llm, reg)["drafts"] == []


# ---------------------------------------------------------------- router
def make_router(cfg: RouterConfig | None = None, gate_timeout: float = 5.0) -> tuple[Router, Vault, MemoryDB]:
    d = tmp()
    mem = MemoryDB(d / "r.db")
    vault = Vault(d / "vault")
    set_vault(vault)
    agents = AgentManager(memory_db=mem, gate=PermissionGate(timeout_sec=gate_timeout))
    return Router(agents, vault, SkillRegistry(dirs=[REPO_SKILLS, d / "skills"]), mem,
                  cfg or RouterConfig(tier3_command="none")), vault, mem


def test_tier1_needs_no_ai_and_is_logged() -> None:
    async def _run() -> None:
        r, vault, mem = make_router()
        out = await r.handle("morning briefing")  # skill, deterministic
        assert out["tier"] == 1 and out["source"] == "skill:morning-briefing" and "Good morning" in out["reply"]
        out = await r.handle("note that the pi needs a usb microphone")
        assert out["tier"] == 1 and vault.pending_raw()
        out = await r.handle("search my notes for microphone")
        assert out["tier"] == 1 and "microphone" in out["reply"].lower()
        out = await r.handle("what time is it")
        assert out["tier"] == 1
        assert r.counts[1] == 4 and len(mem.list_interactions()) == 4

    asyncio.run(_run())


def test_heavy_requests_go_to_tier3_and_without_worker_fall_back_safely() -> None:
    async def _run() -> None:
        r, _, _ = make_router()
        out = await r.handle("build me a script that renames my photos")
        assert out["tier"] == 3
        out = await r.handle("tell me a joke")
        assert out["tier"] == 2

    asyncio.run(_run())


def test_tier3_worker_requires_approval_runs_in_background_and_publishes_output() -> None:
    async def _run() -> None:
        bindir = tmp()
        fake = bindir / "claude"
        fake.write_text("#!/bin/sh\necho \"worker did: $2\"\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        old = os.environ["PATH"]
        os.environ["PATH"] = f"{bindir}:{old}"
        try:
            ws = tmp()
            r, vault, _ = make_router(RouterConfig(tier3_command="claude", tier3_workspace=str(ws)))
            start = bus.last_id

            # 1. denied -> nothing runs
            r.agents.gate.timeout_sec = 0.05
            out = await r.handle("implement a todo app")
            assert out["tier"] == 3 and out["success"] is False and not r.jobs

            # 2. approved -> background job, vault output, spoken completion event
            r.agents.gate.timeout_sec = 5
            task = asyncio.create_task(r.handle("implement a todo app"))
            await asyncio.sleep(0.05)
            r.agents.gate.resolve(True)
            out = await task
            assert out["success"] and "tell you when it's done" in out["reply"]
            for _ in range(100):
                if any(e["type"] == "job.done" for e in bus.since(start)):
                    break
                await asyncio.sleep(0.05)
            done = [e for e in bus.since(start) if e["type"] == "job.done"][-1]
            assert done["ok"] is True
            assert "worker did: implement a todo app" in vault.read(done["output"])["body"]
        finally:
            os.environ["PATH"] = old

    asyncio.run(_run())


def test_audit_log_feeds_from_router() -> None:
    async def _run() -> None:
        r, _, mem = make_router()
        for _ in range(2):
            await r.handle("what time is it")
        rep = audit_history(mem, 1)
        assert rep["interactions"] == 2 and rep["repeated"][0]["count"] == 2
        assert time.time() > 0

    asyncio.run(_run())
