from pathlib import Path
from typing import Any

from loguru import logger
from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.terminal.session import ShellSession


class ShellTool(Tool):
    """
    Tool to execute commands in a persistent shell session.
    Supports stateful operations like 'cd', 'export', and background processes.
    """

    def __init__(self, session: ShellSession):
        self.session = session

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command within a persistent session. "
            "Use this for valid 'cd' commands, setting environment variables, "
            "or running interactive tools. Context (cwd, env) is preserved."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default 30.0)",
                    "default": 30.0
                }
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: float = 30.0, **kwargs: Any) -> str:
        try:
            return await self.session.execute(command, timeout=timeout)
        except TimeoutError:
            return f"Error: Command timed out after {timeout} seconds."
        except (BrokenPipeError, OSError, ConnectionError) as e:
            # PTY/session died — try to recover
            logger.warning(f"Shell session error, attempting recovery: {e}")
            try:
                await self._recover_session()
                return await self.session.execute(command, timeout=timeout)
            except Exception as e2:
                return f"Error: Shell session unrecoverable: {e2}"
        except Exception as e:
            return f"Error executing shell command: {str(e)}"

    async def _recover_session(self) -> None:
        """Attempt to recover a broken shell session."""
        if hasattr(self.session, "close"):
            try:
                await self.session.close()
            except Exception:
                pass
        if hasattr(self.session, "start"):
            await self.session.start()
            logger.info("Shell session recovered")
