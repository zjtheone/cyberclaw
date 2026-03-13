from pathlib import Path
from typing import Any

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.code.repomap import RepoMap, EXTENSION_TO_LANG


class ReadFileMapTool(Tool):
    """
    Tool to read the symbol map (outline) of a file.
    Useful for understanding a file's structure without reading its full content.
    """
    
    def __init__(self, workspace: Path, repomap: RepoMap):
        self.workspace = workspace
        self.repomap = repomap
        
    @property
    def name(self) -> str:
        return "read_file_map"
    
    @property
    def description(self) -> str:
        return "Read the symbol map (classes, functions) of a file."
        
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to map (relative to workspace)",
                }
            },
            "required": ["path"],
        }
    
    async def execute(self, path: str) -> str:
        try:
            target_path = (self.workspace / path).resolve()
            
            # Security check
            if not str(target_path).startswith(str(self.workspace.resolve())):
                return f"Error: Access denied. Path must be within {self.workspace}"
            
            if not target_path.exists():
                return f"Error: File '{path}' does not exist"
                
            if not target_path.is_file():
                return f"Error: '{path}' is not a file"
            
            ext = target_path.suffix
            if ext not in EXTENSION_TO_LANG:
                return f"Error: Unsupported file type '{ext}'. Supported: {', '.join(EXTENSION_TO_LANG.keys())}"
            
            # Helper to format symbols (similar to RepoMap logic but for single file)
            lang = EXTENSION_TO_LANG[ext]
            symbols = self.repomap._extract_symbols(target_path, lang)
            
            if not symbols:
                return f"No symbols found in {path}"
                
            return f"Map of {path}:\n" + "\n".join(f"- {s}" for s in symbols)
            
        except Exception as e:
            return f"Error generating map: {str(e)}"
