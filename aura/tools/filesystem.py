"""
AURA OS — Filesystem Tools
Safe filesystem manipulation primitives with path boundary validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from aura.tools.registry import registry


def _resolve_safe_path(raw_path: str) -> Path:
    """Resolve and validate a filesystem path, expanding ~ and stripping dangerous sequences."""
    expanded = os.path.expanduser(raw_path.strip())
    resolved = Path(expanded).resolve()
    # Reject root deletion / system directory destruction
    system_forbidden = {Path("/"), Path("/bin"), Path("/sbin"), Path("/usr"), Path("/etc"), Path("/System")}
    if resolved in system_forbidden:
        raise PermissionError(f"Access to protected system directory '{resolved}' is forbidden.")
    return resolved


@registry.register("filesystem.mkdir", description="Create a new directory at the specified path.")
async def tool_mkdir(path: str, exist_ok: bool = True) -> Dict[str, Any]:
    target = _resolve_safe_path(path)
    target.mkdir(parents=True, exist_ok=exist_ok)
    return {
        "path": str(target),
        "created": True,
        "exists": target.exists(),
    }


@registry.register("filesystem.write_file", description="Write content to a file at the specified path.")
async def tool_write_file(path: str, content: str) -> Dict[str, Any]:
    target = _resolve_safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "path": str(target),
        "bytes_written": len(content.encode("utf-8")),
    }


@registry.register("filesystem.read_file", description="Read text content from a file.")
async def tool_read_file(path: str, max_chars: int = 10000) -> Dict[str, Any]:
    target = _resolve_safe_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    content = target.read_text(encoding="utf-8")
    truncated = len(content) > max_chars
    return {
        "path": str(target),
        "content": content[:max_chars],
        "truncated": truncated,
        "total_length": len(content),
    }


@registry.register("filesystem.list_dir", description="List files and directories in a given folder.")
async def tool_list_dir(path: str) -> Dict[str, Any]:
    target = _resolve_safe_path(path)
    if not target.is_dir():
        raise NotADirectoryError(f"Directory not found: {target}")
    entries: List[Dict[str, Any]] = []
    for item in target.iterdir():
        entries.append({
            "name": item.name,
            "is_dir": item.is_dir(),
            "size": item.stat().st_size if item.is_file() else 0,
        })
    return {
        "path": str(target),
        "entries": entries,
        "count": len(entries),
    }


@registry.register(
    "filesystem.delete_file",
    description="Delete a file from the filesystem. Requires voice confirmation.",
    requires_voice_confirmation=True,
)
async def tool_delete_file(path: str) -> Dict[str, Any]:
    target = _resolve_safe_path(path)
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")
    if target.is_file():
        target.unlink()
    elif target.is_dir():
        target.rmdir()
    return {
        "path": str(target),
        "deleted": True,
    }
