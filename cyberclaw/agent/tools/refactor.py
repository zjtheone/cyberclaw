
from typing import Any
from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.code.lsp import LSPManager, apply_workspace_edit

class RefactorRenameTool(Tool):
    """Tool to rename symbols safely using LSP."""
    
    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager
    
    @property
    def name(self) -> str:
        return "refactor_rename"
    
    @property
    def description(self) -> str:
        return "Rename a symbol (variable, function, class) across the entire project safely."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file containing the symbol"
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (1-based)"
                },
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)"
                },
                "new_name": {
                    "type": "string",
                    "description": "New name for the symbol"
                }
            },
            "required": ["file_path", "line", "character", "new_name"]
        }
    
    async def execute(self, file_path: str, line: int, character: int, new_name: str, **kwargs: Any) -> str:
        client = await self.lsp_manager.get_client(file_path)
        if not client:
            return f"No LSP server available for {file_path}"
            
        try:
            # 1. Request Rename
            workspace_edit = await client.rename(file_path, line - 1, character, new_name)
            
            if not workspace_edit:
                return "LSP returned no edits. Rename might not be possible or symbol not found."
                
            # 2. Apply Edits
            # Note: apply_workspace_edit is synchronous for now as it does file I/O
            # We might want to make it async if it does heavy I/O, but for text files it's fine.
            modified = apply_workspace_edit(client.workspace, workspace_edit)
            
            if not modified:
                return "No files were modified."
                
            return f"Successfully renamed symbol to '{new_name}'. Modified files:\n" + "\n".join(modified)
            
        except Exception as e:
            return f"Refactoring Error: {e}"
