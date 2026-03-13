"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Dict

import json_repair
from loguru import logger

from cyberclaw.agent.checkpoint import CheckpointManager
from cyberclaw.agent.context import ContextBuilder
from cyberclaw.agent.memory import MemoryConsolidator, MemoryStore
from cyberclaw.agent.permissions import PermissionGate, PermissionResult
from cyberclaw.agent.subagent import SubagentManager
from cyberclaw.agent.tools.cron import CronTool
from cyberclaw.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from cyberclaw.agent.tools.message import MessageTool
from cyberclaw.agent.tools.orchestrator import DecomposeAndSpawnTool, AggregateResultsTool
from cyberclaw.agent.tools.registry import ToolRegistry
from cyberclaw.agent.tools.shell import ExecTool
from cyberclaw.agent.tools.spawn import SpawnTool
from cyberclaw.agent.tools.team_task import TeamTaskTool
from cyberclaw.agent.tools.web import WebFetchTool, WebSearchTool
from cyberclaw.bus.events import InboundMessage, OutboundMessage
from cyberclaw.bus.queue import MessageBus
from cyberclaw.providers.base import LLMStreamChunk, LLMProvider
from cyberclaw.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from cyberclaw.config.schema import ChannelsConfig, ExecToolConfig, AgentsConfig
    from cyberclaw.cron.service import CronService
    from cyberclaw.agent.a2a.router import A2ARouter

