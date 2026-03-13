"""MCP client: connects to MCP servers via stdio transport."""

import asyncio
import json
from typing import Any

from loguru import logger


class MCPClient:
    """
    Client for communicating with MCP servers via stdio (JSON-RPC).

    Launches the server process, sends initialize, and provides
    methods to list and call tools.
    """

    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._initialized = False
        self._tools: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start the MCP server process and initialize."""
        import os
        env = {**os.environ, **self.env}

        self._process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        logger.info(f"MCP server '{self.name}' started (pid={self._process.pid})")

        # Initialize
        result = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cyberclaw", "version": "1.0.0"},
        })

        if result:
            self._initialized = True
            # Send initialized notification
            await self._notify("notifications/initialized", {})
            # List tools
            tools_result = await self._request("tools/list", {})
            if tools_result and "tools" in tools_result:
                self._tools = tools_result["tools"]
                logger.info(f"MCP '{self.name}': {len(self._tools)} tools available")

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            logger.info(f"MCP server '{self.name}' stopped")

    @property
    def tools(self) -> list[dict[str, Any]]:
        """Get the list of tools provided by this server."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server."""
        result = await self._request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        if not result:
            return "Error: no response from MCP server"

        # Extract text content from result
        content = result.get("content", [])
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts) if parts else json.dumps(result)

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None

        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        data = json.dumps(msg) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

        # Read response line
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            if not line:
                return None
            response = json.loads(line.decode())
            if "error" in response:
                logger.error(f"MCP '{self.name}' error: {response['error']}")
                return None
            return response.get("result")
        except asyncio.TimeoutError:
            logger.error(f"MCP '{self.name}' request timeout: {method}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"MCP '{self.name}' invalid JSON: {e}")
            return None

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        data = json.dumps(msg) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()
