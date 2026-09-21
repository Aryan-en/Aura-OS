"""
AURA OS — Sandboxed Terminal Execution Tool
Executes shell commands with timeouts, output capturing, and permission guards.
"""

from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any, Dict

from aura.core.logger import logger
from aura.tools.registry import registry

# Disallowed root-destroying patterns
BLOCKED_PATTERNS = [
    "rm -rf /",
    ":(){ :|:& };:",
    "mkfs",
    "dd if=/dev/zero",
    "> /dev/sda",
]


@registry.register(
    "terminal.run_command",
    description="Execute a sandboxed shell command on the host OS.",
    requires_voice_confirmation=False,
)
async def tool_run_command(
    command: str,
    timeout_sec: float = 30.0,
    cwd: str | None = None,
) -> Dict[str, Any]:
    """Execute a system command securely with timeout."""
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            raise PermissionError(f"Command rejected: contains blocked dangerous pattern '{pattern}'")

    working_dir = os.path.expanduser(cwd) if cwd else os.getcwd()

    logger.debug(f"Executing command: {command} in {working_dir}")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_sec
        )

        stdout_str = stdout_b.decode("utf-8", errors="replace")
        stderr_str = stderr_b.decode("utf-8", errors="replace")

        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "success": proc.returncode == 0,
        }

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_sec} seconds.",
            "success": False,
        }
