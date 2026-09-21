"""
AURA OS — Asynchronous Unix Domain Socket (UDS) Server
Provides secure local IPC for daemon control, status monitoring, and event streams.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional, Set

from aura.core.logger import logger
from aura.ipc.protocol import ErrorCode, IPCRequest, IPCResponse

HandlerFunc = Callable[[IPCRequest], Coroutine[Any, Any, Any]]


class AsyncUnixSocketServer:
    """
    Secure UDS Server for aurad daemon.
    Enforces 0700 on runtime directory and 0600 on the socket file.
    """

    def __init__(
        self,
        socket_path: Path,
        max_payload_bytes: int = 10 * 1024 * 1024,
        client_timeout: float = 30.0,
    ) -> None:
        self.socket_path = socket_path.resolve()
        self.max_payload_bytes = max_payload_bytes
        self.client_timeout = client_timeout
        self._server: Optional[asyncio.Server] = None
        self._handlers: Dict[str, HandlerFunc] = {}
        self._active_clients: Set[asyncio.StreamWriter] = set()
        self._running = False
        self._stop_event = asyncio.Event()

        # Register default core handlers
        self.register("core.ping", self._handle_ping)

    def register(self, method: str, handler: HandlerFunc) -> None:
        """Register an RPC method handler."""
        self._handlers[method] = handler
        logger.debug(f"Registered IPC method: {method}")

    async def _handle_ping(self, request: IPCRequest) -> Dict[str, Any]:
        """Built-in ping response."""
        return {
            "pong": True,
            "server_time": time.time(),
            "echo": request.params,
        }

    async def start(self) -> None:
        """Initialize and bind the Unix domain socket."""
        # Ensure parent directory exists with owner-only (0700) permissions
        parent_dir = self.socket_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(parent_dir, 0o700)
        except OSError as e:
            logger.warning(f"Could not chmod parent dir {parent_dir}: {e}")

        # Unlink stale socket if it exists
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
                logger.info(f"Unlinked stale socket at {self.socket_path}")
            except OSError as e:
                logger.error(f"Failed to remove stale socket {self.socket_path}: {e}")
                raise

        # Start asynchronous server
        self._server = await asyncio.start_unix_server(
            client_connected_cb=self._handle_client,
            path=str(self.socket_path),
        )

        # Enforce owner-only (0600) permissions on the socket file
        try:
            os.chmod(self.socket_path, 0o600)
        except OSError as e:
            logger.warning(f"Could not chmod socket {self.socket_path}: {e}")

        self._running = True
        logger.info(f"AURA IPC Server listening on UDS: {self.socket_path} (mode: 0600)")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Manage an individual client connection loop."""
        self._active_clients.add(writer)
        try:
            while self._running:
                try:
                    # Read line with timeout
                    line = await asyncio.wait_for(
                        reader.readline(), timeout=self.client_timeout
                    )
                except asyncio.TimeoutError:
                    logger.debug("Client connection timed out idle")
                    break

                if not line:
                    # Client disconnected EOF
                    break

                if len(line) > self.max_payload_bytes:
                    response = IPCResponse.fail(
                        request_id="unknown",
                        error="Payload exceeds max size limit",
                        code=ErrorCode.PAYLOAD_TOO_LARGE,
                    )
                    writer.write(response.to_bytes())
                    await writer.drain()
                    break

                # Parse JSON request
                try:
                    raw_str = line.decode("utf-8").strip()
                    if not raw_str:
                        continue
                    request = IPCRequest.model_validate_json(raw_str)
                except Exception as ex:
                    logger.warning(f"Malformed IPC request received: {ex}")
                    response = IPCResponse.fail(
                        request_id="unknown",
                        error=f"Malformed JSON request: {str(ex)}",
                        code=ErrorCode.INVALID_REQUEST,
                    )
                    writer.write(response.to_bytes())
                    await writer.drain()
                    continue

                # Route to registered handler
                handler = self._handlers.get(request.method)
                if not handler:
                    response = IPCResponse.fail(
                        request_id=request.id,
                        error=f"Method '{request.method}' not registered",
                        code=ErrorCode.METHOD_NOT_FOUND,
                    )
                else:
                    try:
                        result = await handler(request)
                        response = IPCResponse.ok(request_id=request.id, data=result)
                    except Exception as err:
                        logger.exception(f"Error handling method {request.method}: {err}")
                        response = IPCResponse.fail(
                            request_id=request.id,
                            error=str(err),
                            code=ErrorCode.INTERNAL_ERROR,
                        )

                writer.write(response.to_bytes())
                await writer.drain()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Unexpected error in client session: {e}")
        finally:
            self._active_clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def broadcast_event(self, event_bytes: bytes) -> None:
        """Broadcast an event frame to all connected clients."""
        for client in list(self._active_clients):
            try:
                client.write(event_bytes)
                await client.drain()
            except Exception:
                self._active_clients.discard(client)

    async def stop(self) -> None:
        """Gracefully stop server and cleanup socket file."""
        self._running = False
        self._stop_event.set()

        # Close all active client connections
        for client in list(self._active_clients):
            try:
                client.close()
            except Exception:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Clean up socket file from filesystem
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
                logger.info(f"Cleaned up socket file {self.socket_path}")
            except OSError as e:
                logger.error(f"Could not remove socket file on shutdown: {e}")

        logger.info("AURA IPC Server stopped")
