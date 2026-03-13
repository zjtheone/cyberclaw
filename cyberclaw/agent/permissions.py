"""Permission gate for tool execution approval."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger


class PermissionMode(str, Enum):
    """Permission checking modes."""
    AUTO = "auto"                    # Auto-approve reads, confirm writes
    CONFIRM_WRITES = "confirm_writes"  # Confirm all write operations
    CONFIRM_ALL = "confirm_all"      # Confirm every tool call
    YOLO = "yolo"                    # Auto-approve everything


class PermissionResult(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionDecision:
    result: PermissionResult
    reason: str = ""


# Tools that are always safe (read-only)
READ_ONLY_TOOLS = frozenset({
    "read_file", "list_dir", "grep", "find_files",
    "git_status", "git_log", "git_diff",
    "web_search", "web_fetch",
    "list_changes", "get_metrics",
    "read_file_map", "read_file_focused",
    "go_to_definition", "find_references", "hover",
    "find_definitions", "find_references_semantic",
    "run_diagnostics",
    "create_implementation_plan",
})

# Tools that modify state and need approval in non-yolo modes
WRITE_TOOLS = frozenset({
    "write_file", "edit_file", "undo", "batch_edit",
    "git_commit", "git_checkout",
})

# Tools that are potentially dangerous
DANGEROUS_TOOLS = frozenset({
    "exec", "shell", "spawn",
})


class PermissionGate:
    """
    Controls which tool calls require user approval.

    Modes:
    - auto: Read-only tools auto-approved, writes auto-approved within workspace,
            dangerous tools require approval
    - confirm_writes: All write operations require approval
    - confirm_all: Every tool call requires approval
    - yolo: Everything auto-approved (for trusted environments)
    """

    def __init__(
        self,
        mode: PermissionMode | str = PermissionMode.AUTO,
        workspace: str | None = None,
        approval_callback: Any = None,
    ):
        self.mode = PermissionMode(mode) if isinstance(mode, str) else mode
        self.workspace = workspace
        self._approval_callback = approval_callback
        # Session-level overrides (user said "always allow X")
        self._session_allows: set[str] = set()

    def check(self, tool_name: str, params: dict[str, Any]) -> PermissionDecision:
        """
        Check if a tool call should be allowed.

        Returns a PermissionDecision with result and reason.
        """
        if self.mode == PermissionMode.YOLO:
            return PermissionDecision(PermissionResult.ALLOW)

        if tool_name in self._session_allows:
            return PermissionDecision(PermissionResult.ALLOW, "session override")

        if self.mode == PermissionMode.CONFIRM_ALL:
            return PermissionDecision(PermissionResult.ASK, f"confirm_all mode")

        # Read-only tools are always safe
        if tool_name in READ_ONLY_TOOLS:
            return PermissionDecision(PermissionResult.ALLOW, "read-only")

        if self.mode == PermissionMode.CONFIRM_WRITES:
            if tool_name in WRITE_TOOLS or tool_name in DANGEROUS_TOOLS:
                return PermissionDecision(PermissionResult.ASK, "write operation")
            return PermissionDecision(PermissionResult.ALLOW)

        # AUTO mode
        if tool_name in WRITE_TOOLS:
            # Auto-approve writes within workspace
            path = params.get("path", "")
            if self.workspace and path and self._is_within_workspace(path):
                return PermissionDecision(PermissionResult.ALLOW, "within workspace")
            if tool_name == "undo":
                return PermissionDecision(PermissionResult.ALLOW, "undo is safe")
            return PermissionDecision(PermissionResult.ASK, "write outside workspace")

        if tool_name in DANGEROUS_TOOLS:
            return PermissionDecision(PermissionResult.ASK, "potentially dangerous")

        # Unknown tools — allow by default in auto mode
        return PermissionDecision(PermissionResult.ALLOW, "unknown tool, auto mode")

    def allow_for_session(self, tool_name: str) -> None:
        """Mark a tool as always-allowed for this session."""
        self._session_allows.add(tool_name)
        logger.info(f"Permission: '{tool_name}' allowed for session")

    async def request_approval(
        self, tool_name: str, params: dict[str, Any], description: str = ""
    ) -> bool:
        """
        Request user approval for a tool call.

        Uses the approval_callback if set, otherwise auto-approves.
        """
        if self._approval_callback:
            return await self._approval_callback(tool_name, params, description)
        # No callback — auto-approve (channel mode or non-interactive)
        logger.warning(f"No approval callback, auto-approving: {tool_name}")
        return True

    def _is_within_workspace(self, path: str) -> bool:
        """Check if a path is within the workspace directory."""
        if not self.workspace:
            return False
        from pathlib import Path
        try:
            resolved = Path(path).expanduser().resolve()
            workspace = Path(self.workspace).expanduser().resolve()
            return str(resolved).startswith(str(workspace))
        except Exception:
            return False
