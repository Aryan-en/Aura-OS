"""
Unit tests for AURA OS IPC Socket Server & Client Protocol.
"""

import asyncio
import os
import stat
import tempfile
from pathlib import Path

import pytest
from aura.ipc.client import AuraIPCClient
from aura.ipc.protocol import ErrorCode, IPCRequest
from aura.ipc.server import AsyncUnixSocketServer


def test_socket_creation_and_permissions() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            server = AsyncUnixSocketServer(socket_path=socket_path)

            await server.start()
            assert socket_path.exists(), "Socket file must exist"

            # Verify permissions (0600 on socket file)
            mode = stat.S_IMODE(os.stat(socket_path).st_mode)
            assert mode == 0o600, f"Expected socket mode 0600, got {oct(mode)}"

            await server.stop()
            assert not socket_path.exists(), "Socket file must be unlinked on stop"

    asyncio.run(_run())


def test_ping_pong_roundtrip() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            server = AsyncUnixSocketServer(socket_path=socket_path)
            await server.start()

            async with AuraIPCClient(socket_path=socket_path) as client:
                latency_ms = await client.ping()
                assert latency_ms > 0
                assert latency_ms < 50.0  # UDS latency is sub-millisecond

                # Direct call to verify pong contents
                response = await client.call("core.ping", {"hello": "world"})
                assert response.success is True
                assert response.data["pong"] is True
                assert response.data["echo"] == {"hello": "world"}

            await server.stop()

    asyncio.run(_run())


def test_custom_handler_and_status() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            server = AsyncUnixSocketServer(socket_path=socket_path)

            async def dummy_handler(req: IPCRequest) -> dict:
                return {"result": req.params.get("num", 0) * 2}

            server.register("math.double", dummy_handler)
            await server.start()

            async with AuraIPCClient(socket_path=socket_path) as client:
                resp = await client.call("math.double", {"num": 21})
                assert resp.success is True
                assert resp.data == {"result": 42}

            await server.stop()

    asyncio.run(_run())


def test_unknown_method_error() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            server = AsyncUnixSocketServer(socket_path=socket_path)
            await server.start()

            async with AuraIPCClient(socket_path=socket_path) as client:
                resp = await client.call("nonexistent.method")
                assert resp.success is False
                assert resp.error_code == ErrorCode.METHOD_NOT_FOUND

            await server.stop()

    asyncio.run(_run())


def test_malformed_json_handling() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            server = AsyncUnixSocketServer(socket_path=socket_path)
            await server.start()

            # Open raw socket connection and send garbage
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(b"NOT_A_VALID_JSON_STRING\n")
            await writer.drain()

            raw_resp = await reader.readline()
            writer.close()
            await writer.wait_closed()

            assert b"INVALID_REQUEST" in raw_resp

            # Ensure server is still alive and responds to ping
            async with AuraIPCClient(socket_path=socket_path) as client:
                pong = await client.ping()
                assert pong > 0

            await server.stop()

    asyncio.run(_run())
