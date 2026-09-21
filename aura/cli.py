"""
AURA OS — Developer Command Line Utility (aura-cli)
Allows interactive query and control of aurad daemon, agents, tools, and voice subsystems.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from aura.core.config import get_default_socket_path
from aura.ipc.client import AuraIPCClient


async def cmd_ping(socket_path: Path) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path) as client:
            latency_ms = await client.ping()
            print(f"✓ aurad is active [ping latency: {latency_ms:.2f}ms]")
            return 0
    except Exception as e:
        print(f"✗ Failed to ping aurad: {e}", file=sys.stderr)
        return 1


async def cmd_status(socket_path: Path) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path) as client:
            response = await client.call("core.status")
            if response.success:
                print(json.dumps(response.data, indent=2))
                return 0
            else:
                print(f"✗ Error querying status: {response.error}", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"✗ Could not connect to aurad: {e}", file=sys.stderr)
        return 1


async def cmd_goal(socket_path: Path, prompt: str) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path, timeout=60.0) as client:
            print(f"⚡ Submitting goal to AURA agents: \"{prompt}\"...")
            response = await client.call("agent.submit_goal", {"goal": prompt})
            if response.success:
                print("✓ Goal completed successfully!")
                print(json.dumps(response.data, indent=2))
                return 0
            else:
                print(f"✗ Goal failed: {response.error}", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"✗ Error submitting goal: {e}", file=sys.stderr)
        return 1


async def cmd_agents(socket_path: Path) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path) as client:
            response = await client.call("agent.list")
            if response.success:
                print(json.dumps(response.data, indent=2))
                return 0
            else:
                print(f"✗ Error: {response.error}", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"✗ Could not connect to aurad: {e}", file=sys.stderr)
        return 1


async def cmd_tools(socket_path: Path) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path) as client:
            response = await client.call("tools.list")
            if response.success:
                print(json.dumps(response.data, indent=2))
                return 0
            else:
                print(f"✗ Error: {response.error}", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"✗ Could not connect to aurad: {e}", file=sys.stderr)
        return 1


async def cmd_stop(socket_path: Path) -> int:
    try:
        async with AuraIPCClient(socket_path=socket_path) as client:
            response = await client.call("core.stop")
            if response.success:
                print("✓ aurad shutdown initiated successfully")
                return 0
            else:
                print(f"✗ Error requesting stop: {response.error}", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"✗ Could not connect to aurad: {e}", file=sys.stderr)
        return 1


def main(args: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="aura-cli",
        description="AURA OS Developer Command Line Utility",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        default=get_default_socket_path(),
        help="Path to aurad Unix Domain Socket",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ping", help="Ping the running aurad daemon")
    subparsers.add_parser("status", help="Get operational status and telemetry")
    subparsers.add_parser("agents", help="List active specialized agents")
    subparsers.add_parser("tools", help="List registered system capabilities")

    goal_parser = subparsers.add_parser("goal", help="Submit a goal to AURA agents")
    goal_parser.add_argument("prompt", type=str, help="Natural language goal prompt")

    subparsers.add_parser("stop", help="Request graceful daemon shutdown")

    parsed = parser.parse_args(args)

    if parsed.command == "ping":
        ret = asyncio.run(cmd_ping(parsed.socket))
    elif parsed.command == "status":
        ret = asyncio.run(cmd_status(parsed.socket))
    elif parsed.command == "agents":
        ret = asyncio.run(cmd_agents(parsed.socket))
    elif parsed.command == "tools":
        ret = asyncio.run(cmd_tools(parsed.socket))
    elif parsed.command == "goal":
        ret = asyncio.run(cmd_goal(parsed.socket, parsed.prompt))
    elif parsed.command == "stop":
        ret = asyncio.run(cmd_stop(parsed.socket))
    else:
        ret = 1

    sys.exit(ret)


if __name__ == "__main__":
    main()
