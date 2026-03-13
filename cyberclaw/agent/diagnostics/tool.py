
import asyncio
from pathlib import Path
from typing import Any, List

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.diagnostics.parsers import PytestParser, GoTestParser, Diagnostic

class DiagnosticTool(Tool):
    """
    Runs tests and parses diagnostics (errors/warnings).
    Returns structured output (file, line, error) instead of raw text.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._parsers = {
            "pytest": PytestParser(),
            "go test": GoTestParser(),
        }

    @property
    def name(self) -> str:
        return "run_diagnostics"

    @property
    def description(self) -> str:
        return (
            "Run a test command (e.g. 'pytest tests/foo.py') and return structured diagnostics "
            "(file, line, error) for easy fixing."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Test command to run (e.g. 'pytest tests/test_foo.py' or 'go test ./...')"
                }
            },
            "required": ["command"]
        }

    async def execute(self, command: str, **kwargs: Any) -> str:
        # Determine parser from command
        parser_key = "pytest" if "pytest" in command else "go test" if "go test" in command else None
        
        # Execute command
        try:
            # security: simple checks?
            if ";" in command or "&&" in command or "|" in command:
                 return "Error: Chained commands not supported for diagnostics. Run single test command."
            
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace)
            )
            stdout, stderr = await proc.communicate()
            
            out_str = stdout.decode("utf-8", errors="replace")
            err_str = stderr.decode("utf-8", errors="replace")
            
            # If command succeeded (exit 0), usually no diagnostics needed?
            # Or maybe verify passed?
            if proc.returncode == 0:
                return "Tests passed! No diagnostics found."
            
            # Parse output
            parser = self._parsers.get(parser_key)
            if not parser:
                # Fallback: return raw output if no parser
                return f"Tests failed (exit {proc.returncode}), but no parser for this command.\nOutput:\n{out_str}\n{err_str}"
            
            diagnostics = parser.parse(out_str, err_str)
            
            if not diagnostics:
                 return f"Tests failed (exit {proc.returncode}), but parser found no structured errors.\nRaw Output:\n{out_str}\n{err_str}"
            
            # Format structured output
            lines = [f"Found {len(diagnostics)} diagnostics:"]
            for diag in diagnostics:
                lines.append(f"FAILURE in {diag.file}:{diag.line}")
                lines.append(f"  Message: {diag.message}")
                lines.append("-" * 40)
                
            return "\n".join(lines)

        except Exception as e:
            return f"Error running diagnostics: {str(e)}"
