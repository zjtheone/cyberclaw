"""Orchestrator-specific tools for task decomposition and worker management."""

import asyncio
from typing import Any

from loguru import logger

from cyberclaw.agent.tools.base import Tool


class DecomposeAndSpawnTool(Tool):
    """Tool for Orchestrator to decompose tasks and dispatch to workers via A2A.

    Sends subtasks to other agents via A2A router and waits for their responses.
    Falls back to spawning subagents if A2A is not available.
    """

    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
        self._agent_id = agent_loop.agent_id if hasattr(agent_loop, 'agent_id') else 'default'

    @property
    def name(self) -> str:
        return "decompose_and_spawn"

    @property
    def description(self) -> str:
        return (
            "**Orchestrator's primary tool** - Decompose a complex task and dispatch workers in parallel.\n\n"
            "This tool:\n"
            "1. Sends subtasks to worker agents via A2A communication\n"
            "2. Waits for all workers to complete (in parallel)\n"
            "3. Aggregates results from all workers\n\n"
            "**IMPORTANT: Do NOT specify agent_id** — workers are auto-distributed across available agents "
            "for maximum parallelism. Only specify agent_id if a task strictly requires a specific agent.\n\n"
            "**Parameters:**\n"
            "- `task`: Main task description\n"
            "- `workers`: List of {label, task} for each worker. Do NOT include agent_id.\n"
            "- `timeout`: Timeout in seconds (default: 1800, do NOT override unless needed)\n\n"
            "**Example:**\n"
            "```json\n"
            "{\n"
            '  "task": "Build an e-commerce site",\n'
            '  "workers": [\n'
            '    {"label": "backend", "task": "Implement API"},\n'
            '    {"label": "frontend", "task": "Implement UI"},\n'
            '    {"label": "database", "task": "Design schema"}\n'
            '  ]\n'
            "}\n"
            "```"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Main task to decompose",
                },
                "workers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "Worker label (e.g., 'backend', 'frontend')",
                            },
                            "task": {
                                "type": "string",
                                "description": "Subtask for this worker",
                            },
                            "agent_id": {
                                "type": "string",
                                "description": "Target agent ID (optional, auto-assigned if omitted)",
                            },
                        },
                        "required": ["label", "task"],
                    },
                    "description": "List of workers to dispatch",
                },
                "timeout": {
                    "type": "integer",
                    "default": 1800,
                    "description": "Timeout in seconds (default: 1800 = 30 minutes)",
                },
            },
            "required": ["task", "workers"],
        }

    async def execute(
        self,
        task: str,
        workers: list[dict],
        timeout: int = 1800,
        **kwargs: Any,
    ) -> dict:
        """Dispatch subtasks to worker agents via A2A and collect results."""
        router = getattr(self.agent_loop, 'a2a_router', None)
        if not router:
            return {"success": False, "error": "A2A router not available"}

        logger.info(
            "Orchestrator decomposing '{}' into {} workers",
            task[:80],
            len(workers),
        )

        # Distribute workers across available agents using round-robin
        # This ensures parallel execution even if LLM assigns all to the same agent
        available_agents = [
            aid for aid in router._mailboxes.keys()
            if aid != self._agent_id
        ]

        if available_agents:
            for i, w in enumerate(workers):
                w["agent_id"] = available_agents[i % len(available_agents)]
        else:
            for w in workers:
                w["agent_id"] = self._agent_id

        # Dispatch all workers in parallel via A2A
        async def dispatch_worker(w: dict) -> dict:
            target = w["agent_id"]
            label = w["label"]
            subtask = w["task"]
            try:
                logger.info("[{}] Dispatching '{}' to agent '{}'", self._agent_id, label, target)
                resp = await router.send_request(
                    from_agent=self._agent_id,
                    to_agent=target,
                    content=subtask,
                    timeout=timeout,
                )
                return {
                    "label": label,
                    "agent_id": target,
                    "status": "ok",
                    "result": resp.content,
                }
            except asyncio.TimeoutError:
                return {"label": label, "agent_id": target, "status": "timeout", "result": ""}
            except Exception as e:
                return {"label": label, "agent_id": target, "status": "error", "result": str(e)}

        results = await asyncio.gather(*[dispatch_worker(w) for w in workers])

        ok_count = sum(1 for r in results if r["status"] == "ok")
        logger.info("Orchestrator: {}/{} workers completed successfully", ok_count, len(results))

        return {
            "success": ok_count > 0,
            "task": task,
            "worker_count": len(results),
            "results": list(results),
        }


class AggregateResultsTool(Tool):
    """Tool for Orchestrator to aggregate worker results."""
    
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
    
    @property
    def name(self) -> str:
        return "aggregate_results"
    
    @property
    def description(self) -> str:
        return (
            "Aggregate results from spawned workers.\n\n"
            "Use this after spawn/wait to combine all worker outputs into a final result.\n\n"
            "**Parameters:** None (automatically aggregates from current session)\n\n"
            "**Returns:** Aggregated summary of all worker results"
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    async def execute(self, **kwargs: Any) -> dict:
        """Aggregate results from workers."""
        if hasattr(self.agent_loop, 'get_worker_results'):
            results = self.agent_loop.get_worker_results()
            return {
                "success": True,
                "result_count": len(results),
                "results": results,
            }
        else:
            return {
                "success": False,
                "error": "Worker results not available yet",
                "results": [],
            }
