"""
AURA OS — Agent Execution Loop
Orchestrates task dispatch, tool execution, retries, and memory synchronization.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional
from aura.agents.task import Task, TaskDAG, TaskStatus
from aura.core.logger import logger
from aura.memory.db import MemoryDB
from aura.tools.registry import registry


class ExecutionLoop:
    """Executes a TaskDAG until completion or failure."""

    def __init__(self, memory_db: Optional[MemoryDB] = None) -> None:
        self.memory = memory_db

    async def run_dag(
        self,
        dag: TaskDAG,
        progress_cb: Optional[Callable[[Task], None]] = None,
    ) -> Dict[str, Any]:
        """Execute all tasks in DAG adhering to dependency topology."""
        start_time = time.time()
        logger.info(f"Beginning execution for goal '{dag.goal_prompt}' [{len(dag.tasks)} tasks]")

        if self.memory:
            self.memory.record_goal(dag.goal_id, dag.goal_prompt)
            for t in dag.tasks.values():
                self.memory.record_task(t.id, dag.goal_id, t.title, t.tool_name)

        while not dag.is_finished():
            ready_tasks = dag.get_ready_tasks()
            if not ready_tasks:
                # Deadlock check: tasks remain but none are ready
                logger.error("Dependency deadlock detected in TaskDAG")
                for t in dag.tasks.values():
                    if t.status == TaskStatus.PENDING:
                        t.status = TaskStatus.FAILED
                        t.error = "Unresolved prerequisite dependency deadlock"
                break

            for task in ready_tasks:
                task.status = TaskStatus.RUNNING
                if progress_cb:
                    progress_cb(task)

                if task.tool_name:
                    tool_start = time.perf_counter()
                    res = await registry.execute(task.tool_name, **task.params)
                    duration_ms = (time.perf_counter() - tool_start) * 1000.0

                    if self.memory:
                        self.memory.record_tool_audit(
                            tool_name=task.tool_name,
                            params=task.params,
                            success=res["success"],
                            duration_ms=duration_ms,
                        )

                    if res["success"]:
                        task.status = TaskStatus.COMPLETED
                        task.result = res.get("data")
                    else:
                        task.retry_count += 1
                        if task.retry_count <= task.max_retries:
                            logger.warning(
                                f"Task '{task.title}' failed: {res.get('error')}. Retrying ({task.retry_count}/{task.max_retries})..."
                            )
                            task.status = TaskStatus.PENDING
                        else:
                            task.status = TaskStatus.FAILED
                            task.error = res.get("error")
                else:
                    # No tool, pure informational step
                    task.status = TaskStatus.COMPLETED

                if self.memory:
                    self.memory.update_task(task.id, task.status.value, task.result, task.error)

                if progress_cb:
                    progress_cb(task)

        duration = time.time() - start_time
        success = dag.is_successful()

        if self.memory:
            self.memory.update_goal_status(dag.goal_id, "COMPLETED" if success else "FAILED")

        logger.info(f"Execution finished in {duration:.2f}s (Success: {success})")
        return {
            "goal_id": dag.goal_id,
            "success": success,
            "duration_sec": duration,
            "tasks": {t.id: {"status": t.status.value, "result": t.result, "error": t.error} for t in dag.tasks.values()},
        }
