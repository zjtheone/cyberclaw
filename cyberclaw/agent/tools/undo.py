"""Undo tool: exposes checkpoint rollback to the LLM."""

from typing import Any

from cyberclaw.agent.checkpoint import CheckpointManager
from cyberclaw.agent.tools.base import Tool


class UndoTool(Tool):
    """Tool to undo file changes made during this session."""

    def __init__(self, checkpoint: CheckpointManager):
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "undo"

    @property
    def description(self) -> str:
        return (
            "Undo file changes made during this session. "
            "With a path, rolls back that file to its state before the last edit. "
            "With path='*', rolls back ALL modified files. "
            "Use list_changes to see what files have been modified."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to undo, or '*' to undo all changes",
                },
                "checkpoint_id": {
                    "type": "string",
                    "description": "Optional specific checkpoint ID to restore",
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, checkpoint_id: str | None = None, **kwargs: Any) -> str:
        if path == "*":
            count = self._checkpoint.rollback_all()
            if count == 0:
                return "No changes to undo."
            return f"Rolled back {count} file(s) to their original state."

        from pathlib import Path as P

        target = P(path).expanduser().resolve()
        ok = self._checkpoint.rollback(target, checkpoint_id)
        if ok:
            return f"Successfully rolled back {path}"
        return f"No checkpoint found for {path}. Use list_changes to see modified files."


class ListChangesTool(Tool):
    """Tool to list all file changes made during this session."""

    def __init__(self, checkpoint: CheckpointManager):
        self._checkpoint = checkpoint

    @property
    def name(self) -> str:
        return "list_changes"

    @property
    def description(self) -> str:
        return "List all files modified during this session, with checkpoint IDs for undo."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        changes = self._checkpoint.list_changes()
        if not changes:
            return "No files have been modified in this session."

        lines = [f"Modified files ({len(changes)}):"]
        for c in changes:
            lines.append(f"  {c.path}  (checkpoint: {c.checkpoint_id})")
        return "\n".join(lines)
