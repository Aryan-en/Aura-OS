"""
Unit tests for AURA OS Agent Runtime & Multi-Agent Manager.
"""

import asyncio
import tempfile
from pathlib import Path

from aura.agents.manager import AgentManager
from aura.agents.planner import GoalPlanner
from aura.agents.task import Task, TaskDAG, TaskStatus
from aura.memory.db import MemoryDB


def test_planner_folder_creation() -> None:
    dag = GoalPlanner.plan("create a folder called TestDirectory on my Desktop")
    assert len(dag.tasks) == 1
    task = list(dag.tasks.values())[0]
    assert task.tool_name == "filesystem.mkdir"
    assert "TestDirectory" in task.params["path"]


def test_planner_command_execution() -> None:
    dag = GoalPlanner.plan("run command 'echo 123'")
    assert len(dag.tasks) == 1
    task = list(dag.tasks.values())[0]
    assert task.tool_name == "terminal.run_command"
    assert task.params["command"] == "echo 123"


def test_agent_manager_execution() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            mem = MemoryDB(db_path)
            manager = AgentManager(memory_db=mem)

            statuses = manager.get_agent_statuses()
            assert len(statuses) == 4
            names = {a["name"] for a in statuses}
            assert "Code Agent" in names
            assert "File Agent" in names

            # Execute a folder creation goal
            test_target = Path(tmpdir) / "AuraProject"
            res = await manager.execute_goal(f"create a folder called {test_target}")
            assert res["success"] is True
            assert test_target.is_dir()

            # Verify memory logged tasks
            tasks = mem.get_goal_tasks(res["goal_id"])
            assert len(tasks) == 1
            assert tasks[0]["status"] == "COMPLETED"

    asyncio.run(_run())
