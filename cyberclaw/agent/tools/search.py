"""Code search tools: grep and find files."""

import asyncio
import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool


def _resolve_path(path: str, allowed_dir: Path | None = None) -> Path:
    """Resolve path and optionally enforce directory restriction."""
    resolved = Path(path).expanduser().resolve()
    if allowed_dir and not str(resolved).startswith(str(allowed_dir.resolve())):
        raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    return resolved


# Common dirs/files to skip when searching
_IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".tox", "dist", "build", ".eggs",
    ".idea", ".vscode", ".DS_Store",
}


class GrepTool(Tool):
    """Tool to search for text patterns in files (like grep -rn)."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search for a text pattern in files within a directory. "
            "Returns matching lines with file paths and line numbers. "
            "Use this to find code references, function definitions, and usages."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The text or regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path to search in"
                },
                "include": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., '*.go', '*.py')"
                },
                "regex": {
                    "type": "boolean",
                    "description": "If true, treat pattern as a regular expression. Default false."
                },
            },
            "required": ["pattern", "path"],
        }

    async def execute(
        self, pattern: str, path: str, include: str = "", regex: bool = False, **kwargs: Any
    ) -> str:
        try:
            search_path = _resolve_path(path, self._allowed_dir)
            if not search_path.exists():
                return f"Error: Path not found: {path}"

            # Try ripgrep first, fall back to grep, then pure Python
            result = await self._search_with_rg(pattern, search_path, include, regex)
            if result is None:
                result = await self._search_with_grep(pattern, search_path, include, regex)
            if result is None:
                result = self._search_python(pattern, search_path, include, regex)

            return result
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error searching: {str(e)}"

    async def _search_with_rg(
        self, pattern: str, path: Path, include: str, regex: bool
    ) -> str | None:
        """Try searching with ripgrep (rg)."""
        cmd = ["rg", "--no-heading", "-n", "--max-count", "50"]
        if not regex:
            cmd.append("--fixed-strings")
        if include:
            cmd.extend(["--glob", include])
        cmd.extend(["--", pattern, str(path)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode not in (0, 1):  # 1 = no matches
                return None
            output = stdout.decode("utf-8", errors="replace").strip()
            return output if output else "No matches found."
        except (FileNotFoundError, asyncio.TimeoutError):
            return None

    async def _search_with_grep(
        self, pattern: str, path: Path, include: str, regex: bool
    ) -> str | None:
        """Try searching with system grep."""
        cmd = ["grep", "-rn", "--color=never"]
        if not regex:
            cmd.append("-F")
        if include:
            cmd.extend(["--include", include])
        cmd.extend(["--", pattern, str(path)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode not in (0, 1):
                return None
            output = stdout.decode("utf-8", errors="replace").strip()
            lines = output.split("\n")
            if len(lines) > 50:
                lines = lines[:50]
                lines.append(f"... (results truncated, showing first 50 matches)")
            return "\n".join(lines) if output else "No matches found."
        except (FileNotFoundError, asyncio.TimeoutError):
            return None

    def _search_python(
        self, pattern: str, path: Path, include: str, regex: bool
    ) -> str:
        """Pure Python fallback search."""
        matches: list[str] = []
        compiled = re.compile(pattern if regex else re.escape(pattern))

        files = [path] if path.is_file() else self._walk_files(path, include)

        for file_path in files:
            if len(matches) >= 50:
                break
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        rel = file_path.relative_to(path) if path.is_dir() else file_path.name
                        matches.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(matches) >= 50:
                            break
            except (OSError, UnicodeDecodeError):
                continue

        if not matches:
            return "No matches found."
        result = "\n".join(matches)
        if len(matches) == 50:
            result += "\n... (results truncated, showing first 50 matches)"
        return result

    def _walk_files(self, root: Path, include: str) -> list[Path]:
        """Walk directory tree yielding files, skipping common ignored dirs."""
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip ignored directories
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
            for fname in filenames:
                if include and not fnmatch.fnmatch(fname, include):
                    continue
                files.append(Path(dirpath) / fname)
                if len(files) > 5000:  # Safety cap
                    return files
        return files


class FindFilesTool(Tool):
    """Tool to find files by name pattern (like find or fd)."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "find_files"

    @property
    def description(self) -> str:
        return (
            "Find files by name pattern in a directory tree. "
            "Use glob patterns like '*.go', 'test_*.py', or exact names like 'Makefile'. "
            "Returns a list of matching file paths."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match file names (e.g., '*.go', 'Makefile', 'test_*.py')"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in"
                },
            },
            "required": ["pattern", "path"],
        }

    async def execute(self, pattern: str, path: str, **kwargs: Any) -> str:
        try:
            search_path = _resolve_path(path, self._allowed_dir)
            if not search_path.exists():
                return f"Error: Path not found: {path}"
            if not search_path.is_dir():
                return f"Error: Not a directory: {path}"

            matches: list[str] = []
            for dirpath, dirnames, filenames in os.walk(search_path):
                dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
                for fname in filenames:
                    if fnmatch.fnmatch(fname, pattern):
                        full = Path(dirpath) / fname
                        try:
                            rel = full.relative_to(search_path)
                        except ValueError:
                            rel = full
                        matches.append(str(rel))
                        if len(matches) >= 50:
                            break
                if len(matches) >= 50:
                    break

            if not matches:
                return f"No files matching '{pattern}' found in {path}"

            result = "\n".join(sorted(matches))
            if len(matches) == 50:
                result += f"\n... (results truncated, showing first 50 matches)"
            return result
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error finding files: {str(e)}"
