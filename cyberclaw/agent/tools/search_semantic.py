
from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.code.symbol_index import SymbolIndex

class FindDefinitionsTool(Tool):
    """
    Finds the definition site(s) of a symbol.
    """
    def __init__(self, workspace: Path, index: SymbolIndex):
        self.workspace = workspace
        self.index = index

    @property
    def name(self) -> str:
        return "find_definitions"

    @property
    def description(self) -> str:
        return "Find the file and approximate line number where a symbol (class, function) is defined."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Name of the symbol to find (e.g. 'AgentLoop', 'run')"
                }
            },
            "required": ["symbol"]
        }

    async def execute(self, symbol: str, **kwargs: Any) -> str:
        locations = self.index.find_definitions(symbol)
        if not locations:
            return f"No definitions found for '{symbol}'."
        
        lines = [f"Definitions for '{symbol}':"]
        for loc in locations:
            # We assume line 0 if unknown, maybe user should read file validation?
            # Or use grep to refine?
            # For now, just show file.
            lines.append(f"- {loc.file} (defined as: {loc.text})")
            
        return "\n".join(lines)


class FindReferencesTool(Tool):
    """
    Finds usage of a symbol across the workspace.
    """
    def __init__(self, workspace: Path, index: SymbolIndex):
        self.workspace = workspace
        self.index = index

    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return "Find references (usages) of a symbol in the codebase."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to search for"
                }
            },
            "required": ["symbol"]
        }

    async def execute(self, symbol: str, **kwargs: Any) -> str:
        try:
            locations = await self.index.find_references(symbol)
            if not locations:
                return f"No references found for '{symbol}'."
            
            # Group by file?
            by_file = {}
            for loc in locations:
                if loc.file not in by_file:
                    by_file[loc.file] = []
                by_file[loc.file].append(loc)
            
            output = [f"References to '{symbol}' ({len(locations)} found):"]
            
            for fpath, locs in by_file.items():
                output.append(f"\nFile: {fpath}")
                for loc in locs:
                    output.append(f"  {loc.line}: {loc.text}")
            
            return "\n".join(output)

        except Exception as e:
            return f"Error finding references: {str(e)}"
