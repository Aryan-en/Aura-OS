"""AURA OS — Vault tools: let agents and voice capture, search, read and publish knowledge."""

from __future__ import annotations

from typing import Any, Dict

from aura.tools.registry import registry
from aura.vault import get_vault


@registry.register("vault.add_note", description="Save a quick capture to the vault's raw/ inbox (title, text).")
async def tool_add_note(title: str, text: str) -> Dict[str, Any]:
    return {"path": get_vault().add_raw(title, text)}


@registry.register("vault.search", description="Search the user's vault (raw, wiki, outputs) by keywords.")
async def tool_search(query: str, limit: int = 5) -> Dict[str, Any]:
    return {"results": get_vault().search(query, int(limit))}


@registry.register("vault.read", description="Read a vault note by vault-relative path, e.g. wiki/foo.md.")
async def tool_read(path: str) -> Dict[str, Any]:
    return get_vault().read(path)


@registry.register("vault.write_output", description="Publish a finished deliverable (report, brief) to outputs/.")
async def tool_write_output(title: str, body: str) -> Dict[str, Any]:
    return {"path": get_vault().write("outputs", title, body)}
