
from typing import Any
from pathlib import Path
from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.code.lsp import LSPManager
from loguru import logger


def _graceful_lsp(func):
    """Decorator for graceful LSP degradation when no server is available."""
    async def wrapper(self, file_path: str, line: int, character: int, **kwargs: Any) -> str:
        try:
            client = await self.lsp_manager.get_client(file_path)
        except Exception as e:
            logger.debug(f"LSP unavailable for {file_path}: {e}")
            client = None

        if not client:
            ext = Path(file_path).suffix
            return (
                f"No LSP server available for {ext} files. "
                "Use grep/find_files for code navigation instead, "
                "or install a language server (e.g., pyright for Python, tsserver for TypeScript)."
            )

        return await func(self, file_path, line, character, _client=client, **kwargs)
    return wrapper


class LSPDefinitionTool(Tool):
    """Tool to find symbol definitions using LSP."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "go_to_definition"

    @property
    def description(self) -> str:
        return "Find the definition of a symbol at a specific line/character in a file. Requires a running LSP server."

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
                }
            },
            "required": ["file_path", "line", "character"]
        }

    @_graceful_lsp
    async def execute(self, file_path: str, line: int, character: int, _client=None, **kwargs: Any) -> str:
        try:
            resp = await _client.definition(file_path, line - 1, character)

            if not resp:
                return "No definition found."

            locations = resp if isinstance(resp, list) else [resp]
            results = []

            for loc in locations:
                uri = loc.get("uri") or loc.get("targetUri")
                r = loc.get("range") or loc.get("targetRange")

                if uri and r:
                    path = uri.replace("file://", "")
                    start_line = r["start"]["line"] + 1
                    start_col = r["start"]["character"]
                    results.append(f"{path}:{start_line}:{start_col}")

            if not results:
                return "No definition locations found."

            return "\n".join(results)

        except Exception as e:
            return f"LSP Error: {e}"


class LSPReferencesTool(Tool):
    """Tool to find symbol references using LSP."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return "Find all references/usages of a symbol at a specific line/character. Requires a running LSP server."

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
                }
            },
            "required": ["file_path", "line", "character"]
        }

    @_graceful_lsp
    async def execute(self, file_path: str, line: int, character: int, _client=None, **kwargs: Any) -> str:
        try:
            resp = await _client.references(file_path, line - 1, character)

            if not resp:
                return "No references found."

            results = []
            for loc in resp:
                uri = loc.get("uri")
                r = loc.get("range")
                if uri and r:
                    path = uri.replace("file://", "")
                    start_line = r["start"]["line"] + 1
                    results.append(f"{path}:{start_line}")

            results = list(dict.fromkeys(results))
            return (
                f"Found {len(results)} references:\n"
                + "\n".join(results[:50])
                + ("\n...(truncated)" if len(results) > 50 else "")
            )

        except Exception as e:
            return f"LSP Error: {e}"


class LSPHoverTool(Tool):
    """Tool to get hover information (types, docstrings)."""

    def __init__(self, lsp_manager: LSPManager):
        self.lsp_manager = lsp_manager

    @property
    def name(self) -> str:
        return "get_hover_info"

    @property
    def description(self) -> str:
        return "Get type information and documentation for a symbol. Requires a running LSP server."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file"
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (1-based)"
                },
                "character": {
                    "type": "integer",
                    "description": "Character position (0-based column offset)"
                }
            },
            "required": ["file_path", "line", "character"]
        }

    @_graceful_lsp
    async def execute(self, file_path: str, line: int, character: int, _client=None, **kwargs: Any) -> str:
        try:
            resp = await _client.hover(file_path, line - 1, character)
            if not resp or not resp.get("contents"):
                return "No hover info available."

            contents = resp["contents"]

            if isinstance(contents, dict) and "value" in contents:
                return contents["value"]
            elif isinstance(contents, list):
                return "\n".join([c if isinstance(c, str) else c.get("value", "") for c in contents])
            elif isinstance(contents, str):
                return contents

            return str(contents)

        except Exception as e:
            return f"LSP Error: {e}"
