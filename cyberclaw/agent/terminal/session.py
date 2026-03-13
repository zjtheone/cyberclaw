
import asyncio
import os
import pty
import subprocess
import time
import uuid
import re
from pathlib import Path
from loguru import logger

class ShellSession:
    """
    Manages a persistent shell session (bash).
    Allows executing commands in the same context (cwd, env vars).
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.master_fd: int | None = None
        self.process: subprocess.Popen | None = None
        self._buffer = b""

    async def start(self):
        """Start the persistent shell process."""
        if self.process and self.process.poll() is None:
            return

        # Create a PTY
        self.master_fd, slave_fd = pty.openpty()

        # Start shell process connected to PTY
        # bash --noediting prevents readline escape codes
        self.process = subprocess.Popen(
            ["/bin/bash", "--noediting", "--noprofile"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(self.workspace),
            preexec_fn=os.setsid,
            env=os.environ.copy()
        )
        
        os.close(slave_fd) # Close slave in parent
        os.set_blocking(self.master_fd, False)
        
        # Initial read to clear banner
        await asyncio.sleep(0.2)
        self._read_available()
        
        # Disable echo and prompt to simplify output parsing
        # stty -echo: disable echo
        # PS1='': disable prompt
        # TERM=dumb: simple terminal
        init_cmd = b"stty -echo; export PS1=''; export TERM=dumb\n"
        os.write(self.master_fd, init_cmd)
        await asyncio.sleep(0.2)
        # Consume the init command output/echo
        self._read_available()
        
        logger.info(f"Started persistent shell session (pid={self.process.pid})")

    async def execute(self, cmd: str, timeout: float = 30.0) -> str:
        """
        Execute a command and return output.
        Raises TimeoutError if command takes too long.
        """
        if not self.process:
            await self.start()

        # Use a complex delimiter to avoid false positives
        token = str(uuid.uuid4())
        # We echo the return code after the delimiter
        # format: <output>\nDELIMITER:<token>:<exit_code>\n
        # We assume clean output because echo is off
        full_cmd = f"{cmd}\n echo \"DELIMITER:{token}:$?\"\n"
        
        os.write(self.master_fd, full_cmd.encode())
        
        output_buffer = b""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Command timed out after {timeout}s")
            
            chunk = self._read_available()
            if chunk:
                output_buffer += chunk
                decoded = output_buffer.decode("utf-8", errors="replace")
                
                if f"DELIMITER:{token}:" in decoded:
                    # Parse output
                    parts = decoded.split(f"DELIMITER:{token}:")
                    content = parts[0]
                    exit_code_str = parts[1].strip()
                    
                    try:
                        exit_code = int(exit_code_str)
                    except ValueError:
                        # Sometimes trailing characters appear
                        try:
                            exit_code = int(exit_code_str.splitlines()[0])
                        except Exception:
                            exit_code = 1
                    
                    # Clean up:
                    # Content might still contain the echoed "echo DELIMITER..." command if stty -echo failed
                    # But if stty -echo works, content should be pure output + newlines
                    
                    final_output = content.strip()
                    # Remove the executed command itself if it appears (unlikely with stty -echo, but just in case)
                    if final_output.startswith(cmd.strip()):
                        final_output = final_output[len(cmd.strip()):].strip()
                    
                    if exit_code != 0:
                        return f"Output:\n{final_output}\n\nExit Code: {exit_code} (FAILED)"
                    return final_output

            if self.process.poll() is not None:
                raise RuntimeError("Shell process died unexpectedly")
                
            await asyncio.sleep(0.1)

    def _read_available(self) -> bytes:
        """Read available data from master_fd non-blocking."""
        if not self.master_fd:
            return b""
        try:
            return os.read(self.master_fd, 8192)
        except (OSError, BlockingIOError):
            return b""

    def close(self):
        """Terminate the shell session."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        if self.master_fd:
            os.close(self.master_fd)
            
        self.process = None
