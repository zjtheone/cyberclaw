"""Subagent manager for background task execution with A2A support."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from cyberclaw.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from cyberclaw.agent.tools.registry import ToolRegistry
from cyberclaw.agent.tools.shell import ExecTool
from cyberclaw.agent.tools.web import WebFetchTool, WebSearchTool
from cyberclaw.bus.events import InboundMessage
from cyberclaw.agent.announce_chain import AnnounceChainManager, AnnounceEvent, AnnounceType
from cyberclaw.bus.queue import MessageBus
from cyberclaw.config.schema import ExecToolConfig
from cyberclaw.providers.base import LLMProvider
from cyberclaw.utils.helpers import build_assistant_message
from cyberclaw.session.keys import SessionKey


class SubagentManager:
    """Manages background subagent execution with A2A support.

    Features:
    - Same-agent and cross-agent subagent spawning
    - Nested subagent support with depth limits
    - Session tracking and cleanup
    - Result announcement to parent sessions
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        serpapi_key: str | None = None,
        search_provider: str = "",
        web_proxy: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ):
        from cyberclaw.config.schema import ExecToolConfig

        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.serpapi_key = serpapi_key
        self.search_provider = search_provider
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
        target_agent_id: str | None = None,
        parent_depth: int = 0,
        max_depth: int = 1,
        max_retries: int = 0,
        retry_delay: float = 5.0,
        timeout: int = 0,
    ) -> str:
        """Spawn a subagent to execute a task in the background.

        Args:
            task: Task description
            label: Optional display label
            origin_channel: Origin channel for announcements
            origin_chat_id: Origin chat ID for announcements
            session_key: Origin session key
            target_agent_id: Target agent ID (default: same as origin)
            parent_depth: Current spawn depth (for nested subagents)
            max_depth: Maximum allowed spawn depth

        Returns:
            Result message (success or error)
        """
        # Check depth limit
        if parent_depth >= max_depth:
            return f"Error: Maximum spawn depth ({max_depth}) reached. Cannot spawn subagent."

        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        # Build session key for the subagent
        agent_id = target_agent_id or "default"
        subagent_session_key = SessionKey.create_subagent(agent_id, task_id)

        logger.info(
            "Spawned subagent [{}] at depth {} (max: {}): {}",
            task_id,
            parent_depth + 1,
            max_depth,
            display_label,
        )

        bg_task = asyncio.create_task(
            self._run_subagent_with_retry(
                task_id=task_id,
                task=task,
                label=display_label,
                origin=origin,
                session_key=str(subagent_session_key),
                parent_session_key=session_key,
                depth=parent_depth + 1,
                max_depth=max_depth,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
            )
        )
        self._running_tasks[task_id] = bg_task
        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        depth_info = f" (depth {parent_depth + 1}/{max_depth})" if parent_depth > 0 else ""
        return f"Subagent [{display_label}]{depth_info} started (id: {task_id}). I'll notify you when it completes."


    async def _publish_announce_via_bus(self, task_id, label, result, status, parent_session_key):
        """Publish announce event via MessageBus."""
        from cyberclaw.bus.events import OutboundMessage

        announce_msg = OutboundMessage(
            channel="system",
            chat_id="announce",
            content=f"ANNOUNCE|{task_id}|{label}|{status}|{result[:500]}",
            metadata={
                "type": "announce",
                "task_id": task_id,
                "label": label,
                "status": status,
                "parent_session": parent_session_key,
            }
        )

        try:
            await self.bus.publish_outbound(announce_msg)
            logger.debug("Published announce for task {}", task_id)
        except Exception as e:
            logger.error("Failed to publish announce: {}", e)

    async def _run_subagent_with_retry(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict,
        session_key: str,
        parent_session_key: str | None,
        depth: int,
        max_depth: int,
        max_retries: int = 0,
        retry_delay: float = 5.0,
        timeout: int = 0,
    ) -> None:
        """Run subagent with retry and timeout support."""
        from cyberclaw.agent.team.errors import (
            create_subagent_error,
            is_retryable_error,
            SubagentError,
        )

        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                if timeout > 0:
                    await asyncio.wait_for(
                        self._run_subagent(
                            task_id, task, label, origin, session_key,
                            parent_session_key, depth, max_depth,
                        ),
                        timeout=timeout,
                    )
                else:
                    await self._run_subagent(
                        task_id, task, label, origin, session_key,
                        parent_session_key, depth, max_depth,
                    )
                return

            except asyncio.TimeoutError:
                last_error = SubagentError(
                    error_type="timeout",
                    message=f"Task timed out after {timeout}s",
                    task_id=task_id,
                    retryable=attempt < max_retries,
                )

            except Exception as e:
                last_error = create_subagent_error(e, task_id=task_id)
                if not is_retryable_error(e):
                    break

            if attempt >= max_retries:
                break

            delay = retry_delay * (2 ** attempt)
            logger.warning(
                f"Subagent [{task_id}] failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.1f}s: {last_error.message}"
            )
            await asyncio.sleep(delay)
            attempt += 1

        logger.error(f"Subagent [{task_id}] failed after {attempt} attempts: {last_error}")

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        session_key: str,
        parent_session_key: str | None,
        depth: int,
        max_depth: int,
    ) -> None:
        """Execute the subagent task and announce the result.

        Args:
            task_id: Unique task ID
            task: Task description
            label: Display label
            origin: Origin channel/chat_id
            session_key: This subagent's session key
            parent_session_key: Parent session key
            depth: Current depth
            max_depth: Maximum depth
        """
        logger.info("Subagent [{}] starting task at depth {}: {}", task_id, depth, label)

        try:
            # Build subagent tools (no message tool, no spawn tool if at max depth)
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    restrict_to_workspace=self.restrict_to_workspace,
                )
            )
            tools.register(WebSearchTool(
                api_key=self.brave_api_key,
                serpapi_key=self.serpapi_key,
                provider=self.search_provider,
                proxy=self.web_proxy,
            ))
            tools.register(WebFetchTool(proxy=self.web_proxy))

            # Allow spawn tool only if not at max depth
            if depth < max_depth:
                from cyberclaw.agent.tools.spawn import SpawnTool

                spawn_tool = SpawnTool(self)
                tools.register(spawn_tool)

            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task, depth, max_depth)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            # Run agent loop (limited iterations)
            max_iterations = 15
            iteration = 0
            final_result: str | None = None

            while iteration < max_iterations:
                iteration += 1

                response = await self.provider.chat_with_retry(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    reasoning_effort=self.reasoning_effort,
                )

                if response.has_tool_calls:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append(build_assistant_message(
                        response.content or "",
                        tool_calls=tool_call_dicts,
                        reasoning_content=response.reasoning_content,
                        thinking_blocks=response.thinking_blocks,
                    ))

                    # Execute tools
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug(
                            "Subagent [{}] executing: {} with arguments: {}",
                            task_id,
                            tool_call.name,
                            args_str,
                        )
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.name,
                                "content": result,
                            }
                        )
                else:
                    final_result = response.content
                    break

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            logger.info("Subagent [{}] completed successfully at depth {}", task_id, depth)
            await self._announce_result(
                task_id=task_id,
                label=label,
                task=task,
                result=final_result,
                origin=origin,
                status="ok",
                depth=depth,
                session_key=session_key,
                parent_session_key=parent_session_key,
            )

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error("Subagent [{}] failed at depth {}: {}", task_id, depth, e)
            await self._announce_result(
                task_id=task_id,
                label=label,
                task=task,
                result=error_msg,
                origin=origin,
                status="error",
                depth=depth,
                session_key=session_key,
                parent_session_key=parent_session_key,
            )

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
        depth: int,
        session_key: str,
        parent_session_key: str | None,
    ) -> None:
        """Announce the subagent result to the parent session.

        Args:
            task_id: Task ID
            label: Display label
            task: Task description
            result: Result message
            origin: Origin channel/chat_id
            status: "ok" or "error"
            depth: Spawn depth
            session_key: This subagent's session key
            parent_session_key: Parent session key
        """
        status_text = "completed successfully" if status == "ok" else "failed"
        depth_info = f" (depth {depth})" if depth > 1 else ""

        announce_content = f"""[Subagent '{label}'{depth_info} {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
            metadata={
                "task_id": task_id,
                "session_key": session_key,
                "parent_session_key": parent_session_key,
                "depth": depth,
            },
        )

        await self.bus.publish_inbound(msg)
        logger.debug(
            "Subagent [{}] announced result to {}:{}", task_id, origin["channel"], origin["chat_id"]
        )

    def _build_subagent_prompt(self, task: str, depth: int, max_depth: int) -> str:
        """Build a focused system prompt for the subagent.

        Args:
            task: Task description
            depth: Current depth
            max_depth: Maximum depth

        Returns:
            System prompt
        """
        from cyberclaw.agent.context import ContextBuilder
        from cyberclaw.agent.skills import SkillsLoader
        from datetime import datetime
        import time as _time

        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"
        time_ctx = f"Current Time: {now} ({tz})"

        can_spawn = (
            "Yes - you can spawn your own subagents"
            if depth < max_depth
            else "No - maximum depth reached"
        )

        parts = [f"""# Subagent

