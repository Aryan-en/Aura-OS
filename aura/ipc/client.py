"""
AURA OS — Asynchronous Unix Domain Socket (UDS) Client
Allows CLI utilities and external agents to communicate directly with aurad.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional

from aura.core.logger import logger
from aura.ipc.protocol import IPCRequest, IPCResponse


class AuraIPCClient:
    """Client for communicating with aurad over Unix Domain Socket."""

    def __init__(self, socket_path: Path, timeout: float = 5.0) -> None:
        self.socket_path = socket_path.resolve()
        self.timeout = timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        """Establish connection to the daemon socket."""
        if not self.socket_path.exists():
            raise FileNotFoundError(
                f"AURA daemon socket does not exist at '{self.socket_path}'. "
                "Is aurad running?"
            )
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, ConnectionRefusedError) as e:
            raise ConnectionError(
                f"Could not connect to AURA daemon socket at '{self.socket_path}': {e}"
            )

    async def call(
        self, method: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> IPCResponse:
        """Send an RPC request and await the structured response."""
        if not self._writer or not self._reader:
            await self.connect()
            assert self._writer is not None and self._reader is not None

        effective_timeout = timeout or self.timeout
        request = IPCRequest(method=method, params=params or {})
        self._writer.write(request.to_bytes())
        await self._writer.drain()

        try:
            line = await asyncio.wait_for(
                self._reader.readline(), timeout=effective_timeout
            )
            if not line:
                raise ConnectionResetError("Server closed connection unexpectedly")

            return IPCResponse.model_validate_json(line.decode("utf-8").strip())
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"IPC call '{method}' timed out after {effective_timeout}s"
            )

    async def ping(self) -> float:
        """
        Send ping to daemon and measure round-trip latency in milliseconds.
        """
        start = time.perf_counter()
        response = await self.call("core.ping")
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if not response.success:
            raise RuntimeError(f"Ping failed: {response.error}")
        return elapsed_ms

    async def close(self) -> None:
        """Close connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    async def __aenter__(self) -> AuraIPCClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
