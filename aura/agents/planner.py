"""
AURA OS — Agent Goal Planner
Decomposes natural language user goals into structured, executable Task DAGs.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from aura.agents.gemini import GeminiClient
from aura.agents.task import Task, TaskDAG
from aura.core.logger import logger
from aura.tools.registry import registry


class GoalPlanner:
    """Plans execution graphs from natural language goal prompts."""

    @staticmethod
    def plan(goal_prompt: str, gemini_client: Optional[GeminiClient] = None) -> TaskDAG:
        dag = TaskDAG(goal_prompt=goal_prompt)

        # 1. High-Parameter Reasoning via Google Gemini API
        client = gemini_client or GeminiClient()
        if client.is_configured():
            try:
                tools_def = [t.model_dump() for t in registry.get_definitions()]
                ai_tasks = client.plan_goal(goal_prompt, tools_def)
                if ai_tasks and len(ai_tasks) > 0:
                    for t_spec in ai_tasks:
                        task = Task(
                            title=t_spec.get("title", f"Execute {t_spec.get('tool_name')}"),
                            tool_name=t_spec.get("tool_name"),
                            params=t_spec.get("params", {}),
                            dependencies=t_spec.get("dependencies", []),
                        )
                        dag.add_task(task)
                    logger.info(
                        f"Gemini successfully planned {len(dag.tasks)} tasks for goal: '{goal_prompt}'"
                    )
                    return dag
            except Exception as e:
                logger.warning(f"Gemini AI planning failed ({e}), falling back to deterministic rules")

        # 2. Local Deterministic Rule Fallback
        # Pattern 1: Folder creation ("create a folder called X on my Desktop")
        folder_match = re.search(
            r"(?:create|make)(?:\s+a)?\s+(?:folder|directory)(?:\s+called|\s+named)?\s+([a-zA-Z0-9_\-\.\/]+)(?:\s+on|\s+in)?\s*(.*)?",
            goal_prompt,
            re.IGNORECASE,
        )
        if folder_match:
            folder_name = folder_match.group(1).strip()
            loc = folder_match.group(2).strip().lower() if folder_match.group(2) else ""
            if "desktop" in loc:
                target_path = os.path.expanduser(f"~/Desktop/{folder_name}")
            elif "documents" in loc:
                target_path = os.path.expanduser(f"~/Documents/{folder_name}")
            elif "downloads" in loc:
                target_path = os.path.expanduser(f"~/Downloads/{folder_name}")
            else:
                target_path = os.path.expanduser(folder_name)

            task = Task(
                title=f"Create directory {target_path}",
                tool_name="filesystem.mkdir",
                params={"path": target_path},
            )
            dag.add_task(task)
            return dag

        # Pattern 2: Write file ("write file X with content Y")
        write_match = re.search(
            r"(?:write|create)\s+file\s+([^\s]+)\s+(?:with|containing)\s+(?:content\s+)?(.*)",
            goal_prompt,
            re.IGNORECASE,
        )
        if write_match:
            filepath = write_match.group(1).strip()
            content = write_match.group(2).strip()
            task = Task(
                title=f"Write content to {filepath}",
                tool_name="filesystem.write_file",
                params={"path": filepath, "content": content},
            )
            dag.add_task(task)
            return dag

        # Pattern 3: Shell command execution ("run command X" or "execute X")
        cmd_match = re.search(r"(?:run|execute)(?:\s+command)?\s+['\"]?([^'\"]+)['\"]?", goal_prompt, re.IGNORECASE)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            task = Task(
                title=f"Execute shell command '{cmd}'",
                tool_name="terminal.run_command",
                params={"command": cmd},
            )
            dag.add_task(task)
            return dag

        # Default fallback: Echo / Informational Task
        task = Task(
            title=f"Process goal: {goal_prompt}",
            tool_name="terminal.run_command",
            params={"command": f"echo 'AURA goal acknowledged: {goal_prompt}'"},
        )
        dag.add_task(task)
        return dag
