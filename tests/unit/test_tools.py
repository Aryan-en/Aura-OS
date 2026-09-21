"""
Unit tests for AURA OS Tools Subsystem.
"""

import asyncio
import tempfile
from pathlib import Path

from aura.tools.registry import registry
import aura.tools.filesystem  # noqa: F401
import aura.tools.terminal    # noqa: F401


def test_tool_registry_discovery() -> None:
    defs = registry.get_definitions()
    names = {d.name for d in defs}
    assert "filesystem.mkdir" in names
    assert "filesystem.write_file" in names
    assert "filesystem.read_file" in names
    assert "filesystem.delete_file" in names
    assert "terminal.run_command" in names

    del_tool = registry.get_definition("filesystem.delete_file")
    assert del_tool is not None
    assert del_tool.requires_voice_confirmation is True


def test_filesystem_mkdir_write_read() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_folder = Path(tmpdir) / "sub" / "folder"
            res = await registry.execute("filesystem.mkdir", path=str(test_folder))
            assert res["success"] is True
            assert test_folder.is_dir()

            # Write file
            file_path = test_folder / "hello.txt"
            res_write = await registry.execute(
                "filesystem.write_file", path=str(file_path), content="Aura OS Operational"
            )
            assert res_write["success"] is True

            # Read file
            res_read = await registry.execute("filesystem.read_file", path=str(file_path))
            assert res_read["success"] is True
            assert res_read["data"]["content"] == "Aura OS Operational"

    asyncio.run(_run())


def test_terminal_run_command() -> None:
    async def _run() -> None:
        res = await registry.execute("terminal.run_command", command="echo 'Hello Aura'")
        assert res["success"] is True
        assert res["data"]["exit_code"] == 0
        assert "Hello Aura" in res["data"]["stdout"]

    asyncio.run(_run())


def test_blocked_dangerous_command() -> None:
    async def _run() -> None:
        res = await registry.execute("terminal.run_command", command="rm -rf /")
        assert res["success"] is False
        assert "blocked dangerous pattern" in res["error"]

    asyncio.run(_run())