from cyberclaw.agent.a2a.types import AgentMessage, MessagePriority, MessageType
from cyberclaw.agent.announce_chain import AnnounceChainManager


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        agent_id: str = "default",  # Agent identifier
        model: str | None = None,
        max_iterations: int = 40,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        reasoning_effort: str | None = None,
        context_window_tokens: int = 65_536,
        memory_window: int = 50,
        brave_api_key: str | None = None,
        serpapi_key: str | None = None,
        search_provider: str = "",
        web_proxy: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        context_window: int = 120000,
        on_tool_call: Callable[[str, str, str], None] | None = None,
        auto_verify: bool = True,
        auto_verify_command: str = "",
        sandbox: bool = False,
        permission_mode: str = "auto",
        thinking_budget: int = 0,
        memory_search_config: Optional[Dict[str, Any]] = None,
        mcp_servers: dict | None = None,
        channels_config: "ChannelsConfig | None" = None,
        on_thinking: Callable[[str], None] | None = None,
        on_iteration: Callable[[int, int], None] | None = None,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_plan_progress: Callable[[list], None] | None = None,
        agents_config: "AgentsConfig | None" = None,
    ):
        from cyberclaw.config.schema import ExecToolConfig
        from cyberclaw.cron.service import CronService

        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.agent_id = agent_id
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.frequency_penalty = frequency_penalty
        self.reasoning_effort = reasoning_effort
        self.context_window_tokens = context_window_tokens
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.serpapi_key = serpapi_key
        self.search_provider = search_provider
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.context_window = context_window
        self.on_tool_call = on_tool_call
        self.auto_verify = auto_verify
        self.auto_verify_command = auto_verify_command
        self.sandbox = sandbox
        self.thinking_budget = thinking_budget
        self.memory_search_config = memory_search_config
        self.on_thinking = on_thinking
        self.on_iteration = on_iteration
        self.on_tool_start = on_tool_start
        self.on_status = on_status
        self.on_plan_progress = on_plan_progress

        # MCP support
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None

        # Store agents config for Broadcast tool
        self._agents_config = agents_config

        # Build role-specific system prompt suffix (for orchestrator, etc.)
        self._role_prompt = self._build_role_prompt()
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()

        # Checkpoint system (Phase 1A)
        self.checkpoint = CheckpointManager(workspace)

        # Permission gate (Phase 1C)
        self.permission_gate = PermissionGate(
            mode=permission_mode,
            workspace=str(workspace),
        )

        self.context = ContextBuilder(workspace, memory_search_config)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=reasoning_effort,
            brave_api_key=brave_api_key,
            serpapi_key=serpapi_key,
            search_provider=search_provider,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        # Persistent shell session (Shell or Docker)
        if self.sandbox:
            from cyberclaw.agent.terminal.docker_session import DockerSession

            image = self.exec_config.sandbox_image
            self.shell_session = DockerSession(workspace, image=image)
        else:
            from cyberclaw.agent.terminal.session import ShellSession

            self.shell_session = ShellSession(workspace)

        # LSP Manager (Phase 7)
        from cyberclaw.agent.code.lsp import LSPManager

        self.lsp_manager = LSPManager(workspace)

        # Metrics Tracker (Phase 9)
        from cyberclaw.agent.metrics import MetricsTracker

        self.metrics = MetricsTracker(workspace)

        # Conversation compactor (Phase 2B)
        from cyberclaw.agent.compaction import ConversationCompactor

        self.compactor = ConversationCompactor(provider, model=self.model)

        # Hooks system (Phase 4B)
        from cyberclaw.agent.hooks import HookRegistry

        self.hooks = HookRegistry()

        # MCP manager (Phase 4A)
        from cyberclaw.mcp.registry import MCPManager

        self.mcp_manager = MCPManager()

        # Token-based memory consolidator (from HEAD)
        self.memory_consolidator = MemoryConsolidator(
            workspace=workspace,
            provider=provider,
            model=self.model,
            sessions=self.sessions,
            context_window_tokens=context_window_tokens,
            build_messages=self.context.build_messages,
            get_tool_definitions=self.tools.get_definitions,
        )

        # A2A router (set externally by MultiAgentGateway for shared routing)
        self.a2a_router: "A2ARouter | None" = None

        # Announce chain for hierarchical result aggregation
        self.announce_chain = AnnounceChainManager()

        # Self-Improving Agent Components (P0/P1/P2)
        from cyberclaw.agent.reflection import ReflectionEngine
        from cyberclaw.agent.experience import ExperienceRepository
        from cyberclaw.agent.confidence import ConfidenceEvaluator
        from cyberclaw.agent.tool_optimizer import ToolOptimizer
        from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer
        from cyberclaw.agent.skills import SkillsLoader

        self.reflection_engine = ReflectionEngine(workspace, provider, self.model)
        self.experience_repo = ExperienceRepository(workspace)

        # Confidence Evaluator (P1)
        self.confidence_evaluator = ConfidenceEvaluator(
            workspace,
            provider=provider,
            model=self.model,
            threshold=0.7,
            auto_verify=self.auto_verify,
        )

        # Tool Optimizer (P1)
        self.tool_optimizer = ToolOptimizer(
            workspace,
            metrics_tracker=self.metrics,
            min_samples=3,
            prefer_fast_tools=True,
        )

        # Dynamic skill discovery (P2)
        self.skills_loader = SkillsLoader(workspace)
        self._known_skills: dict[str, str] = {
            s["name"]: s["source"]
            for s in self.skills_loader.list_skills(filter_unavailable=False)
        }

        # Skill Evolution Analyzer (P2)
        self.skill_analyzer = SkillEvolutionAnalyzer(
            workspace=workspace,
            experience_repo=self.experience_repo,
            metrics_tracker=self.metrics,
            tool_optimizer=self.tool_optimizer,
            skills_dir=workspace / "skills",
            skills_loader=self.skills_loader,
        )

        # Track tool execution for reflection
        self._current_task_tool_calls: list[dict[str, Any]] = []
        self._current_task_start_time: float = 0.0
        self._current_task_description: str = ""
        self._pending_reflection_tasks: set[asyncio.Task] = set()

        self._running = False
        self._processing = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._processing_lock = asyncio.Lock()
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir, checkpoint=self.checkpoint))
        self.tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir, checkpoint=self.checkpoint))
        self.tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))

        # Undo / checkpoint tools (Phase 1A)
        from cyberclaw.agent.tools.undo import UndoTool, ListChangesTool

        self.tools.register(UndoTool(self.checkpoint))
        self.tools.register(ListChangesTool(self.checkpoint))

        # Git tools (Phase 1B)
        from cyberclaw.agent.tools.git import (
            GitStatusTool,
            GitDiffTool,
            GitCommitTool,
            GitLogTool,
            GitCheckoutTool,
        )

        ws = str(self.workspace)
        self.tools.register(GitStatusTool(ws))
        self.tools.register(GitDiffTool(ws))
        self.tools.register(GitCommitTool(ws))
        self.tools.register(GitLogTool(ws))
        self.tools.register(GitCheckoutTool(ws))

        # Batch edit tool (Phase 4C)
        from cyberclaw.agent.tools.batch_edit import BatchEditTool

        self.tools.register(BatchEditTool(self.checkpoint, allowed_dir=allowed_dir))

        # Shell tools
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                session=self.shell_session if self.sandbox else None,
                path_append=self.exec_config.path_append,
            )
        )

        # Persistent shell tool (stateful)
        from cyberclaw.agent.tools.terminal import ShellTool

        self.tools.register(ShellTool(self.shell_session))

        # Code Intelligence Tools
        from cyberclaw.agent.tools.code import ReadFileMapTool

        if self.context.repomap:
            self.tools.register(ReadFileMapTool(self.workspace, self.context.repomap))

        # Smart Context (Focus Mode)
        from cyberclaw.agent.tools.code_focused import ReadFileFocusedTool

        if hasattr(self.context, "folding_engine") and self.context.folding_engine:
            self.tools.register(ReadFileFocusedTool(self.workspace, self.context.folding_engine))

        # Semantic Search (LSP-Lite) - Phase 7
        from cyberclaw.agent.tools.lsp import LSPDefinitionTool, LSPReferencesTool, LSPHoverTool

        self.tools.register(LSPDefinitionTool(self.lsp_manager))
        self.tools.register(LSPReferencesTool(self.lsp_manager))
        self.tools.register(LSPHoverTool(self.lsp_manager))

        # Refactoring Tools (Phase 8)
        from cyberclaw.agent.tools.refactor import RefactorRenameTool

        self.tools.register(RefactorRenameTool(self.lsp_manager))

        # Metrics Tool (Phase 9)
        from cyberclaw.agent.tools.metrics import GetMetricsTool

        self.tools.register(GetMetricsTool(self.metrics))

        # Legacy Semantic Search (Index-based)
        from cyberclaw.agent.tools.search_semantic import FindDefinitionsTool, FindReferencesTool

        if hasattr(self.context, "symbol_index") and self.context.symbol_index:
            self.tools.register(FindDefinitionsTool(self.workspace, self.context.symbol_index))
            self.tools.register(FindReferencesTool(self.workspace, self.context.symbol_index))

        # Diagnostics (Phase 4)
        from cyberclaw.agent.diagnostics.tool import DiagnosticTool

        self.tools.register(DiagnosticTool(self.workspace))

        # Planning (Phase 5)
        from cyberclaw.agent.planner import Planner
        from cyberclaw.agent.tools.planner import PlanTool, UpdatePlanStepTool

        self.planner = Planner(self.provider, self.context, self.workspace)
        self.tools.register(PlanTool(self.planner))

        # Memory Search Tool (Phase 6)
        from cyberclaw.agent.tools.memory_search import MemorySearchTool
        self.tools.register(MemorySearchTool(self.context.memory))
        self.tools.register(UpdatePlanStepTool(self.planner))

        # Wire plan progress callback
        if self.on_plan_progress:
            from dataclasses import asdict
            self.planner._on_plan_progress = lambda steps: self.on_plan_progress(
                [asdict(s) for s in steps]
            )

        # Search tools
        from cyberclaw.agent.tools.search import GrepTool, FindFilesTool

        self.tools.register(GrepTool(allowed_dir=allowed_dir))
        self.tools.register(FindFilesTool(allowed_dir=allowed_dir))

        # Web tools
        self.tools.register(WebSearchTool(
            api_key=self.brave_api_key,
            serpapi_key=self.serpapi_key,
            provider=self.search_provider,
            proxy=self.web_proxy,
        ))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Orchestrator tools (for task decomposition)
        if self.agent_id == "orchestrator":
            decompose_tool = DecomposeAndSpawnTool(self)
            self.tools.register(decompose_tool)

            aggregate_tool = AggregateResultsTool(self)
            self.tools.register(aggregate_tool)
            logger.info("Registered Orchestrator tools for agent {}", self.agent_id)

        # Broadcast tool (for team communication)
        if self._agents_config:
            from cyberclaw.agent.tools.broadcast import BroadcastTool
            broadcast_tool = BroadcastTool(
                manager=self.subagents,
                agents_config=self._agents_config,
            )
            broadcast_tool._agent_loop = self
            broadcast_tool.set_context(
                channel="cli",
                chat_id="direct",
                session_key="cli:direct",
                agent_id="default",
            )
            self.tools.register(broadcast_tool)

        # Team task tool (for triggering team collaboration via A2A)
        if self._agents_config:
            team_tool = TeamTaskTool(self)
            self.tools.register(team_tool)
        else:
            logger.debug(
                "[{}] No agents_config -- team_task tool not registered",
                self.agent_id,
            )

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # Self-Improving Agent Tools (P0/P1/P2)
        from cyberclaw.agent.tools.self_improvement import (
            GetReflectionsTool,
            GetExperienceTool,
            GetSelfImprovementMetricsTool,
            GetConfidenceTool,
            GetToolRecommendationsTool,
            GetSkillEvolutionTool,
        )

        # P0 Tools
        self.tools.register(GetReflectionsTool(self.reflection_engine, self.experience_repo))
        self.tools.register(GetExperienceTool(self.experience_repo))

        # P1 Tools
        self.tools.register(GetConfidenceTool(self.confidence_evaluator))
        self.tools.register(GetToolRecommendationsTool(self.tool_optimizer))

        # P2 Tools - Re-initialize skill analyzer after tools are registered
        from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer
        self.skill_analyzer = SkillEvolutionAnalyzer(
            self.workspace,
            experience_repo=self.experience_repo,
            metrics_tracker=self.metrics,
            tool_optimizer=self.tool_optimizer,
            skills_dir=self.workspace / "skills",
            skills_loader=self.skills_loader,
        )
        self.tools.register(GetSkillEvolutionTool(self.skill_analyzer))

        # Combined metrics tool
        self.tools.register(GetSelfImprovementMetricsTool(
            self.reflection_engine,
            self.experience_repo,
            self.metrics,
            tool_optimizer=self.tool_optimizer,
            skill_analyzer=self.skill_analyzer,
        ))
        logger.info("Registered self-improvement tools (P0/P1/P2)")

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>...</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}...")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    def _build_role_prompt(self) -> str:
        """Build role-specific prompt based on agent_id and available team tools."""
        parts = []

        # Orchestrator role
        if self.agent_id == "orchestrator":
            from cyberclaw.agent.team.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT
            parts.append(ORCHESTRATOR_SYSTEM_PROMPT)

        # Team awareness
        if self._agents_config and self._agents_config.teams:
            team_info = []
            for t in self._agents_config.teams:
                members_str = ", ".join(t.members)
                leader_str = f", leader={t.leader}" if t.leader else ""
                team_info.append(f"  - {t.name}: [{members_str}] strategy={t.strategy}{leader_str}")
            parts.append(
                "## Available Teams\n"
                "You can use the `team_task` tool to dispatch tasks to these teams:\n"
                + "\n".join(team_info)
                + "\n\nFor complex tasks, prefer delegating to teams rather than doing everything yourself."
            )

        return "\n\n".join(parts)

    def _inject_role_prompt(self, messages: list[dict]) -> list[dict]:
        """Inject role-specific prompt into the system message."""
        if not self._role_prompt or not messages:
            return messages
        if messages[0].get("role") == "system":
            messages[0] = {
                **messages[0],
                "content": messages[0]["content"] + "\n\n" + self._role_prompt,
            }
        return messages

    def get_runtime_status(self) -> dict:
        """Return runtime status of this agent."""
        mailbox_depth = 0
        if self.a2a_router:
            mailbox = self.a2a_router.get_mailbox(self.agent_id)
            if mailbox:
                mailbox_depth = mailbox.queue.qsize()

        subagent_count = 0
        if hasattr(self, "subagents"):
            subagent_count = self.subagents.get_running_count()

        tool_names = []
        if hasattr(self, "tools"):
            tool_names = self.tools.tool_names

        is_ready = self._running or (self.a2a_router is not None)

        return {
            "agent_id": self.agent_id,
            "ready": is_ready,
            "processing": self._processing,
            "model": self.model,
            "subagent_count": subagent_count,
            "a2a_mailbox_depth": mailbox_depth,
            "tools": tool_names,
        }

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop (used by gateway/bus message processing)."""
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        while iteration < self.max_iterations:
            iteration += 1

            tool_defs = self.tools.get_definitions()

            response = await self.provider.chat_with_retry(
                messages=messages,
                tools=tool_defs,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
                frequency_penalty=self.frequency_penalty,
                thinking_budget=self.thinking_budget,
            )

            if response.has_tool_calls:
                if on_progress:
                    thought = self._strip_think(response.content)
                    if thought:
                        await on_progress(thought)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                clean = self._strip_think(response.content)
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        logger.info("Agent loop started (agent_id={})", self.agent_id)

        # Start MCP servers and register their tools
        await self._start_mcp_servers()
        await self._connect_mcp()

        try:
            while self._running:
                try:
                    msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Poll A2A mailbox during idle time
                    await self._poll_a2a_mailbox()
                    continue

                if msg.content.strip().lower() == "/stop":
                    await self._handle_stop(msg)
                else:
                    task = asyncio.create_task(self._dispatch(msg))
                    self._active_tasks.setdefault(msg.session_key, []).append(task)
                    task.add_done_callback(
                        lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None
                    )
        finally:
            # Wait for pending reflection tasks
            if self._pending_reflection_tasks:
                logger.info(f"Waiting for {len(self._pending_reflection_tasks)} pending reflection tasks...")
                done, pending = await asyncio.wait(self._pending_reflection_tasks, timeout=10.0)
                if pending:
                    logger.warning(f"{len(pending)} reflection tasks did not complete in time, cancelling")
                    for t in pending:
                        t.cancel()

            if hasattr(self, "lsp_manager"):
                logger.info("Shutting down LSP manager...")
                await self.lsp_manager.shutdown()
            if hasattr(self, "mcp_manager"):
                logger.info("Shutting down MCP servers...")
                await self.mcp_manager.stop_all()
            if hasattr(self, "shell_session") and hasattr(self.shell_session, "close"):
                try:
                    await self.shell_session.close()
                except Exception:
                    pass
            if hasattr(self, "checkpoint"):
                self.checkpoint.cleanup()

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""
        async with self._processing_lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _start_mcp_servers(self) -> None:
        """Start configured MCP servers and register their tools."""
        try:
            from cyberclaw.config.loader import load_config

            config = load_config()
            if config.mcp.servers:
                from cyberclaw.mcp.config import MCPConfig

                mcp_config = MCPConfig(
                    servers={name: server for name, server in config.mcp.servers.items()}
                )
                tools = await self.mcp_manager.start_servers(mcp_config)
                for tool in tools:
                    self.tools.register(tool)
                if tools:
                    logger.info(f"Registered {len(tools)} MCP tools")
        except Exception as e:
            logger.debug(f"MCP startup skipped: {e}")

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from cyberclaw.agent.tools.mcp import connect_mcp_servers

        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass
            self._mcp_stack = None

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # Handle system messages (subagent announces)
        if msg.channel == "system":
            return await self._process_system_message(msg)

        self._processing = True
        self._current_task_start_time = time.time()
        self._current_task_description = msg.content[:500]
        self._current_task_tool_calls = []
        try:
            return await self._process_message_inner(msg, session_key, on_progress)
        finally:
            self._processing = False

    async def _process_message_inner(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Inner message processing logic."""
        key = session_key or msg.session_key

        agent_id = key.split(":")[0] if key and ":" in key else "unknown"

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("[{}] Processing: {}", agent_id, preview)
        session = self.sessions.get_or_create(key)

        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            try:
                if not await self.memory_consolidator.archive_unconsolidated(session):
                    return OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Memory archival failed, session not cleared. Please try again.",
                    )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )

            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="cyberclaw commands:\n/new -- Start a new conversation\n/stop -- Stop the current task\n/help -- Show available commands")

        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        # Auto-load frequent skills
        frequent_skills = None
        if self.skill_analyzer:
            frequent = self.skill_analyzer.get_frequently_used_skills(min_uses=3, min_success_rate=0.5)
            if frequent:
                frequent_skills = frequent
                logger.debug("Auto-loading frequent skills: {}", frequent)

        history = session.get_history(max_messages=0)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            skill_names=frequent_skills,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
            plan_context=self.planner.get_progress_context() if hasattr(self, 'planner') else None,
        )
        initial_messages = self._inject_role_prompt(initial_messages)

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        # Agent loop
        iteration = 0
        final_content = None
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        progress_cb = on_progress or _bus_progress
        # Track save boundary — updated when compaction changes list length
        save_from = 1 + len(history)

        while iteration < self.max_iterations:
            iteration += 1

            if self.on_iteration:
                try:
                    self.on_iteration(iteration, self.max_iterations)
                except Exception:
                    pass

            # Trim context if approaching window limit
            pre_len = len(initial_messages)
            initial_messages = self._trim_context(initial_messages)
            initial_messages = await self._compact_context(initial_messages)
            post_len = len(initial_messages)
            if post_len != pre_len:
                save_from = max(1, save_from - (pre_len - post_len))

            if self.on_status:
                try:
                    self.on_status("thinking")
                except Exception:
                    pass

            tool_defs = self.tools.get_definitions()

            logger.info(
                "[{}] Calling LLM (model={}, msgs={}, tools={})",
                self.agent_id,
                self.model,
                len(initial_messages),
                len(tool_defs),
            )

            response = await self.provider.chat_with_retry(
                messages=initial_messages,
                tools=tool_defs,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
                frequency_penalty=self.frequency_penalty,
                thinking_budget=self.thinking_budget,
            )

            logger.info("[{}] LLM responded (iter {})", self.agent_id, iteration)

            # Track token usage
            if response.usage:
                for k in total_usage:
                    total_usage[k] += response.usage.get(k, 0)
                self.metrics.record_tokens(
                    prompt=response.usage.get("prompt_tokens", 0),
                    completion=response.usage.get("completion_tokens", 0),
                )

            # Notify thinking content
            if response.reasoning_content and self.on_thinking:
                try:
                    self.on_thinking(response.reasoning_content)
                except Exception:
                    pass

            if response.has_tool_calls:
                if self.on_status:
                    try:
                        self.on_status("executing_tools")
                    except Exception:
                        pass

                if progress_cb:
                    thought = self._strip_think(response.content)
                    if thought:
                        await progress_cb(thought)
                    await progress_cb(self._tool_hint(response.tool_calls), tool_hint=True)

                for tc in response.tool_calls:
                    if self.on_tool_start:
                        try:
                            self.on_tool_start(tc.name, tc.arguments)
                        except Exception:
                            pass

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
                initial_messages = self.context.add_assistant_message(
                    initial_messages,
                    response.content,
                    tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                # Execute tools (with permission checks and parallel read-only execution)
                executed_tools = []
                last_modified_file = ""
                tool_results = await self._execute_tools(response.tool_calls)
                for tool_call, result in zip(response.tool_calls, tool_results):
                    result_preview = result[:120] + "..." if len(result) > 120 else result

                    if self.on_tool_call:
                        try:
                            args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                            self.on_tool_call(tool_call.name, args_str[:100], result_preview)
                        except Exception:
                            pass

                    initial_messages = self.context.add_tool_result(
                        initial_messages, tool_call.id, tool_call.name, result
                    )
                    executed_tools.append(tool_call.name)
                    if tool_call.name in ("write_file", "edit_file"):
                        last_modified_file = tool_call.arguments.get("path", "")

                # Auto-verify after file modifications
                initial_messages, _has_errors = await self._auto_verify(
                    initial_messages, executed_tools, last_modified_file
                )
            else:
                clean = self._strip_think(response.content)
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                initial_messages = self.context.add_assistant_message(
                    initial_messages, clean,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None:
            if iteration >= self.max_iterations:
                logger.warning("Max iterations ({}) reached", self.max_iterations)
                final_content = (
                    f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                    "without completing the task. You can try breaking the task into smaller steps."
                )
            else:
                final_content = "I've completed processing but have no response to give."

        # Token usage info
        if total_usage.get("total_tokens", 0) > 0:
            logger.info("Token usage: {}", total_usage)

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        # Save to session
        is_error = response.finish_reason == "error" if response else False
        self._save_turn(session, initial_messages, save_from)
        self.sessions.save(session)
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        # Self-Improving: Generate reflection after task completion (P0)
        task_status = "failure" if is_error else ("success" if iteration < self.max_iterations else "partial_success")

        reflection_task = asyncio.create_task(
            self._generate_task_reflection(
                task_description=self._current_task_description or msg.content[:200],
                status=task_status,
                duration=time.time() - self._current_task_start_time,
                tokens_used=total_usage.get("total_tokens", 0),
            )
        )
        self._pending_reflection_tasks.add(reflection_task)

        def _reflection_done(t: asyncio.Task) -> None:
            self._pending_reflection_tasks.discard(t)
            if not t.cancelled() and t.exception():
                logger.error("Reflection task failed: {}", t.exception())

        reflection_task.add_done_callback(_reflection_done)

        # If message() tool already sent a reply to the user in this turn,
        # suppress the automatic OutboundMessage to avoid duplication.
        # BUT: never suppress for A2A channels — the A2A response goes to the
        # requesting agent, not the user, so it must always be returned.
        if msg.channel != "a2a" and (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata={**(msg.metadata or {}), "usage": total_usage},
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process a system message (e.g., subagent announce)."""
        logger.info("Processing system message from {}", msg.sender_id)

        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        self._set_tool_context(origin_channel, origin_chat_id, msg.metadata.get("message_id"))

        _frequent = self.skill_analyzer.get_frequently_used_skills() if self.skill_analyzer else None
        history = session.get_history(max_messages=0)
        messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            skill_names=_frequent or None,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        messages = self._inject_role_prompt(messages)

        final_content, _, all_msgs = await self._run_agent_loop(messages)
        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        return OutboundMessage(
            channel=origin_channel, chat_id=origin_chat_id,
            content=final_content or "Background task completed.",
        )

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # skip empty assistant messages
            if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                            continue
                        if (c.get("type") == "image_url"
                                and c.get("image_url", {}).get("url", "").startswith("data:image/")):
                            filtered.append({"type": "text", "text": "[image]"})
                        else:
                            filtered.append(c)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _execute_tools(self, tool_calls: list) -> list[str]:
        """Execute tool calls with permission checks and parallel read-only execution."""
        from cyberclaw.agent.permissions import READ_ONLY_TOOLS

        results: list[str | None] = [None] * len(tool_calls)

        parallel_indices = []
        sequential_indices = []
        for i, tc in enumerate(tool_calls):
            decision = self.permission_gate.check(tc.name, tc.arguments)
            if decision.result == PermissionResult.DENY:
                results[i] = f"Permission denied: {decision.reason}"
                continue
            if decision.result == PermissionResult.ASK:
                approved = await self.permission_gate.request_approval(
                    tc.name,
                    tc.arguments,
                    description=f"{tc.name}({json.dumps(tc.arguments, ensure_ascii=False)[:100]})",
                )
                if not approved:
                    results[i] = "Tool call rejected by user."
                    continue

            if tc.name in READ_ONLY_TOOLS:
                parallel_indices.append(i)
            else:
                sequential_indices.append(i)

        # Execute read-only tools in parallel
        if parallel_indices:
            async def _run(idx: int) -> tuple[int, str]:
                tc = tool_calls[idx]
                return idx, await self._execute_single_tool(tc.name, tc.arguments)

            parallel_results = await asyncio.gather(
                *[_run(i) for i in parallel_indices],
                return_exceptions=True,
            )
            for item in parallel_results:
                if isinstance(item, Exception):
                    continue
                idx, result = item
                results[idx] = result

        # Execute write/dangerous tools sequentially
        for i in sequential_indices:
            tc = tool_calls[i]
            results[i] = await self._execute_single_tool(tc.name, tc.arguments)

        return [r or "Error: tool execution skipped" for r in results]

    async def _execute_single_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a single tool with hooks and metrics tracking."""
        from cyberclaw.agent.hooks import HookContext

        agent_id = self.agent_id

        args_str = json.dumps(arguments, ensure_ascii=False)
        logger.info("[{}] Tool call: {}({}...)", agent_id, name, args_str[:150])

        # Pre-hooks
        ctx = HookContext(tool_name=name, params=arguments)
        ctx = await self.hooks.run_pre_hooks(ctx)
        if ctx.cancelled:
            return f"Tool call cancelled by hook: {name}"
        if ctx.modified_params:
            arguments = ctx.modified_params

        start_time = time.time()
        success = True
        error_msg = None

        try:
            result = await self.tools.execute(name, arguments)
        except Exception as e:
            success = False
            error_msg = str(e)
            result = f"Tool Execution Error: {e}"

        duration = time.time() - start_time
        self.metrics.record_tool_call(name, success, duration, error_msg)

        # Self-Improving: Track tool call for reflection (P0)
        self._current_task_tool_calls.append({
            "tool_name": name,
            "arguments": arguments,
            "success": success,
            "duration": duration,
            "error": error_msg,
        })

        # Self-Improving: Track for tool optimization (P1)
        if self.tool_optimizer:
            self.tool_optimizer.record_tool_execution(
                tool_name=name,
                success=success,
                duration=duration,
                error=error_msg,
                task_description=self._current_task_description[:100] if self._current_task_description else None,
                category=self._infer_tool_category(name),
            )

        # Self-Improving: Track skill usage (P2)
        if self.skill_analyzer:
            is_skill = name in self._known_skills or name.startswith("skill_")

            if is_skill:
                self.skill_analyzer.track_skill_usage(
                    skill_name=name,
                    success=success,
                    duration=duration,
                    task_description=self._current_task_description[:200] if self._current_task_description else "",
                    error_message=error_msg or "",
                    skill_source=self._known_skills.get(name, "unknown"),
                )

        # Post-hooks
        ctx.result = result
        ctx = await self.hooks.run_post_hooks(ctx)
        if ctx.modified_result:
            result = ctx.modified_result

        return result

    def _infer_tool_category(self, tool_name: str) -> str:
        """Infer tool category for optimization tracking (P1)."""
        name_lower = tool_name.lower()

        if any(x in name_lower for x in ["read_file", "write_file", "edit_file", "list_dir"]):
            return "file_operation"
        elif any(x in name_lower for x in ["web_search", "web_fetch", "grep", "find_files", "find_definitions"]):
            return "search"
        elif any(x in name_lower for x in ["exec", "shell"]):
            return "shell"
        elif any(x in name_lower for x in ["git_"]):
            return "git"
        elif any(x in name_lower for x in ["memory_search"]):
            return "memory"
        elif any(x in name_lower for x in ["diagnostic", "test", "run_diagnostics"]):
            return "test"
        elif any(x in name_lower for x in ["message", "send"]):
            return "communication"
        elif any(x in name_lower for x in ["spawn", "subagent"]):
            return "orchestration"
        elif any(x in name_lower for x in ["plan", "update_plan"]):
            return "planning"
        else:
            return "general"

    def _infer_task_domain(self, task_description: str) -> str:
        """Infer task domain from description for confidence evaluation (P1)."""
        desc_lower = task_description.lower()

        if any(x in desc_lower for x in ["code", "function", "class", "import", "def ", "package"]):
            return "code"
        elif any(x in desc_lower for x in ["file", "read", "write", "create", "delete", "directory"]):
            return "file_operation"
        elif any(x in desc_lower for x in ["calculate", "math", "compute", "formula", "equation"]):
            return "math"
        elif any(x in desc_lower for x in ["search", "find", "lookup", "query"]):
            return "web_search"
        elif any(x in desc_lower for x in ["debug", "error", "fix", "issue", "bug"]):
            return "debugging"
        elif any(x in desc_lower for x in ["test", "verify", "check", "validate"]):
            return "test"
        else:
            return "general"

    def _trim_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tier 1 context trimming: truncate long tool outputs."""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)

        if total_chars <= self.context_window:
            return messages

        logger.info("Context trimming: {} chars exceeds {} limit", total_chars, self.context_window)

        keep_tail = 20
        if len(messages) <= keep_tail + 1:
            return messages

        # Ensure tool results stay with their tool calls
        tail = messages[-keep_tail:]
        tool_call_ids_in_tail = {m.get("tool_call_id") for m in tail if m.get("role") == "tool"}

        split_point = len(messages) - keep_tail
        for i in range(len(messages) - keep_tail - 1, 0, -1):
            msg = messages[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                assistant_tool_ids = {tc.get("id") for tc in msg.get("tool_calls", [])}
                if assistant_tool_ids & tool_call_ids_in_tail:
                    split_point = i
                    break

        trimmed = [messages[0]]
        middle = messages[1:split_point]
        kept_tail = messages[split_point:]

        for msg in middle:
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                if len(content) > 1000:
                    msg = {
                        **msg,
                        "content": content[:1000] + f"... [trimmed, was {len(content)} chars]",
                    }
            elif msg.get("role") == "assistant" and not msg.get("tool_calls"):
                content = str(msg.get("content", ""))
                if len(content) > 500:
                    msg = {
                        **msg,
                        "content": content[:500] + f"... [trimmed, was {len(content)} chars]",
                    }
            trimmed.append(msg)

        trimmed.extend(kept_tail)
        new_chars = sum(len(str(m.get("content", ""))) for m in trimmed)
        logger.info("Context trimmed: {} -> {} chars", total_chars, new_chars)

        return trimmed

    async def _compact_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tier 2 smart compaction: summarize old messages via LLM when context is large."""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        threshold = int(self.context_window * 0.7)

        if total_chars <= threshold:
            return messages
        logger.info("Smart compaction triggered: {} chars > {} threshold", total_chars, threshold)
        if self.on_status:
            try:
                self.on_status("compacting_context")
            except Exception:
                pass
        return await self.compactor.compact(messages, keep_recent=10)

    async def _auto_verify(
        self,
        messages: list[dict[str, Any]],
        executed_tools: list[str],
        last_modified_file: str = "",
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run auto-verification after file modifications."""
        if not self.auto_verify:
            return messages, False

        from cyberclaw.agent.verify import should_verify, get_verify_command

        if not should_verify(executed_tools):
            return messages, False

        verify_cmd = get_verify_command(
            self.workspace, self.auto_verify_command, last_modified_file
        )
        if not verify_cmd:
            return messages, False

        logger.info("Auto-verify: running '{}'", verify_cmd)

        if self.on_tool_call:
            try:
                self.on_tool_call("auto_verify", verify_cmd[:60], "running...")
            except Exception:
                pass

        try:
            result = await self.tools.execute("exec", {"command": verify_cmd})
        except Exception as e:
            result = f"Auto-verify error: {e}"

        result_preview = result[:120] + "..." if len(result) > 120 else result

        if self.on_tool_call:
            try:
                self.on_tool_call("auto_verify", verify_cmd[:60], result_preview)
            except Exception:
                pass

        verify_msg = f"[Auto-verification] `{verify_cmd}`:\n{result}"

        has_errors = any(w in result.lower() for w in ['error:', 'failed', 'traceback', 'exception'])

        if has_errors:
            verify_msg += "\n\n[SYSTEM CRITICAL] The verification FAILED. You MUST use tools to fix these errors before returning a final answer to the user. Do not stop until it passes."

        messages.append({"role": "user", "content": verify_msg})
        logger.info("Auto-verify result: {}", result_preview)

        return messages, has_errors

    async def _generate_task_reflection(
        self,
        task_description: str,
        status: str,
        duration: float,
        tokens_used: int,
    ) -> None:
        """Generate reflection report after task completion (P0 - Self-Improving Agent)."""
        task_id = f"task_{int(time.time())}"
        logger.info("Starting reflection for task {} (status={}, duration={:.2f}s)", task_id, status, duration)

        try:
            report = await self.reflection_engine.generate_reflection(
                task_id=task_id,
                task_description=task_description,
                status=status,
                duration=duration,
                tool_calls=self._current_task_tool_calls,
                tokens_used=tokens_used,
                errors=[tc.get("error", "") for tc in self._current_task_tool_calls if tc.get("error")],
            )

            if report.what_went_well or report.suggested_improvements or report.lessons_learned:
                category = self._categorize_task(task_description, self._current_task_tool_calls)

                logger.debug("Adding experience to repository: category={}", category)
                self.experience_repo.add_experience(
                    task_description=task_description[:200],
                    task_category=category,
                    success=(status == "success"),
                    input_context=task_description[:500],
                    solution_approach=", ".join(set(tc.get("tool_name", "") for tc in self._current_task_tool_calls)),
                    tools_used=list(set(tc.get("tool_name", "") for tc in self._current_task_tool_calls)),
                    outcome_description=report.lessons_learned[0] if report.lessons_learned else status,
                    key_insights=report.lessons_learned[:3],
                    warnings=report.what_went_poorly[:2],
                    is_generalizable=True,
                    applicability_conditions=[],
                    confidence_score=report.confidence_score,
                    tags=[status, category],
                )
                logger.info("Experience stored in repository")

                if self.confidence_evaluator and hasattr(report, 'confidence_score'):
                    self.confidence_evaluator.record_outcome(
                        question=task_description[:200],
                        predicted_score=report.confidence_score,
                        actual_success=(status == "success"),
                        domain=category,
                    )

            logger.info("Reflection completed: status={}, confidence={:.2f}, insights={}", status, report.confidence_score, len(report.lessons_learned))

            # Trigger skill evolution analysis (P2)
            if self.skill_analyzer:
                logger.debug("Triggering skill evolution analysis...")
                try:
                    skill_stats = self.skill_analyzer.analyze_skill_usage(period_days=30)
                    patterns = self.skill_analyzer.detect_usage_patterns()
                    gaps = self.skill_analyzer.identify_gaps()
                    evolution_report = self.skill_analyzer.generate_report(period_days=30)
                    self.skill_analyzer._save_report(evolution_report)

                    logger.info("Skill evolution analysis completed: {} skills analyzed, {} gaps identified", len(skill_stats), len(gaps))

                    if gaps:
                        critical_gaps = [g for g in gaps if g.impact == "high"]
                        if critical_gaps:
                            logger.warning("Found {} critical skill gaps:", len(critical_gaps))
                            for gap in critical_gaps[:3]:
                                logger.warning("  - {}: {}", gap.description, gap.recommendation)

                except Exception as e:
                    logger.error("Skill evolution analysis failed: {}: {}", type(e).__name__, e)
                    import traceback
                    logger.debug("Traceback: {}", traceback.format_exc())

        except asyncio.TimeoutError:
            logger.warning("Reflection timed out for task {}", task_id)
        except Exception as e:
            logger.error("Task reflection failed: {}: {}", type(e).__name__, e)
            import traceback
            logger.debug("Traceback: {}", traceback.format_exc())
        finally:
            self._current_task_tool_calls = []
            self._current_task_description = ""

    def _categorize_task(self, description: str, tool_calls: list[dict]) -> str:
        """Categorize task based on description and tools used."""
        tool_names = set(tc.get("tool_name", "") for tc in tool_calls)

        if any("file" in t for t in tool_names):
            return "file_operation"
        if any("exec" in t or "shell" in t for t in tool_names):
            return "shell_command"
        if any("search" in t or "grep" in t for t in tool_names):
            return "code_search"
        if any("web" in t for t in tool_names):
            return "web_research"
        if any("git" in t for t in tool_names):
            return "version_control"
        if any("test" in t or "diagnostic" in t for t in tool_names):
            return "testing"

        desc_lower = description.lower()
        if "create" in desc_lower or "write" in desc_lower:
            return "creation"
        if "fix" in desc_lower or "bug" in desc_lower or "error" in desc_lower:
            return "debugging"
        if "analyze" in desc_lower or "review" in desc_lower:
            return "analysis"

        return "general"

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            media=media,
        )
        response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""

    async def process_direct_stream(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Process a message with streaming output."""
        session = self.sessions.get_or_create(session_key)

        _frequent = self.skill_analyzer.get_frequently_used_skills() if self.skill_analyzer else None
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=content,
            skill_names=_frequent or None,
            media=media,
            channel=channel,
            chat_id=chat_id,
            plan_context=self.planner.get_progress_context() if hasattr(self, 'planner') else None,
        )
        messages = self._inject_role_prompt(messages)

        iteration = 0
        final_content_parts: list[str] = []
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        is_error_response = False

        while iteration < self.max_iterations:
            iteration += 1
            messages = self._trim_context(messages)
            messages = await self._compact_context(messages)

            if self.on_iteration:
                try:
                    self.on_iteration(iteration, self.max_iterations)
                except Exception:
                    pass

            if self.on_status:
                try:
                    self.on_status("thinking")
                except Exception:
                    pass

            collected_content = ""
            collected_reasoning = ""
            tool_calls_data: dict[int, dict[str, Any]] = {}
            is_final_text = True

            async for chunk in self.provider.stream_chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                frequency_penalty=self.frequency_penalty,
                thinking_budget=self.thinking_budget,
            ):
                await asyncio.sleep(0)

                if chunk.usage:
                    for k in total_usage:
                        total_usage[k] += chunk.usage.get(k, 0)

                if chunk.reasoning_content:
                    collected_reasoning += chunk.reasoning_content
                    if self.on_thinking:
                        try:
                            self.on_thinking(chunk.reasoning_content)
                        except Exception:
                            pass

                if chunk.delta_content:
                    collected_content += chunk.delta_content

                if chunk.finish_reason == "error":
                    is_error_response = True

                if chunk.tool_call_index is not None:
                    is_final_text = False
                    idx = chunk.tool_call_index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {"id": "", "name": "", "args": ""}
                    if chunk.tool_call_id:
                        tool_calls_data[idx]["id"] = chunk.tool_call_id
                    if chunk.tool_call_name:
                        tool_calls_data[idx]["name"] = chunk.tool_call_name
                    if chunk.tool_call_arguments_delta:
                        tool_calls_data[idx]["args"] += chunk.tool_call_arguments_delta

            if is_final_text and not tool_calls_data:
                if collected_content:
                    yield collected_content
                    final_content_parts.append(collected_content)
                break

            if tool_calls_data:
                tool_call_dicts = []
                parsed_calls = []
                truncated_calls = []
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    try:
                        if not tc_data["args"]:
                            logger.warning(
                                "Tool call '{}' (id={}) has empty arguments - possible output token truncation",
                                tc_data['name'], tc_data['id'],
                            )
                            truncated_calls.append(tc_data)
                        args = json.loads(tc_data["args"]) if tc_data["args"] else {}
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Tool call JSON decode error: name={}, error={}, raw_args={}",
                            tc_data['name'], e, (tc_data['args'][:200] if tc_data['args'] else 'EMPTY'),
                        )
                        truncated_calls.append(tc_data)
                        args = {"_raw": tc_data["args"], "_parse_error": str(e)}

                    tool_call_dicts.append(
                        {
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {"name": tc_data["name"], "arguments": tc_data["args"]},
                        }
                    )
                    parsed_calls.append((tc_data["id"], tc_data["name"], args))

                # If ALL tool calls are truncated, ask LLM to retry
                if truncated_calls and len(truncated_calls) == len(parsed_calls):
                    logger.warning(
                        "All {} tool call(s) have empty/invalid arguments. Asking LLM to retry.",
                        len(truncated_calls),
                    )
                    messages = self.context.add_assistant_message(
                        messages,
                        collected_content or None,
                        tool_call_dicts,
                        reasoning_content=collected_reasoning or None,
                    )
                    for tc_data in tool_call_dicts:
                        messages = self.context.add_tool_result(
                            messages,
                            tc_data["id"],
                            tc_data["function"]["name"],
                            "Error: tool call arguments were truncated (output too long). "
                            "Please reduce your output text and call tools one at a time with shorter content.",
                        )
                    continue

                messages = self.context.add_assistant_message(
                    messages,
                    collected_content or None,
                    tool_call_dicts,
                    reasoning_content=collected_reasoning or None,
                )

                from cyberclaw.providers.base import ToolCallRequest

                if self.on_status:
                    try:
                        self.on_status("executing_tools")
                    except Exception:
                        pass

                for tc_id, tc_name, tc_args in parsed_calls:
                    if self.on_tool_start:
                        try:
                            self.on_tool_start(tc_name, tc_args)
                        except Exception:
                            pass

                tc_objects = [
                    ToolCallRequest(id=tc_id, name=tc_name, arguments=tc_args)
                    for tc_id, tc_name, tc_args in parsed_calls
                ]
                tool_results = await self._execute_tools(tc_objects)

                executed_tools_stream = []
                last_modified_file_stream = ""
                for (tc_id, tc_name, tc_args), result in zip(parsed_calls, tool_results):
                    result_preview = result[:120] + "..." if len(result) > 120 else result

                    if self.on_tool_call:
                        try:
                            args_str = json.dumps(tc_args, ensure_ascii=False)
                            self.on_tool_call(tc_name, args_str[:100], result_preview)
                        except Exception:
                            pass

                    messages = self.context.add_tool_result(messages, tc_id, tc_name, result)
                    executed_tools_stream.append(tc_name)
                    if tc_name in ("write_file", "edit_file"):
                        last_modified_file_stream = tc_args.get("path", "")

                messages, _has_errors = await self._auto_verify(
                    messages, executed_tools_stream, last_modified_file_stream
                )

        # Save to session
        final_text = "".join(final_content_parts) if final_content_parts else ""
        session.add_message("user", content)

        # Self-Improving: Confidence Injection (P1)
        confidence_suffix = ""
        if final_text and self.confidence_evaluator and not is_error_response:
            confidence_result = self.confidence_evaluator.evaluate(
                question=content[:500],
                answer=final_text,
                context={
                    "domain": self._infer_task_domain(content),
                    "tool_calls": len(self._current_task_tool_calls),
                },
                tool_results=self._current_task_tool_calls,
            )

            if confidence_result.level in ("low", "medium"):
                confidence_suffix = "\n\n" + self.confidence_evaluator.generate_verification_prompt(confidence_result)

            self.metrics.record_tool_call(
                tool_name="confidence_evaluation",
                success=True,
                duration=0.0,
                error=None,
            )

        if final_text and not is_error_response:
            session.add_message("assistant", final_text + confidence_suffix)
        self.sessions.save(session)

        if total_usage.get("total_tokens", 0) > 0:
            yield f"\n\n[tokens: {total_usage['prompt_tokens']:,} in + {total_usage['completion_tokens']:,} out = {total_usage['total_tokens']:,} total]"

        if confidence_suffix:
            yield confidence_suffix

        if iteration >= self.max_iterations and not final_content_parts:
            yield f"\n\n[WARNING] I have reached the maximum number of steps ({self.max_iterations}). Please ask me to 'continue' to proceed."

    async def _consolidate_memory(self, session, archive_all: bool = False) -> None:
        """Consolidate old messages into MEMORY.md + HISTORY.md."""
        memory = MemoryStore(self.workspace)

        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info(
                "Memory consolidation (archive_all): {} total messages archived",
                len(session.messages),
            )
        else:
            keep_count = self.memory_window // 2
            if len(session.messages) <= keep_count:
                logger.debug(
                    "Session {}: No consolidation needed (messages={}, keep={})",
                    session.key,
                    len(session.messages),
                    keep_count,
                )
                return

            messages_to_process = len(session.messages) - session.last_consolidated
            if messages_to_process <= 0:
                logger.debug(
                    "Session {}: No new messages to consolidate (last_consolidated={}, total={})",
                    session.key,
                    session.last_consolidated,
                    len(session.messages),
                )
                return

            old_messages = session.messages[session.last_consolidated : -keep_count]
            if not old_messages:
                return
            logger.info(
                "Memory consolidation started: {} total, {} new to consolidate, {} keep",
                len(session.messages),
                len(old_messages),
                keep_count,
            )

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(
                f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}"
            )
        conversation = "\n".join(lines)
        current_memory = memory.read_long_term()

        prompt = f"""You are a memory consolidation agent. Process this conversation and return a JSON object with exactly two keys:

1. "history_entry": A paragraph (2-5 sentences) summarizing the key events/decisions/topics. Start with a timestamp like [YYYY-MM-DD HH:MM]. Include enough detail to be useful when found by grep search later.

2. "memory_update": The updated long-term memory content. Add any new facts: user location, preferences, personal info, habits, project context, technical decisions, tools/services used. If nothing new, return the existing content unchanged.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{conversation}

**IMPORTANT**: Both values MUST be strings, not objects or arrays.

Example:
{{
  "history_entry": "[2026-02-14 22:50] User asked about...",
  "memory_update": "- Host: HARRYBOOK-T14P\\n- Name: Nado"
}}

Respond with ONLY valid JSON, no markdown fences."""

        try:
            response = await self.provider.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a memory consolidation agent. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
            )
            text = (response.content or "").strip()
            if not text:
                logger.warning("Memory consolidation: LLM returned empty response, skipping")
                return
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json_repair.loads(text)
            if not isinstance(result, dict):
                logger.warning(
                    "Memory consolidation: unexpected response type, skipping. Response: {}",
                    text[:200],
                )
                return

            if entry := result.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                memory.append_history(entry)
            if update := result.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    memory.write_long_term(update)

            if archive_all:
                session.last_consolidated = 0
            else:
                old_len = len(session.messages)
                session.messages = session.messages[-keep_count:]
                session.last_consolidated = 0
                logger.info(
                    "Memory consolidation done: pruned {} -> {} messages",
                    old_len,
                    len(session.messages),
                )
        except Exception as e:
            logger.error("Memory consolidation failed: {}", e)

    # ==========================================================================
    # A2A Mailbox Polling (integrated into main loop)
    # ==========================================================================

    async def _poll_a2a_mailbox(self) -> None:
        """Poll A2A mailbox for incoming messages and process them."""
        if not self.a2a_router:
            return

        mailbox = self.a2a_router.get_mailbox(self.agent_id)
        if not mailbox or mailbox.queue.empty():
            return

        try:
            a2a_msg = await mailbox.queue.get(timeout=0.05)
        except (asyncio.TimeoutError, RuntimeError):
            return

        logger.info(
            "[{}] Received A2A {} from {}",
            self.agent_id,
            a2a_msg.type.value,
            a2a_msg.from_agent,
        )

        content = a2a_msg.content
        if a2a_msg.type == MessageType.REQUEST:
            content = (
                f"[A2A Request from {a2a_msg.from_agent} "
                f"(id={a2a_msg.message_id})]\n{content}"
            )

        inbound = InboundMessage(
            channel="a2a",
            chat_id=a2a_msg.from_agent,
            content=content,
            sender_id=a2a_msg.from_agent,
            metadata={
                "a2a_message_id": a2a_msg.message_id,
                "a2a_type": a2a_msg.type.value,
                "a2a_from": a2a_msg.from_agent,
                "a2a_request_id": a2a_msg.request_id,
            },
        )

        # Use a unique session key per A2A request to avoid history
        # contamination across different tasks. Include the message_id so
        # each top-level orchestrator request gets a fresh conversation.
        a2a_session_key = f"a2a:{a2a_msg.from_agent}:{a2a_msg.message_id}"
        response = await self._process_message(inbound, session_key=a2a_session_key)

        if a2a_msg.type == MessageType.REQUEST:
            # Always send a response for A2A requests to avoid blocking the
            # orchestrator's asyncio.gather() indefinitely.
            response_content = response.content if response else "Task completed (no explicit response)."
            try:
                await self.a2a_router.send_response(
                    from_agent=self.agent_id,
                    to_agent=a2a_msg.from_agent,
                    request_id=a2a_msg.message_id,
                    content=response_content,
                )
            except Exception as e:
                logger.error(
                    "Failed to send A2A response to {}: {}",
                    a2a_msg.from_agent,
                    e,
                )

    # ==========================================================================
    # A2A (Agent-to-Agent) Communication Methods
    # ==========================================================================

    async def send_request(
        self,
        to_agent: str,
        content: str,
        timeout: int = 300,
        priority: str = "normal",
    ) -> AgentMessage:
        """Send request to another agent and wait for response."""
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")

        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }

        return await self.a2a_router.send_request(
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            timeout=timeout,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )

    async def send_response(
        self,
        request_id: str,
        to_agent: str,
        content: str,
        priority: str = "normal",
    ) -> bool:
        """Send response to a request."""
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")

        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }

        return await self.a2a_router.send_response(
            from_agent=self.agent_id,
            to_agent=to_agent,
            request_id=request_id,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )

    async def send_notification(
        self,
        to_agent: str,
        content: str,
        priority: str = "normal",
    ) -> bool:
        """Send notification to another agent (no response expected)."""
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")

        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }

        return await self.a2a_router.send_notification(
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
        )

    async def broadcast(
        self,
        content: str,
        priority: str = "normal",
        exclude: list[str] | None = None,
    ) -> int:
        """Broadcast message to all agents."""
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")

        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT,
        }

        return await self.a2a_router.broadcast(
            from_agent=self.agent_id,
            content=content,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
            exclude=exclude,
        )

    async def receive_message(
        self,
        timeout: float | None = None,
    ) -> AgentMessage:
        """Receive next message from mailbox."""
        if not self.a2a_router:
            raise ValueError("A2A router not initialized")

        return await self.a2a_router.get_message(
            agent_id=self.agent_id,
            timeout=timeout,
        )

    # ==========================================================================
    # AnnounceChain Methods (for Orchestrator pattern)
    # ==========================================================================

    async def wait_for_workers(
        self,
        timeout: float = 600,
        poll_interval: float = 1.0,
    ) -> dict | None:
        """Wait for all spawned workers to complete and aggregate results."""
        current_session_key = f"{self.agent_id}:current"

        logger.info(
            "Orchestrator waiting for workers (timeout: {}s)...",
            timeout,
        )

        result = await self.announce_chain.wait_for_children(
            parent_session_key=current_session_key,
            timeout=timeout,
            poll_interval=poll_interval,
        )

        if result:
            logger.info(
                "All {} workers completed, aggregating results...",
                len(result.children),
            )
            return {
                "success": True,
                "worker_count": len(result.children),
                "results": [child.to_dict() for child in result.children],
                "summary": result.get_summary(),
            }
        else:
            logger.warning("Timeout waiting for workers")
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "worker_count": 0,
                "results": [],
            }

    def get_worker_results(self) -> list:
        """Get results from completed workers."""
        current_session_key = f"{self.agent_id}:current"
        aggregation = self.announce_chain.get_aggregation(current_session_key)

        if aggregation:
            return [child.to_dict() for child in aggregation.children]
        return []
