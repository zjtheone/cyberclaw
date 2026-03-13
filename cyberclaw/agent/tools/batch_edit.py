"""Batch edit tool: atomic multi-file editing with rollback."""

import difflib
from pathlib import Path
from typing import Any

from cyberclaw.agent.checkpoint import CheckpointManager
from cyberclaw.agent.tools.base import Tool


class BatchEditTool(Tool):
    """
    Atomic multi-file edit: all edits succeed or all are rolled back.

    Each edit is a {path, old_text, new_text} triple, same as edit_file.
    """

    def __init__(self, checkpoint: CheckpointManager, allowed_dir: Path | None = None):
        self._checkpoint = checkpoint
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "batch_edit"

    @property
    def description(self) -> str:
        return (
            "Edit multiple files atomically. All edits succeed or all are rolled back. "
            "Each edit specifies path, old_text, and new_text (same as edit_file). "
            "Use this when changes span multiple files and must be consistent."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "description": "List of edits to apply atomically",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "old_text": {"type": "string", "description": "Text to find"},
                            "new_text": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old_text", "new_text"],
                    },
                },
            },
            "required": ["edits"],
        }

    async def execute(self, edits: list[dict[str, str]], **kwargs: Any) -> str:
        if not edits:
            return "No edits provided."

        # Phase 1: Validate all edits before applying any
        resolved: list[tuple[Path, str, str, str]] = []  # (path, content, old_text, new_text)
        for i, edit in enumerate(edits):
            path_str = edit.get("path", "")
            old_text = edit.get("old_text", "")
            new_text = edit.get("new_text", "")

            try:
                file_path = Path(path_str).expanduser().resolve()
                if self._allowed_dir:
                    if not str(file_path).startswith(str(self._allowed_dir.resolve())):
                        return f"Error in edit #{i + 1}: {path_str} is outside allowed directory"
            except Exception as e:
                return f"Error in edit #{i + 1}: invalid path: {e}"

            if not file_path.exists():
                return f"Error in edit #{i + 1}: file not found: {path_str}"

            content = file_path.read_text(encoding="utf-8")
            if old_text not in content:
                return f"Error in edit #{i + 1}: old_text not found in {path_str}"

            count = content.count(old_text)
            if count > 1:
                return f"Error in edit #{i + 1}: old_text appears {count} times in {path_str}"

            resolved.append((file_path, content, old_text, new_text))

        # Phase 2: Snapshot all files
        checkpoint_ids: list[tuple[Path, str]] = []
        for file_path, _, _, _ in resolved:
            cid = self._checkpoint.snapshot(file_path)
            checkpoint_ids.append((file_path, cid))

        # Phase 3: Apply all edits
        diffs = []
        try:
            for file_path, content, old_text, new_text in resolved:
                old_lines = content.splitlines(keepends=True)
                new_content = content.replace(old_text, new_text, 1)
                file_path.write_text(new_content, encoding="utf-8")

                new_lines = new_content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{file_path.name}",
                    tofile=f"b/{file_path.name}",
                )
                diffs.append("".join(diff))
        except Exception as e:
            # Rollback all on failure
            for file_path, cid in checkpoint_ids:
                self._checkpoint.rollback(file_path, cid)
            return f"Error during batch edit, all changes rolled back: {e}"

        # Build result
        result = f"Successfully edited {len(edits)} file(s) atomically."
        diff_text = "\n".join(d for d in diffs if d)
        if diff_text:
            result += f"\n\n{diff_text}"
        return result
