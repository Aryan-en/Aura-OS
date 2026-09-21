"""
AURA OS — Core Runtime Daemon (aurad)
Primary userspace daemon managing all subsystems: Agents, Voice, Vision, Memory, Context, and IPC.
"""

from __future__ import annotations

import asyncio
import os
import platform
import signal
import time
from typing import Any, Dict, Optional

from aura import __version__
from aura.agents.manager import AgentManager
from aura.context.manager import ContextEngine
from aura.core.config import AuraConfig
from aura.core.logger import logger, setup_logger
from aura.ipc.protocol import IPCRequest
from aura.ipc.server import AsyncUnixSocketServer
from aura.memory.db import MemoryDB
from aura.tools.registry import registry
from aura.vision.fusion import MultimodalFusionEngine
from aura.vision.gestures import GestureClassifier
from aura.vision.landmarks import HandLandmarks
from aura.vision.raycaster import SpatialRaycaster
from aura.voice.service import VoiceService


class AuraDaemon:
    """The central AURA OS userspace daemon engine."""

    def __init__(self, config: Optional[AuraConfig] = None) -> None:
        self.config = config or AuraConfig.load()
        self.start_time = time.time()
        self._shutdown_event = asyncio.Event()

        # Initialize Subsystems
        self.memory = MemoryDB(db_path=self.config.agent.sqlite_db_path)
        self.agents = AgentManager(memory_db=self.memory)
        self.voice = VoiceService(agent_manager=self.agents)
        self.context = ContextEngine()
        self.raycaster = SpatialRaycaster()
        self.classifier = GestureClassifier()
        self.fusion = MultimodalFusionEngine()

        # Initialize IPC Server
        self.ipc_server = AsyncUnixSocketServer(
            socket_path=self.config.socket.socket_path,
            max_payload_bytes=self.config.socket.max_payload_bytes,
            client_timeout=self.config.socket.client_timeout_sec,
        )

        self._register_rpc_methods()

    def _register_rpc_methods(self) -> None:
        """Register all RPC endpoints exposed across subsystems."""
        # Core & Status
        self.ipc_server.register("core.status", self._handle_status)
        self.ipc_server.register("core.stop", self._handle_stop)

        # Agent Runtime
        self.ipc_server.register("agent.submit_goal", self._handle_submit_goal)
        self.ipc_server.register("agent.list", self._handle_list_agents)

        # Tools
        self.ipc_server.register("tools.list", self._handle_list_tools)
        self.ipc_server.register("tools.execute", self._handle_execute_tool)

        # Context
        self.ipc_server.register("context.get", self._handle_get_context)

        # Vision & Spatial Gestures
        self.ipc_server.register("vision.process_landmarks", self._handle_process_landmarks)

        # Voice
        self.ipc_server.register("voice.pause", self._handle_voice_pause)

    async def _handle_status(self, request: IPCRequest) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self.start_time, 2)
        return {
            "daemon": "aurad",
            "version": __version__,
            "status": "active (running)",
            "uptime_seconds": uptime_sec,
            "pid": os.getpid(),
            "platform": platform.platform(),
            "environment": self.config.environment,
            "subsystems": {
                "ipc": "online",
                "agents": "online",
                "tools": f"online ({len(registry.get_definitions())} tools)",
                "memory": "online (sqlite)",
                "voice": f"online ({self.voice.state.value})",
                "vision": "online (21-point tracking)",
                "context": "online",
            },
            "active_agents": self.agents.get_agent_statuses(),
        }

    async def _handle_stop(self, request: IPCRequest) -> Dict[str, Any]:
        logger.info("Received stop request via IPC")
        asyncio.create_task(self.request_shutdown(delay=0.2))
        return {"status": "stopping", "message": "AURA daemon is shutting down"}

    async def _handle_submit_goal(self, request: IPCRequest) -> Dict[str, Any]:
        prompt = request.params.get("goal") or request.params.get("prompt")
        if not prompt:
            raise ValueError("Parameter 'goal' or 'prompt' is required.")
        logger.info(f"IPC Goal Received: \"{prompt}\"")
        return await self.agents.execute_goal(prompt)

    async def _handle_list_agents(self, request: IPCRequest) -> Dict[str, Any]:
        return {"agents": self.agents.get_agent_statuses()}

    async def _handle_list_tools(self, request: IPCRequest) -> Dict[str, Any]:
        return {"tools": [t.model_dump() for t in registry.get_definitions()]}

    async def _handle_execute_tool(self, request: IPCRequest) -> Dict[str, Any]:
        tool_name = request.params.get("name")
        args = request.params.get("args", {})
        if not tool_name:
            raise ValueError("Parameter 'name' is required.")
        return await registry.execute(tool_name, **args)

    async def _handle_get_context(self, request: IPCRequest) -> Dict[str, Any]:
        return self.context.get_snapshot()

    async def _handle_process_landmarks(self, request: IPCRequest) -> Dict[str, Any]:
        points_data = request.params.get("points")
        if not points_data or len(points_data) != 21:
            raise ValueError("Must provide 21 3D points.")
        landmarks = HandLandmarks(points=points_data)
        gesture = self.classifier.classify(landmarks)
        target = self.raycaster.project(landmarks)

        self.fusion.record_target(target)
        self.fusion.record_gesture(gesture)

        if gesture.gesture.name == "OPEN_PALM":
            self.voice.emergency_pause()

        return {
            "gesture": gesture.gesture.value,
            "confidence": gesture.confidence,
            "screen_target": target.model_dump(),
        }

    async def _handle_voice_pause(self, request: IPCRequest) -> Dict[str, Any]:
        self.voice.emergency_pause()
        return {"status": "paused", "message": "Voice audio and speech halted."}

    async def request_shutdown(self, delay: float = 0.0) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        self._shutdown_event.set()

    def _setup_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._signal_callback(s))
                )
            except NotImplementedError:
                pass

    async def _signal_callback(self, sig: signal.Signals) -> None:
        logger.warning(f"Received signal {sig.name} ({sig.value}), initiating orderly shutdown...")
        self._shutdown_event.set()

    async def run(self) -> None:
        setup_logger(log_level="INFO", json_output=False)
        logger.info(f"=== Starting AURA OS Unified Runtime (aurad v{__version__}) ===")
        logger.info(f"Process PID: {os.getpid()} on {platform.system()} {platform.machine()}")

        self._setup_signal_handlers()
        await self.ipc_server.start()

        logger.info(f"Loaded {len(registry.get_definitions())} system tools into capability registry")
        logger.info("AURA Subsystems (Agents, Memory, Voice, Vision, Context) fully operational")

        await self._shutdown_event.wait()

        logger.info("Teardown initiated, closing server and subcomponents...")
        await self.ipc_server.stop()
        logger.info("=== AURA OS Daemon cleanly exited ===")


def main() -> None:
    daemon = AuraDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
