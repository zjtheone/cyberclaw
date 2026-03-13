"""Announce Chain management for hierarchical result aggregation.

This module implements:
- Parent-child session relationship tracking
- Result aggregation across spawn tree
- Announce message formatting
- Cascade stop mechanism
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from enum import Enum

from loguru import logger

from cyberclaw.session.keys import SessionKey, extract_agent_id


class AnnounceType(Enum):
    """Type of announce event."""

    COMPLETION = "completion"
    ERROR = "error"
    TIMEOUT = "timeout"
    PROGRESS = "progress"
    CANCELLED = "cancelled"


@dataclass
class AnnounceEvent:
    """Represents an announce event in the chain."""

    event_id: str
    event_type: AnnounceType
    task_id: str
    task_label: str
    task_description: str
    result: str
    status: str  # "ok", "error", "timeout", "cancelled"
    depth: int
    session_key: str
    parent_session_key: str | None
    runtime_seconds: float
    token_usage: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "task_label": self.task_label,
            "task_description": self.task_description,
            "result": self.result,
            "status": self.status,
            "depth": self.depth,
            "session_key": self.session_key,
            "parent_session_key": self.parent_session_key,
            "runtime_seconds": self.runtime_seconds,
            "token_usage": self.token_usage,
            "created_at": self.created_at.isoformat(),
            **self.metadata,
        }


@dataclass
class AggregatedResult:
    """Aggregated result from multiple child announces."""

    parent_session_key: str
    children: list[AnnounceEvent] = field(default_factory=list)
    synthesized_result: str = ""
    synthesis_complete: bool = False

    def add_child(self, event: AnnounceEvent) -> None:
        """Add a child announce event."""
        self.children.append(event)

    def get_summary(self) -> str:
        """Get a summary of all child results."""
        if not self.children:
            return "No child results"

        lines = [
            f"Aggregated results from {len(self.children)} child(ren):",
            "",
        ]

        for i, child in enumerate(self.children, 1):
            status_icon = "✅" if child.status == "ok" else "❌"
            preview = child.result[:200] + "..." if len(child.result) > 200 else child.result
            lines.append(f"{i}. {status_icon} [{child.task_label}] ({child.status})")
            lines.append(f"   {preview}")
            lines.append("")

        if self.synthesized_result:
            lines.append("Synthesis:")
            lines.append(self.synthesized_result)

        return "\n".join(lines)


class AnnounceChainManager:
    """Manages announce chains for hierarchical result aggregation.

    Features:
    - Track parent-child relationships
    - Aggregate results from children
    - Format announce messages
    - Handle cascade stop
    """

    def __init__(self):
        self._events: dict[str, AnnounceEvent] = {}  # event_id -> event
        self._aggregations: dict[str, AggregatedResult] = {}  # parent_session -> aggregation
        self._session_children: dict[str, list[str]] = {}  # parent_session -> [event_ids]

    def register_announce(self, event: AnnounceEvent) -> None:
        """
        Register an announce event.

        Args:
            event: Announce event to register
        """
        self._events[event.event_id] = event

        # Track parent-child relationship
        if event.parent_session_key:
            if event.parent_session_key not in self._session_children:
                self._session_children[event.parent_session_key] = []
            self._session_children[event.parent_session_key].append(event.event_id)

            # Add to aggregation
            if event.parent_session_key not in self._aggregations:
                self._aggregations[event.parent_session_key] = AggregatedResult(
                    parent_session_key=event.parent_session_key
                )
            self._aggregations[event.parent_session_key].add_child(event)

        logger.debug(
            "Registered announce event {} at depth {} from {}",
            event.event_id,
            event.depth,
            event.session_key,
        )

    def get_aggregation(self, session_key: str) -> AggregatedResult | None:
        """
        Get aggregated result for a session.

        Args:
            session_key: Session key

        Returns:
            AggregatedResult or None if no aggregation exists
        """
        return self._aggregations.get(session_key)

    def get_child_events(self, session_key: str) -> list[AnnounceEvent]:
        """
        Get all child announce events for a session.

        Args:
            session_key: Parent session key

        Returns:
            List of child AnnounceEvent objects
        """
        event_ids = self._session_children.get(session_key, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def format_announce_message(self, event: AnnounceEvent, include_stats: bool = True) -> str:
        """
        Format an announce event into a message.

        Args:
            event: Announce event
            include_stats: Whether to include runtime/token stats

        Returns:
            Formatted message string
        """
        status_text = (
            "completed successfully" if event.status == "ok" else f"failed ({event.status})"
        )
        depth_info = f" (depth {event.depth})" if event.depth > 1 else ""

        lines = [
            f"[Subagent '{event.task_label}'{depth_info} {status_text}]",
            "",
            f"Task: {event.task_description}",
            "",
            "Result:",
            event.result,
        ]

        if include_stats:
            lines.append("")
            lines.append(f"Runtime: {event.runtime_seconds:.1f}s")
            if event.token_usage:
                total = sum(event.token_usage.values())
                lines.append(
                    f"Tokens: {total:,} (input: {event.token_usage.get('input', 0):,}, output: {event.token_usage.get('output', 0):,})"
                )

        lines.append("")
        lines.append("Summarize this naturally for the user. Keep it brief.")

        return "\n".join(lines)

    def format_aggregation_message(
        self,
        aggregation: AggregatedResult,
        include_details: bool = True,
    ) -> str:
        """
        Format an aggregation into a message.

        Args:
            aggregation: Aggregated result
            include_details: Whether to include detailed child results

        Returns:
            Formatted message string
        """
        if not aggregation.children:
            return "[No child results to aggregate]"

        lines = [
            f"[Orchestrator: Aggregating {len(aggregation.children)} child result(s)]",
            "",
        ]

        if include_details:
            lines.append("Child Results:")
            lines.append("")

            for i, child in enumerate(aggregation.children, 1):
                status_icon = "✅" if child.status == "ok" else "❌"
                lines.append(f"{i}. {status_icon} **{child.task_label}** ({child.status})")
                lines.append(f"   {child.result[:150]}...")
                lines.append("")

        if aggregation.synthesized_result:
            lines.append("Synthesis:")
            lines.append(aggregation.synthesized_result)
        else:
            lines.append("Review the child results above and provide a comprehensive summary.")

        return "\n".join(lines)

    def cascade_stop(self, session_key: str) -> list[str]:
        """
        Get all descendant sessions that should be stopped.

        Args:
            session_key: Session key to stop

        Returns:
            List of descendant session keys to stop
        """
        descendants = []
        self._collect_descendants(session_key, descendants)
        return descendants

    def _collect_descendants(self, session_key: str, result: list[str], depth: int = 0) -> None:
        """Recursively collect descendant sessions."""
        if depth > 10:  # Safety limit
            logger.warning("Stopped collecting descendants at depth 10 to prevent infinite loop")
            return

        event_ids = self._session_children.get(session_key, [])
        for event_id in event_ids:
            event = self._events.get(event_id)
            if event:
                result.append(event.session_key)
                # Recursively collect children
                self._collect_descendants(event.session_key, result, depth + 1)

    def get_spawn_tree(self, root_session_key: str) -> dict[str, Any]:
        """
        Get the spawn tree structure from a root session.

        Args:
            root_session_key: Root session key

        Returns:
            Tree structure as nested dictionary
        """
        return self._build_tree_node(root_session_key)

    def _build_tree_node(self, session_key: str) -> dict[str, Any]:
        """Build a tree node recursively."""
        node = {
            "session_key": session_key,
            "agent_id": extract_agent_id(session_key),
            "children": [],
        }

        event_ids = self._session_children.get(session_key, [])
        for event_id in event_ids:
            event = self._events.get(event_id)
            if event:
                child_node = {
                    "session_key": event.session_key,
                    "agent_id": extract_agent_id(event.session_key),
                    "task_id": event.task_id,
                    "task_label": event.task_label,
                    "status": event.status,
                    "children": [],
                }
                node["children"].append(child_node)

        return node

    def clear(self) -> None:
        """Clear all tracked events and aggregations."""
        self._events.clear()
        self._aggregations.clear()
        self._session_children.clear()
        logger.debug("Cleared announce chain manager")
    
    async def wait_for_children(
        self,
        parent_session_key: str,
        timeout: float = 300,
        poll_interval: float = 1.0,
    ) -> AggregatedResult | None:
        """等待指定 parent session 的所有子任务完成。
        
        轮询检查子任务完成情况，直到所有子任务完成或超时。
        
        Args:
            parent_session_key: 父 session key
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
        
        Returns:
            AggregatedResult 如果完成，None 如果超时
        """
        import asyncio
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查是否有聚合结果
            aggregation = self._aggregations.get(parent_session_key)
            
            if aggregation and aggregation.children:
                # 所有已注册的孩子都已完成（announce 是同步触发的）
                return aggregation
            
            # 等待下一次轮询
            await asyncio.sleep(poll_interval)
        
        # 超时
        logger.warning(
            f"Timeout waiting for children of {parent_session_key} after {timeout}s"
        )
        return None
    
    def get_children_count(self, parent_session_key: str) -> int:
        """获取指定 parent 的子任务数量。"""
        event_ids = self._session_children.get(parent_session_key, [])
        return len(event_ids)
    
    def has_children(self, parent_session_key: str) -> bool:
        """检查指定 parent 是否有子任务。"""
        return self.get_children_count(parent_session_key) > 0

def create_announce_event(
    task_id: str,
    task_label: str,
    task_description: str,
    result: str,
    status: str,
    depth: int,
    session_key: str,
    parent_session_key: str | None,
    runtime_seconds: float,
    token_usage: dict[str, int] | None = None,
    event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AnnounceEvent:
    """
    Convenience function to create an announce event.

    Args:
        task_id: Task identifier
        task_label: Display label
        task_description: Task description
        result: Result message
        status: Status string
        depth: Spawn depth
        session_key: Session key
        parent_session_key: Parent session key
        runtime_seconds: Runtime in seconds
        token_usage: Token usage dict
        event_id: Optional event ID (auto-generated if not provided)
        metadata: Optional metadata

    Returns:
        AnnounceEvent
    """
    import uuid

    return AnnounceEvent(
        event_id=event_id or str(uuid.uuid4()),
        event_type=AnnounceType.COMPLETION if status == "ok" else AnnounceType.ERROR,
        task_id=task_id,
        task_label=task_label,
        task_description=task_description,
        result=result,
        status=status,
        depth=depth,
        session_key=session_key,
        parent_session_key=parent_session_key,
        runtime_seconds=runtime_seconds,
        token_usage=token_usage or {},
        metadata=metadata or {},
    )
