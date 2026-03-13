"""Team task tool — entry point for triggering multi-agent team collaboration.

Supports three strategies:
- parallel: All members work concurrently via A2A requests
- sequential: Members work one after another, passing context
- leader_delegate: Leader decomposes and delegates to members
"""

import asyncio
from typing import Any

from loguru import logger

from cyberclaw.agent.tools.base import Tool


class TeamTaskTool(Tool):
    """Tool to trigger agent team collaboration.

    Any agent can use this tool to dispatch a task to a configured team.
    The team's strategy determines how members collaborate.
    """

    def __init__(self, agent_loop):
        self.agent_loop = agent_loop

    @property
    def name(self) -> str:
        return "team_task"

    @property
    def description(self) -> str:
        return (
            "Dispatch a task to an agent team for collaborative execution.\n\n"
            "Teams are pre-configured groups of agents that work together.\n"
            "Strategies: parallel, sequential, leader_delegate.\n\n"
            "Parameters:\n"
            "- team: Team name (as configured)\n"
            "- task: Task description to execute\n"
            "- timeout: Timeout in seconds (default: 300)"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team name",
                },
                "task": {
                    "type": "string",
                    "description": "Task to execute",
                },
                "timeout": {
                    "type": "integer",
                    "default": 300,
                    "description": "Timeout in seconds",
                },
            },
            "required": ["team", "task"],
        }

    async def execute(
        self,
        team: str,
        task: str,
        timeout: int = 300,
        **kwargs: Any,
    ) -> dict:
        """Execute a team task."""
        from cyberclaw.agent.team.manager import TeamManager

        # Validate prerequisites
        if not self.agent_loop.a2a_router:
            return {"success": False, "error": "A2A router not available"}

        agents_config = getattr(self.agent_loop, "_agents_config", None)
        if not agents_config:
            return {"success": False, "error": "Agents config not available"}

        # Look up team
        tm = TeamManager(agents_config)
        team_config = tm.get_team(team)
        if not team_config:
            available = [t.name for t in tm.list_teams()]
            return {
                "success": False,
                "error": f"Team '{team}' not found",
                "available_teams": available,
            }

        # Validate team
        errors = tm.validate_team(team)
        if errors:
            return {"success": False, "error": "Invalid team", "details": errors}

        # Runtime check: verify all members are registered with A2A router
        router = self.agent_loop.a2a_router
        unregistered = [
            m for m in team_config.members if not router.get_mailbox(m)
        ]
        if unregistered:
            return {
                "success": False,
                "error": f"Team members not registered: {unregistered}",
            }

        strategy = team_config.strategy
        logger.info(
            "[{}] Dispatching team task to '{}' (strategy={}, members={})",
            self.agent_loop.agent_id,
            team,
            strategy,
            team_config.members,
        )

        if strategy == "parallel":
            return await self._run_parallel(team_config, task, timeout)
        elif strategy == "sequential":
            return await self._run_sequential(team_config, task, timeout)
        elif strategy == "leader_delegate":
            return await self._run_leader_delegate(team_config, task, timeout)
        else:
            return {"success": False, "error": f"Unknown strategy: {strategy}"}

    async def _run_parallel(self, team_config, task: str, timeout: int) -> dict:
        """All members work concurrently via A2A requests."""
        router = self.agent_loop.a2a_router
        from_agent = self.agent_loop.agent_id

        async def request_member(member_id: str) -> dict:
            try:
                resp = await router.send_request(
                    from_agent=from_agent,
                    to_agent=member_id,
                    content=task,
                    timeout=timeout,
                )
                return {"agent": member_id, "status": "ok", "result": resp.content}
            except asyncio.TimeoutError:
                return {"agent": member_id, "status": "timeout", "result": ""}
            except Exception as e:
                return {"agent": member_id, "status": "error", "result": str(e)}

        tasks = [request_member(m) for m in team_config.members]
        results = await asyncio.gather(*tasks)

        return {
            "success": True,
            "team": team_config.name,
            "strategy": "parallel",
            "results": list(results),
        }

    async def _run_sequential(self, team_config, task: str, timeout: int) -> dict:
        """Members work one after another, each receiving prior context."""
        router = self.agent_loop.a2a_router
        from_agent = self.agent_loop.agent_id
        results = []
        accumulated_context = task

        for member_id in team_config.members:
            prompt = (
                f"Task: {task}\n\n"
                f"Previous context:\n{accumulated_context}"
                if results
                else task
            )
            try:
                resp = await router.send_request(
                    from_agent=from_agent,
                    to_agent=member_id,
                    content=prompt,
                    timeout=timeout,
                )
                results.append({"agent": member_id, "status": "ok", "result": resp.content})
                accumulated_context += f"\n\n[{member_id}]: {resp.content}"
            except asyncio.TimeoutError:
                results.append({"agent": member_id, "status": "timeout", "result": ""})
                break
            except Exception as e:
                results.append({"agent": member_id, "status": "error", "result": str(e)})
                break

        return {
            "success": True,
            "team": team_config.name,
            "strategy": "sequential",
            "results": results,
        }

    async def _run_leader_delegate(self, team_config, task: str, timeout: int) -> dict:
        """Leader decomposes the task and delegates subtasks to members."""
        router = self.agent_loop.a2a_router
        from_agent = self.agent_loop.agent_id
        leader = team_config.leader

        if not leader:
            return {"success": False, "error": "leader_delegate requires a leader"}

        workers = [m for m in team_config.members if m != leader]
        if not workers:
            return {"success": False, "error": "No workers besides leader"}

        # Step 1: Ask leader to decompose the task
        decompose_prompt = (
            f"You are the team leader. Decompose this task into subtasks, "
            f"one for each worker: {workers}\n\n"
            f"Task: {task}\n\n"
            f"Reply with a JSON array of objects: "
            f'[{{"worker": "<agent_id>", "subtask": "<description>"}}]'
        )

        try:
            leader_resp = await router.send_request(
                from_agent=from_agent,
                to_agent=leader,
                content=decompose_prompt,
                timeout=timeout // 2,
            )
        except (asyncio.TimeoutError, Exception) as e:
            return {"success": False, "error": f"Leader failed: {e}"}

        # Step 2: Parse leader's decomposition
        import json
        subtasks = self._parse_subtasks(leader_resp.content, workers)

        if not subtasks:
            # Fallback: send full task to all workers in parallel
            subtasks = [{"worker": w, "subtask": task} for w in workers]

        # Step 3: Delegate subtasks to workers in parallel
        async def delegate(item: dict) -> dict:
            wid = item["worker"]
            try:
                resp = await router.send_request(
                    from_agent=from_agent,
                    to_agent=wid,
                    content=item["subtask"],
                    timeout=timeout,
                )
                return {"agent": wid, "status": "ok", "result": resp.content}
            except asyncio.TimeoutError:
                return {"agent": wid, "status": "timeout", "result": ""}
            except Exception as e:
                return {"agent": wid, "status": "error", "result": str(e)}

        worker_results = await asyncio.gather(*[delegate(s) for s in subtasks])

        return {
            "success": True,
            "team": team_config.name,
            "strategy": "leader_delegate",
            "leader": leader,
            "decomposition": subtasks,
            "results": list(worker_results),
        }

    @staticmethod
    def _parse_subtasks(content: str, workers: list[str]) -> list[dict]:
        """Try to parse leader's JSON subtask decomposition."""
        import json
        import re

        # Try to find JSON array in the response
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if not match:
            return []

        try:
            parsed = json.loads(match.group())
            if not isinstance(parsed, list):
                return []
            # Validate structure
            result = []
            for item in parsed:
                w = item.get("worker", "")
                s = item.get("subtask", "")
                if w in workers and s:
                    result.append({"worker": w, "subtask": s})
            return result
        except (json.JSONDecodeError, AttributeError):
            return []
