"""Hooks system: pre/post tool execution hooks."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from loguru import logger


@dataclass
class HookContext:
    """Context passed to hooks."""
    tool_name: str
    params: dict[str, Any]
    result: str | None = None  # Only set for post-hooks
    cancelled: bool = False
    modified_params: dict[str, Any] | None = None
    modified_result: str | None = None


# Hook function types
PreHook = Callable[[HookContext], Awaitable[HookContext]]
PostHook = Callable[[HookContext], Awaitable[HookContext]]


class HookRegistry:
    """
    Registry for pre/post tool execution hooks.

    Pre-hooks can modify parameters or cancel execution.
    Post-hooks can modify results or trigger side effects.

    Example use cases:
    - Auto-format files after edit
    - Audit log for shell commands
    - Custom write validation
    """

    def __init__(self):
        self._pre_hooks: list[tuple[str | None, PreHook]] = []   # (tool_pattern, hook)
        self._post_hooks: list[tuple[str | None, PostHook]] = []

    def add_pre_hook(self, hook: PreHook, tool_pattern: str | None = None) -> None:
        """
        Register a pre-execution hook.

        Args:
            hook: Async function receiving HookContext, returning modified context.
            tool_pattern: Tool name to match (None = all tools).
        """
        self._pre_hooks.append((tool_pattern, hook))

    def add_post_hook(self, hook: PostHook, tool_pattern: str | None = None) -> None:
        """
        Register a post-execution hook.

        Args:
            hook: Async function receiving HookContext, returning modified context.
            tool_pattern: Tool name to match (None = all tools).
        """
        self._post_hooks.append((tool_pattern, hook))

    async def run_pre_hooks(self, ctx: HookContext) -> HookContext:
        """Run all matching pre-hooks. Returns (possibly modified) context."""
        for pattern, hook in self._pre_hooks:
            if pattern and pattern != ctx.tool_name:
                continue
            try:
                ctx = await hook(ctx)
                if ctx.cancelled:
                    logger.info(f"Hook cancelled tool '{ctx.tool_name}'")
                    break
            except Exception as e:
                logger.error(f"Pre-hook error for '{ctx.tool_name}': {e}")
        return ctx

    async def run_post_hooks(self, ctx: HookContext) -> HookContext:
        """Run all matching post-hooks. Returns (possibly modified) context."""
        for pattern, hook in self._post_hooks:
            if pattern and pattern != ctx.tool_name:
                continue
            try:
                ctx = await hook(ctx)
            except Exception as e:
                logger.error(f"Post-hook error for '{ctx.tool_name}': {e}")
        return ctx

    def _matches(self, pattern: str | None, tool_name: str) -> bool:
        """Check if a pattern matches a tool name."""
        if pattern is None:
            return True
        if "*" in pattern:
            # Simple glob: "git_*" matches "git_status", "git_commit", etc.
            prefix = pattern.rstrip("*")
            return tool_name.startswith(prefix)
        return pattern == tool_name


# Built-in hooks

async def auto_format_hook(ctx: HookContext) -> HookContext:
    """Post-hook: auto-format file after edit/write (if formatter available)."""
    if ctx.tool_name not in ("write_file", "edit_file"):
        return ctx

    path = ctx.params.get("path", "")
    if not path:
        return ctx

    # Detect formatter by extension
    formatters = {
        ".py": "ruff format",
        ".js": "prettier --write",
        ".ts": "prettier --write",
        ".jsx": "prettier --write",
        ".tsx": "prettier --write",
        ".go": "gofmt -w",
        ".rs": "rustfmt",
    }

    from pathlib import Path
    ext = Path(path).suffix
    fmt_cmd = formatters.get(ext)
    if not fmt_cmd:
        return ctx

    try:
        proc = await asyncio.create_subprocess_exec(
            *fmt_cmd.split(), path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.wait(), timeout=10.0)
    except Exception:
        pass  # Formatting is best-effort

    return ctx
