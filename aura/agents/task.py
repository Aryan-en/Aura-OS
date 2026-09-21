"""
AURA OS — Task & Dependency DAG Primitives
Models individual atomic task steps, dependencies, retries, and execution states.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(BaseModel):
    """An atomic unit of work within an agent plan."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = Field(..., description="Human-readable description of the step")
    tool_name: Optional[str] = Field(default=None, description="Tool to invoke")
    params: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list, description="IDs of tasks that must finish first")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def is_ready(self, completed_task_ids: set[str]) -> bool:
        """Check if all prerequisite tasks have completed successfully."""
        return self.status == TaskStatus.PENDING and all(
            dep in completed_task_ids for dep in self.dependencies
        )


class TaskDAG(BaseModel):
    """Directed Acyclic Graph of tasks representing a goal breakdown."""
    goal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_prompt: str
    tasks: Dict[str, Task] = Field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_ready_tasks(self) -> List[Task]:
        """Return tasks ready for immediate concurrent or sequential execution."""
        completed = {t.id for t in self.tasks.values() if t.status == TaskStatus.COMPLETED}
        return [t for t in self.tasks.values() if t.is_ready(completed)]

    def is_finished(self) -> bool:
        """Check if all tasks have reached a terminal state."""
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for t in self.tasks.values()
        )

    def is_successful(self) -> bool:
        """Check if all tasks completed without failures."""
        return bool(self.tasks) and all(t.status == TaskStatus.COMPLETED for t in self.tasks.values())
