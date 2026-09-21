"""
AURA OS — Tool & Capability Registry
Provides dynamic registration, input validation, and execution guards for OS tools.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

from aura.core.logger import logger


class ToolDefinition(BaseModel):
    """Metadata describing an executable tool primitive."""
    name: str = Field(..., description="Unique tool identifier (e.g. 'filesystem.mkdir')")
    description: str = Field(..., description="Semantic purpose of the tool")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema of parameters")
    requires_voice_confirmation: bool = Field(default=False, description="Whether tool requires physical/voice approval")


class ToolRegistry:
    """Registry managing available system tools and their execution."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._definitions: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        requires_voice_confirmation: bool = False,
    ) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
        """Decorator to register an async tool handler."""
        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
            sig = inspect.signature(func)
            params: Dict[str, Any] = {
                k: str(v.annotation if v.annotation != inspect.Parameter.empty else "Any")
                for k, v in sig.parameters.items()
            }
            self._tools[name] = func
            self._definitions[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=params,
                requires_voice_confirmation=requires_voice_confirmation,
            )
            logger.debug(f"Registered tool: {name} (voice confirmation: {requires_voice_confirmation})")
            return func
        return decorator

    def get_definitions(self) -> List[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._definitions.values())

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get definition for a specific tool."""
        return self._definitions.get(name)

    async def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a tool with parameter passing and error boundary."""
        if name not in self._tools:
            return {
                "success": False,
                "error": f"Tool '{name}' is not registered in AURA tool registry.",
            }

        func = self._tools[name]
        try:
            result = await func(**kwargs)
            return {
                "success": True,
                "data": result,
            }
        except Exception as e:
            logger.exception(f"Error executing tool '{name}': {e}")
            return {
                "success": False,
                "error": str(e),
            }


# Global tool registry instance
registry = ToolRegistry()