{time_ctx}

## Spawn Depth
You are at depth {depth} of {max_depth}.

## Can You Spawn Subagents?
{can_spawn}

You are a subagent spawned by the main agent to complete a specific task.

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final result will be reported back to the parent agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings
5. If you can spawn subagents (depth < max), use them for parallel tasks

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- Complete the task thoroughly
- {"Spawn subagents for parallel work" if depth < max_depth else "Cannot spawn subagents (max depth reached)"}

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Access the main agent's conversation history
- {"Spawn more subagents" if depth >= max_depth else ""}

## Workspace
{self.workspace}"""]

        skills_summary = SkillsLoader(self.workspace).build_skills_summary()
        if skills_summary:
            parts.append(f"## Skills\n\nRead SKILL.md with read_file to use a skill.\n\n{skills_summary}")

        parts.append("\nWhen you have completed the task, provide a clear summary of your findings or actions.")

        return "\n\n".join(parts)

    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all subagents for the given session.

        Args:
            session_key: Session key

        Returns:
            Count of cancelled tasks
        """
        tasks = [
            self._running_tasks[tid]
            for tid in self._session_tasks.get(session_key, [])
            if tid in self._running_tasks and not self._running_tasks[tid].done()
        ]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)

    def get_task_info(self, task_id: str) -> dict[str, Any] | None:
        """Get information about a running task.

        Args:
            task_id: Task ID

        Returns:
            Task info dict or None if not found
        """
        task = self._running_tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task_id,
            "done": task.done(),
            "cancelled": task.cancelled(),
        }
