
import os
from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.code.folding import FoldingEngine

class ReadFileFocusedTool(Tool):
    """
    Reads a file while collapsing irrelevant code blocks (Focus Mode).
    Save tokens by only expanding the 'focused' parts of the code.
    """

    def __init__(self, workspace: Path, folding_engine: FoldingEngine):
        self.workspace = workspace
        self.folding_engine = folding_engine

    @property
    def name(self) -> str:
        return "read_file_focused"

    @property
    def description(self) -> str:
        return (
            "Read a file with 'smart context'. Irrelevant code is collapsed to skeletons. "
            "Specify 'focus_lines' (e.g. '10-20,35') or 'focus_symbols' (e.g. 'AgentLoop,run')."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to workspace)"
                },
                "focus_lines": {
                    "type": "string",
                    "description": "Comma-separated line numbers or ranges (e.g. '1-10, 25')"
                },
                "focus_symbols": {
                    "type": "string",
                    "description": "Comma-separated symbol names to focus on (e.g. 'MyClass, my_function')"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, focus_lines: str | None = None, focus_symbols: str | None = None, **kwargs: Any) -> str:
        try:
            target_path = (self.workspace / path).resolve()
            
            # Security check
            if not str(target_path).startswith(str(self.workspace.resolve())):
                return f"Error: Access denied. Path must be within {self.workspace}"
            
            if not target_path.exists():
                return f"Error: File not found: {path}"
            
            if not target_path.is_file():
                return f"Error: Not a file: {path}"
                
            # Parse focus lines
            lines_to_focus = set()
            
            if focus_lines:
                try:
                    parts = focus_lines.split(",")
                    for part in parts:
                        part = part.strip()
                        if "-" in part:
                            start, end = map(int, part.split("-"))
                            for i in range(start, end + 1):
                                lines_to_focus.add(i)
                        else:
                            lines_to_focus.add(int(part))
                except ValueError:
                    return "Error: Invalid format for focus_lines. Use '1-10, 25'."

            # Parse focus symbols
            if focus_symbols:
                symbols = [s.strip() for s in focus_symbols.split(",") if s.strip()]
                if symbols:
                    resolved_lines = self.folding_engine.resolve_symbols_to_lines(target_path, symbols)
                    lines_to_focus.update(resolved_lines)
            
            # If no focus provided, behave like read_file (or maybe just skeleton?)
            # Let's default to FULL file if nothing provided, but that defeats purpose?
            # Or assume user wants SKELETON if nothing provided?
            # Let's pass empty list -> FoldingEngine determines (currently full file or skeleton logic).
            # Update: FoldingEngine.fold returns full content if focus_lines is empty.
            # If user calls this tool, they likely want SOME focus.
            # If they pass nothing, maybe they want full file?
            # Let's just pass the set.
            
            final_focus = sorted(list(lines_to_focus)) if lines_to_focus else None
            
            content = self.folding_engine.fold(target_path, focus_lines=final_focus)
            return content

        except Exception as e:
            return f"Error reading file focused: {str(e)}"
