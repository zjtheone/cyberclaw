"""Spawn tool for creating background subagents with A2A policy enforcement."""

from typing import TYPE_CHECKING, Any

from cyberclaw.agent.tools.base import Tool
from cyberclaw.session.keys import SessionKey, extract_agent_id

if TYPE_CHECKING:
    from cyberclaw.agent.subagent import SubagentManager
    from cyberclaw.config.loader import Config
    from cyberclaw.agent.policy_engine import AgentToAgentPolicyEngine


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution.

    Supports:
    - Same-agent subagent spawning
    - Cross-agent spawning (with policy enforcement)
    - Nested subagent spawning (with depth limits)
    """

    def __init__(
        self,
        manager: "SubagentManager",
        config: "Config | None" = None,
        policy_engine: "AgentToAgentPolicyEngine | None" = None,
    ):
        self._manager = manager
        self._config = config
        self._policy_engine = policy_engine
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._agent_id = "default"
        self._spawn_depth = 0

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        agent_id: str | None = None,
        spawn_depth: int = 0,
    ) -> None:
        """Set the origin context for subagent announcements.

        Args:
            channel: Origin channel
            chat_id: Origin chat ID
            session_key: Origin session key
            agent_id: Origin agent ID
            spawn_depth: Current spawn depth
        """
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"
        self._agent_id = agent_id or "default"
        self._spawn_depth = spawn_depth

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done.\n"
            "\nParameters:\n"
            "- task: The task for the subagent to complete (required)\n"
            "- label: Optional short label for the task (for display)\n"
            "- agent_id: Optional target agent ID (default: same as current agent)\n"
            "\nNote: Cross-agent spawning requires tools.agent_to_agent.enabled=true"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete (required for single spawn)",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Optional target agent ID (default: same as current agent)",
                },
                # Batch spawn parameters
                "batch": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "Task description"},
                            "label": {"type": "string", "description": "Optional label"},
                        },
                        "required": ["task"],
                    },
                    "description": "Batch spawn: array of tasks to spawn in parallel",
                },
                "wait": {
                    "type": "boolean",
                    "default": False,
                    "description": "Wait for batch results (only for batch mode)",
                },
                "timeout": {
                    "type": "integer",
                    "default": 300,
                    "description": "Timeout in seconds for batch wait (only for batch mode)",
                },
            },
            "required": [],  # Either 'task' or 'batch' is required
        }

    async def execute(
        self,
        task: str | None = None,
        label: str | None = None,
        agent_id: str | None = None,
        batch: list[dict] | None = None,
        wait: bool = False,
        timeout: int = 300,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task.

        Args:
            task: Task description (for single spawn)
            label: Optional label (for single spawn)
            agent_id: Optional target agent ID
            batch: Batch spawn - list of {task, label} dicts
            wait: Wait for batch results (only for batch mode)
            timeout: Timeout in seconds for batch wait
            **kwargs: Additional arguments

        Returns:
            Result message (success or error)
        """
        # Batch mode
        if batch:
            return await self._execute_batch(batch, wait, timeout)

        # Single spawn mode
        if not task:
            return "Error: Either 'task' or 'batch' parameter is required"

        return await self._spawn_single(task, label, agent_id)

    async def _spawn_single(
        self,
        task: str,
        label: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        """Spawn a single subagent."""
        target_agent_id = agent_id or self._agent_id

        # Check A2A policy
        policy_result = self._check_spawn_policy(target_agent_id)
        if policy_result.is_denied:
            return f"Error: {policy_result.message}"

        # Get spawn depth limit
        max_depth = self._get_max_spawn_depth()

        try:
            # Spawn the subagent
            result = await self._manager.spawn(
                task=task,
                label=label,
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                session_key=self._session_key,
                target_agent_id=target_agent_id,
                parent_depth=self._spawn_depth,
                max_depth=max_depth,
            )
            return result
        except Exception as e:
            return f"Error spawning subagent: {str(e)}"

    async def _execute_batch(
        self,
        batch: list[dict],
        wait: bool = False,
        timeout: int = 300,
    ) -> str:
        """Execute batch spawn.

        Args:
            batch: List of {task, label} dicts
            wait: Wait for all results
            timeout: Timeout for wait

        Returns:
            Formatted results
        """
        if not batch:
            return "Error: Batch cannot be empty"

        import asyncio

        # Spawn all tasks
        tasks = []
        for item in batch:
            task_desc = item.get("task", "")
            label = item.get("label")

            if not task_desc:
                continue

            # Create coroutine for each spawn
            coro = self._spawn_single(task_desc, label)
            tasks.append(coro)

        if not tasks:
            return "Error: No valid tasks in batch"

        # Execute all spawns in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            return f"Error in batch spawn: {str(e)}"

        if not wait:
            # Return immediately with task IDs
            return f"Spawned {len(results)} subagents. Use wait_for_children to collect results."

        # Format results
        output_lines = [f"Batch spawn completed ({len(results)} tasks):\n"]
        for i, (item, result) in enumerate(zip(batch, results), 1):
            label = item.get("label", f"Task {i}")
            if isinstance(result, Exception):
                output_lines.append(f"  {label}: FAILED - {str(result)}")
            else:
                # Result is already a string from _spawn_single
                result_str = str(result)
                output_lines.append(f"  {label}: {result_str[:200]}..." if len(result_str) > 200 else f"  {label}: {result_str}")

        return "\n".join(output_lines)

    def _check_spawn_policy(self, target_agent_id: str) -> "PolicyDecision":
        """Check if spawning is allowed by policy.

        Args:
            target_agent_id: Target agent ID

        Returns:
            PolicyDecision
        """
        # If no policy engine, allow all (backward compatibility)
        if not self._policy_engine:
            from cyberclaw.agent.policy_engine import PolicyDecision, PolicyCheckResult

            return PolicyDecision(
                result=PolicyCheckResult.ALLOWED,
                message="No policy engine configured, allowing spawn",
            )

        # Check policy
        return self._policy_engine.check_spawn_allowed(
            requester_agent_id=self._agent_id,
            target_agent_id=target_agent_id,
            current_depth=self._spawn_depth,
        )

    def _get_max_spawn_depth(self) -> int:
        """Get the maximum spawn depth from configuration.

        Returns:
            Maximum spawn depth
        """
        if self._config:
            try:
                agent_config = self._config.agents.get_agent(self._agent_id)
                return agent_config.subagents.max_spawn_depth
            except Exception:
                pass

        # Default: no nesting
        return 1
