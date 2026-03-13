
import asyncio
import subprocess
import uuid
from pathlib import Path
from loguru import logger

class DockerSession:
    """
    Manages a persistent Docker container session.
    Commands are executed via `docker exec`.
    """

    def __init__(self, workspace: Path, image: str = "python:3.12-slim"):
        self.workspace = workspace
        self.image = image
        self.container_id: str | None = None
        self.container_name = f"cyberclaw-sandbox-{uuid.uuid4().hex[:8]}"

    async def start(self):
        """Start the sandbox container."""
        if self.container_id:
            return

        logger.info(f"Starting sandbox container {self.container_name} ({self.image})...")
        
        # Start container detached, mounting workspace
        # tail -f /dev/null keeps it running
        cmd = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "-v", f"{self.workspace}:/workspace",
            "-w", "/workspace",
            self.image,
            "tail", "-f", "/dev/null"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start docker container: {stderr.decode()}")
            
        self.container_id = stdout.decode().strip()
        logger.info(f"Sandbox started: {self.container_id}")

    async def execute(self, cmd: str, timeout: float = 30.0) -> str:
        """
        Execute a command inside the container.
        """
        if not self.container_id:
            await self.start()

        # Wrap command in sh -c to allow redirection/piping?
        # docker exec -i work_dir sh -c "cmd"
        full_cmd = [
            "docker", "exec", 
            "-w", "/workspace",
            self.container_id,
            "sh", "-c", cmd 
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                
                output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
                
                if proc.returncode != 0:
                     return f"Output:\n{output}\n\nExit Code: {proc.returncode} (FAILED)"
                
                return output.strip()
                
            except asyncio.TimeoutError:
                # Kill exec process?
                try:
                    proc.kill()
                except:
                    pass
                raise TimeoutError(f"Command timed out after {timeout}s")
                
        except Exception as e:
            return f"Docker execution error: {e}"

    def close(self):
        """Stop and remove the container."""
        if self.container_id:
            logger.info(f"Stopping sandbox {self.container_name}...")
            subprocess.run(
                ["docker", "rm", "-f", self.container_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.container_id = None
