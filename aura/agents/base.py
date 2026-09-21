"""
AURA OS — Base Agent Model
Defines agent identity, roles, state machine, and goal lifecycle.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aura.agents.task import TaskDAG


class AgentState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class AgentInfo(BaseModel):
    """Metadata representing an active or idle specialized agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    role: str
    state: AgentState = Field(default=AgentState.IDLE)
    current_task: Optional[str] = None
    started_at: float = Field(default_factory=time.time)
    metrics: Dict[str, Any] = Field(default_factory=dict)
