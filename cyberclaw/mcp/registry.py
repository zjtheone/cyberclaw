"""MCP tool adapter: wraps MCP server tools as cyberclaw Tool instances."""

from typing import Any

from loguru import logger

from cyberclaw.agent.tools.base import Tool
from cyberclaw.mcp.client import MCPClient
from cyberclaw.mcp.config import MCPConfig, MCPServerConfig


class MCPToolAdapter(Tool):
    """
    Adapts an MCP tool to the cyberclaw Tool interface.

    The agent sees it as a regular tool — completely transparent.
    """

    def __init__(self, client: MCPClient, tool_def: dict[str, Any]):
        self._client = client
        self._tool_def = tool_def
        self._name = f"mcp_{client.name}_{tool_def['name']}"
        self._original_name = tool_def["name"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._tool_def.get("description", f"MCP tool: {self._original_name}")

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool_def.get("inputSchema", {"type": "object", "properties": {}})

    async def execute(self, **kwargs: Any) -> str:
        try:
            return await self._client.call_tool(self._original_name, kwargs)
        except Exception as e:
            return f"MCP tool error: {e}"


class MCPManager:
    """
    Manages MCP server connections and tool registration.

    Reads config, starts servers, and registers their tools into the ToolRegistry.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}

    async def start_servers(self, config: MCPConfig) -> list[Tool]:
        """
        Start all configured MCP servers and return their tools as Tool instances.

        Args:
            config: MCP configuration with server definitions.

        Returns:
            List of MCPToolAdapter instances ready for registration.
        """
        tools: list[Tool] = []

        for name, server_config in config.servers.items():
            if not server_config.enabled or not server_config.command:
                continue

            client = MCPClient(
                name=name,
                command=server_config.command,
                args=server_config.args,
                env=server_config.env,
            )

            try:
                await client.start()
                self._clients[name] = client

                for tool_def in client.tools:
                    adapter = MCPToolAdapter(client, tool_def)
                    tools.append(adapter)
                    logger.info(f"MCP tool registered: {adapter.name}")

            except Exception as e:
                logger.error(f"Failed to start MCP server '{name}': {e}")

        return tools

    async def stop_all(self) -> None:
        """Stop all running MCP servers."""
        for name, client in self._clients.items():
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping MCP server '{name}': {e}")
        self._clients.clear()
