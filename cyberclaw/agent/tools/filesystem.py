"""File system tools: read, write, edit."""
import re
import difflib
from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool


def _resolve_path(
    path: str, workspace: Path | None = None, allowed_dir: Path | None = None
) -> Path:
    """Resolve path against workspace (if relative) and enforce directory restriction."""
    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()
    if allowed_dir:
        try:
            resolved.relative_to(allowed_dir.resolve())
        except ValueError:
            raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents with line numbers."""

    _MAX_CHARS = 128_000  # ~128 KB — prevents OOM from reading huge files into LLM context

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file with line numbers. "
            "Optionally specify start_line and end_line to read a range. "
            "Large files are truncated to 200 lines — use start_line/end_line to read sections."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional start line number (1-indexed, inclusive)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional end line number (1-indexed, inclusive)"
                },
            },
            "required": ["path"]
        }

    async def execute(self, path: str, start_line: int = 0, end_line: int = 0, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            size = file_path.stat().st_size
            if size > self._MAX_CHARS * 4:  # rough upper bound (UTF-8 chars <= 4 bytes)
                return (
                    f"Error: File too large ({size:,} bytes). "
                    f"Use exec tool with head/tail/grep to read portions."
                )

            content = file_path.read_text(encoding="utf-8")
            all_lines = content.splitlines()
            total = len(all_lines)

            # Apply range if specified
            if start_line > 0 or end_line > 0:
                s = max(1, start_line) if start_line > 0 else 1
                e = min(total, end_line) if end_line > 0 else total
                selected = all_lines[s - 1:e]
                numbered = [f"{s + i:>6}: {line}" for i, line in enumerate(selected)]
                header = f"[{path}] Lines {s}-{e} of {total}\n"
                return header + "\n".join(numbered)

            # Full file with truncation
            max_lines = 200
            if total <= max_lines:
                numbered = [f"{i:>6}: {line}" for i, line in enumerate(all_lines, 1)]
                header = f"[{path}] {total} lines\n"
                return header + "\n".join(numbered)
            else:
                # Show first 200 lines with a note
                numbered = [f"{i:>6}: {line}" for i, line in enumerate(all_lines[:max_lines], 1)]
                header = f"[{path}] {total} lines (showing first {max_lines})\n"
                footer = f"\n... ({total - max_lines} more lines. Use start_line/end_line to read further.)"
                return header + "\n".join(numbered) + footer
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, checkpoint: "CheckpointManager | None" = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to write to"},
                "content": {"type": "string", "description": "The content to write"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Snapshot before writing
            if self._checkpoint:
                self._checkpoint.snapshot(file_path)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {path}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file using Aider-style SEARCH/REPLACE blocks."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None, checkpoint: "CheckpointManager | None" = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a file using Aider-style SEARCH/REPLACE blocks. "
            "You MUST format the 'blocks' parameter exactly like this:\n"
            "<<<<<<< SEARCH\n"
            "exact lines to find from the original file\n"
            "=======\n"
            "new lines to replace them with\n"
            ">>>>>>> REPLACE\n"
            "Include enough context lines in the SEARCH block to uniquely identify the location."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit",
                },
                "blocks": {
                    "type": "string",
                    "description": "The SEARCH/REPLACE block(s)",
                },
            },
            "required": ["path", "blocks"],
        }

    async def execute(self, path: str, blocks: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")
            old_lines = content.splitlines(keepends=True)

            pattern = re.compile(
                r"<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
                re.DOTALL | re.MULTILINE
            )

            matches = pattern.finditer(blocks)
            new_content = content
            applied_count = 0

            for match in matches:
                search = match.group("search")
                replace = match.group("replace")

                # Normalize line endings for the search
                search_normalized = search.replace('\r\n', '\n')
                new_content_normalized = new_content.replace('\r\n', '\n')

                # Try exact match first
                if search_normalized in new_content_normalized:
                    new_content = new_content_normalized.replace(search_normalized, replace.replace('\n', '\n'), 1)
                    applied_count += 1
                    continue

                # Aider-style flexible whitespace match
                def get_indent(s):
                    lines = [l for l in s.splitlines() if l.strip()]
                    return min(len(l) - len(l.lstrip()) for l in lines) if lines else 0

                s_indent = get_indent(search_normalized)
                r_indent = get_indent(replace.replace('\r\n', '\n'))

                # Outdent both to find the "core" match
                s_core_lines = [l[s_indent:] if l.strip() else l for l in search_normalized.splitlines()]
                r_core_lines = [l[r_indent:] if l.strip() else l for l in replace.replace('\r\n', '\n').splitlines()]

                # Search file line by line for the core lines
                file_lines = new_content_normalized.splitlines(keepends=True)
                file_lines_stripped = [l.lstrip() for l in file_lines]
                s_core_stripped = [l.lstrip() for l in s_core_lines]

                part_len = len(s_core_stripped)
                match_found = False

                for i in range(len(file_lines_stripped) - part_len + 1):
                    # Compare non-empty lines, ignoring leading whitespace
                    if [l for l in file_lines_stripped[i : i + part_len] if l.strip()] == [l for l in s_core_stripped if l.strip()]:
                        # Re-indent the replace block to match the original file's indentation
                        original_indent = len(file_lines[i]) - len(file_lines[i].lstrip())

                        # Add original indentation to the core replace lines
                        indented_replace_lines = [(" " * original_indent) + l if l.strip() else "\n" for l in r_core_lines]
                        indented_replace = "".join(l if l.endswith("\n") else l + "\n" for l in indented_replace_lines)

                        # Apply the patch
                        new_content = "".join(file_lines[:i]) + indented_replace + "".join(file_lines[i + part_len:])
                        applied_count += 1
                        match_found = True
                        break

                if not match_found:
                    return f"Error: The following SEARCH block was not found in the file (even with flexible whitespace matching):\n{search_normalized}"

            if applied_count == 0:
                return "Error: No valid SEARCH/REPLACE blocks found in 'blocks' parameter."

            # Snapshot before writing
            if self._checkpoint:
                self._checkpoint.snapshot(file_path)

            file_path.write_text(new_content, encoding="utf-8")

            # Generate unified diff
            new_lines = new_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
            )
            diff_text = "".join(diff)

            if diff_text:
                return f"Successfully applied {applied_count} edit block(s) to {path}\n\n{diff_text}"
            return f"Successfully applied {applied_count} edit block(s) to {path} (no visible diff)"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        """Build a helpful error when old_text is not found."""
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return (
            f"Error: old_text not found in {path}. No similar text found. Verify the file content."
        )


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The directory path to list"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"

            items = []
            for i, item in enumerate(sorted(dir_path.iterdir())):
                if i >= 100:
                    items.append(f"... (total {len(list(dir_path.iterdir()))} items, showing first 100)")
                    break
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if not items:
                return f"Directory {path} is empty"

            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
