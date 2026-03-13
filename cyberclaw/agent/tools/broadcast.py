"""Broadcast tool for sending messages to a team of agents.

This tool allows orchestrating parallel or sequential execution across a team.
"""

from typing import Any, TYPE_CHECKING

from cyberclaw.agent.tools.base import Tool

if TYPE_CHECKING:
    from cyberclaw.agent.subagent import SubagentManager
    from cyberclaw.config.schema import AgentsConfig, TeamConfig


class BroadcastTool(Tool):
    """将消息广播到 team 中的所有 agent。

    支持两种策略：
    - parallel: 并行执行所有 agent（默认）
    - sequential: 顺序执行每个 agent
    """

    def __init__(
        self,
        manager: "SubagentManager",
        agents_config: "AgentsConfig | None" = None,
    ):
        self._manager = manager
        self._agents_config = agents_config
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._agent_id = "default"

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        """Set the origin context for broadcast."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"
        self._agent_id = agent_id or "default"

    @property
    def name(self) -> str:
        return "broadcast"

    @property
    def description(self) -> str:
        return (
            "Broadcast a message to a team of agents and collect results. "
            "Use this to get multiple perspectives on a topic or distribute work across specialists.\n"
            "\nParameters:\n"
            "- team: Team name (must be configured in agents.teams)\n"
            "- message: Message to broadcast to all team members\n"
            "- strategy: Execution strategy - 'parallel' (default) or 'sequential'\n"
            "- timeout: Timeout in seconds for each agent (default: 300)\n"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team name to broadcast to",
                },
                "message": {
                    "type": "string",
                    "description": "Message to broadcast to all team members",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["parallel", "sequential"],
                    "default": "parallel",
                    "description": "Execution strategy",
                },
                "timeout": {
                    "type": "integer",
                    "default": 300,
                    "description": "Timeout in seconds for each agent",
                },
            },
            "required": ["team", "message"],
        }

    async def execute(
        self,
        team: str,
        message: str,
        strategy: str = "parallel",
        timeout: int = 300,
        **kwargs: Any,
    ) -> str:
        """Execute broadcast to team.

        Args:
            team: Team name
            message: Message to broadcast
            strategy: 'parallel' or 'sequential'
            timeout: Timeout per agent

        Returns:
            Aggregated results from all team members
        """
        if not self._agents_config:
            return "Error: Broadcast tool requires agents_config to be set"

        # Find team configuration
        team_config = self._agents_config.get_team(team)
        if not team_config:
            available_teams = [t.name for t in self._agents_config.teams]
            return (
                f"Error: Team '{team}' not found. "
                f"Available teams: {', '.join(available_teams) if available_teams else 'none'}"
            )

        if not team_config.members:
            return f"Error: Team '{team}' has no members"

        import asyncio

        if strategy == "sequential":
            # Sequential execution
            results = []
            for member_id in team_config.members:
                try:
                    result = await self._spawn_single(member_id, message, timeout)
                    results.append((member_id, result, None))
                except Exception as e:
                    results.append((member_id, None, str(e)))
        else:
            # Parallel execution (default)
            tasks = [
                self._spawn_single(member_id, message, timeout) for member_id in team_config.members
            ]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for member_id, result in zip(team_config.members, task_results):
                if isinstance(result, Exception):
                    results.append((member_id, None, str(result)))
                else:
                    results.append((member_id, result, None))

        # Format aggregated results
        return self._format_results(team, team_config, results, strategy)

    async def _spawn_single(
        self,
        agent_id: str,
        message: str,
        timeout: int,
    ) -> str:
        """Send task to a single agent and wait for result.

        Prefers A2A router (real-time response) over SubagentManager.spawn()
        (fire-and-forget).
        """
        # Try A2A router first — returns actual execution result
        a2a_router = getattr(self._manager, '_a2a_router', None)
        if not a2a_router:
            # Check if agent_loop has a2a_router
            agent_loop = getattr(self, '_agent_loop', None)
            if agent_loop:
                a2a_router = getattr(agent_loop, 'a2a_router', None)

        if a2a_router and a2a_router.get_mailbox(agent_id):
            import asyncio
            try:
                resp = await a2a_router.send_request(
                    from_agent=self._agent_id,
                    to_agent=agent_id,
                    content=message,
                    timeout=timeout,
                )
                return resp.content
            except asyncio.TimeoutError:
                return f"Timeout after {timeout}s"
            except Exception as e:
                return f"A2A error: {e}"

        # Fallback to spawn (fire-and-forget)
        result = await self._manager.spawn(
            task=message,
            label=f"broadcast:{agent_id}",
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
            target_agent_id=agent_id,
            parent_depth=0,
            max_depth=2,
        )
        return result

    def _format_results(
        self,
        team: str,
        team_config: "TeamConfig",
        results: list[tuple[str, str | None, str | None]],
        strategy: str,
    ) -> str:
        """Format broadcast results."""
        lines = [
            f"**Broadcast to team '{team}' completed ({strategy} strategy)**",
            "",
            f"Team members: {', '.join(team_config.members)}",
            "",
            "Results:",
            "",
        ]

        success_count = 0
        fail_count = 0

        for member_id, result, error in results:
            if error:
                fail_count += 1
                lines.append(f"❌ **{member_id}**: FAILED - {error}")
            else:
                success_count += 1
                preview = result[:150] + "..." if len(result) > 150 else result
                lines.append(f"✅ **{member_id}**: {preview}")

            lines.append("")

        # Summary
        lines.append("---")
        lines.append(
            f"Summary: {success_count} succeeded, {fail_count} failed out of {len(results)} agents"
        )

        if team_config.leader and success_count > 0:
            lines.append(f"Team leader: {team_config.leader}")

        return "\n".join(lines)
