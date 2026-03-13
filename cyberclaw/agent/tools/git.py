"""Git integration tools with structured output."""

import asyncio
import json
from typing import Any

from loguru import logger

from cyberclaw.agent.tools.base import Tool


async def _run_git(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )


class GitStatusTool(Tool):
    """Structured git status output."""

    def __init__(self, workspace: str):
        self._cwd = workspace

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Show git repository status: modified, staged, and untracked files in structured format."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        code, out, err = await _run_git("status", "--porcelain=v1", "-uall", cwd=self._cwd)
        if code != 0:
            return f"Error: {err or out}"

        if not out:
            return "Working tree clean — no changes."

        staged, modified, untracked = [], [], []
        for line in out.splitlines():
            if len(line) < 4:
                continue
            x, y, path = line[0], line[1], line[3:]
            if x in "MADRC":
                staged.append(f"  {x} {path}")
            if y in "MD":
                modified.append(f"  {y} {path}")
            if x == "?" and y == "?":
                untracked.append(f"  {path}")

        parts = []
        # Branch info
        code2, branch, _ = await _run_git("branch", "--show-current", cwd=self._cwd)
        if code2 == 0 and branch:
            parts.append(f"Branch: {branch}")

        if staged:
            parts.append("Staged:\n" + "\n".join(staged))
        if modified:
            parts.append("Modified:\n" + "\n".join(modified))
        if untracked:
            parts.append("Untracked:\n" + "\n".join(untracked))

        return "\n\n".join(parts)


class GitDiffTool(Tool):
    """Show git diff for staged, unstaged, or specific files."""

    def __init__(self, workspace: str):
        self._cwd = workspace

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return (
            "Show git diff. By default shows unstaged changes. "
            "Use staged=true for staged changes. Optionally specify a file path."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional file path to diff",
                },
                "staged": {
                    "type": "boolean",
                    "description": "If true, show staged (cached) changes",
                },
            },
        }

    async def execute(self, path: str = "", staged: bool = False, **kwargs: Any) -> str:
        args = ["diff"]
        if staged:
            args.append("--cached")
        if path:
            args.extend(["--", path])

        code, out, err = await _run_git(*args, cwd=self._cwd)
        if code != 0:
            return f"Error: {err or out}"
        return out or "No differences."


class GitCommitTool(Tool):
    """Commit staged changes with a message."""

    def __init__(self, workspace: str):
        self._cwd = workspace

    @property
    def name(self) -> str:
        return "git_commit"

    @property
    def description(self) -> str:
        return (
            "Commit staged changes to git. Requires a commit message. "
            "Use git_status first to verify what will be committed. "
            "Optionally stage all modified files with add_all=true."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "add_all": {
                    "type": "boolean",
                    "description": "If true, stage all modified/deleted files before committing (git add -A)",
                },
            },
            "required": ["message"],
        }

    async def execute(self, message: str, add_all: bool = False, **kwargs: Any) -> str:
        if add_all:
            code, _, err = await _run_git("add", "-A", cwd=self._cwd)
            if code != 0:
                return f"Error staging files: {err}"

        # Check there's something to commit
        code, out, _ = await _run_git("diff", "--cached", "--stat", cwd=self._cwd)
        if code == 0 and not out:
            return "Nothing staged to commit. Use git_status to check, or set add_all=true."

        code, out, err = await _run_git("commit", "-m", message, cwd=self._cwd)
        if code != 0:
            return f"Commit failed: {err or out}"

        logger.info(f"Git commit: {message[:60]}")
        return out


class GitLogTool(Tool):
    """Show recent git log entries."""

    def __init__(self, workspace: str):
        self._cwd = workspace

    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "Show recent git commits. Returns structured output with hash, author, date, and message."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show (default 10, max 50)",
                },
                "path": {
                    "type": "string",
                    "description": "Optional file path to filter commits",
                },
            },
        }

    async def execute(self, count: int = 10, path: str = "", **kwargs: Any) -> str:
        n = min(max(1, count), 50)
        fmt = "--format=%H|%an|%ai|%s"
        args = ["log", f"-{n}", fmt]
        if path:
            args.extend(["--", path])

        code, out, err = await _run_git(*args, cwd=self._cwd)
        if code != 0:
            return f"Error: {err or out}"

        if not out:
            return "No commits found."

        lines = ["Hash         | Author       | Date                | Message"]
        lines.append("-" * 80)
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                h, author, date, msg = parts
                lines.append(f"{h[:12]} | {author[:12]:<12} | {date[:19]} | {msg}")

        return "\n".join(lines)


class GitCheckoutTool(Tool):
    """Checkout a branch or restore a file."""

    def __init__(self, workspace: str):
        self._cwd = workspace

    @property
    def name(self) -> str:
        return "git_checkout"

    @property
    def description(self) -> str:
        return (
            "Checkout a branch or restore a file from git. "
            "For branches, refuses if there are uncommitted changes that would be lost. "
            "For files, restores the file to its last committed state."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Branch name to switch to, or file path to restore",
                },
                "is_file": {
                    "type": "boolean",
                    "description": "If true, treat target as a file path to restore",
                },
            },
            "required": ["target"],
        }

    async def execute(self, target: str, is_file: bool = False, **kwargs: Any) -> str:
        if is_file:
            code, out, err = await _run_git("checkout", "--", target, cwd=self._cwd)
            if code != 0:
                return f"Error restoring {target}: {err or out}"
            return f"Restored {target} to last committed state."

        # Branch checkout — check for uncommitted changes first
        code, status, _ = await _run_git("status", "--porcelain", cwd=self._cwd)
        if code == 0 and status:
            return (
                f"Refusing to switch branch: you have uncommitted changes.\n"
                f"Commit or stash them first.\n\n{status}"
            )

        code, out, err = await _run_git("checkout", target, cwd=self._cwd)
        if code != 0:
            return f"Error: {err or out}"
        return f"Switched to branch '{target}'"
