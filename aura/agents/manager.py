"""
AURA OS — Multi-Agent Manager
Supervises specialized domain agents, orchestrates goal lifecycles, and maintains system state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from aura.agents.base import AgentInfo, AgentState
from aura.agents.loop import ExecutionLoop
from aura.agents.planner import GoalPlanner
from aura.core.logger import logger
from aura.memory.db import MemoryDB


class AgentManager:
    """Central supervisor for all active and specialized OS agents."""

    def __init__(self, memory_db: Optional[MemoryDB] = None) -> None:
        self.memory = memory_db
        self.loop = ExecutionLoop(memory_db=memory_db)
        self.agents: Dict[str, AgentInfo] = {
            "code": AgentInfo(name="Code Agent", role="Code synthesis, test execution, debugging"),
            "research": AgentInfo(name="Research Agent", role="Knowledge extraction, documentation, search"),
            "file": AgentInfo(name="File Agent", role="Filesystem organization, cleanup, metadata indexing"),
            "system": AgentInfo(name="System Agent", role="Health telemetry, resource monitoring, security"),
        }

    def get_agent_statuses(self) -> List[Dict[str, Any]]:
        """Return status and activity of all specialized agents."""
        return [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "state": a.state.value,
                "current_task": a.current_task,
                "started_at": a.started_at,
            }
            for a in self.agents.values()
        ]

    async def execute_goal(self, goal_prompt: str) -> Dict[str, Any]:
        """Plan and execute a user goal end-to-end."""
        # Determine responsible agent
        prompt_lower = goal_prompt.lower()
        if any(w in prompt_lower for w in ("code", "test", "python", "script", "debug")):
            active_agent = self.agents["code"]
        elif any(w in prompt_lower for w in ("file", "folder", "directory", "mkdir", "delete", "organize")):
            active_agent = self.agents["file"]
        elif any(w in prompt_lower for w in ("research", "explain", "paper", "search", "docs")):
            active_agent = self.agents["research"]
        else:
            active_agent = self.agents["system"]

        active_agent.state = AgentState.PLANNING
        active_agent.current_task = goal_prompt

        dag = GoalPlanner.plan(goal_prompt)

        active_agent.state = AgentState.EXECUTING
        result = await self.loop.run_dag(dag)

        active_agent.state = AgentState.DONE if result["success"] else AgentState.FAILED
        active_agent.current_task = None
        return result
