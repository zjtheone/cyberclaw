"""File watcher for memory indexing."""

import asyncio
import time
from pathlib import Path
from typing import Callable, Dict, List, Set, Optional
from loguru import logger


class FileWatcher:
    """Simple polling file watcher for memory files."""
    
    def __init__(
        self,
        watch_paths: List[str],
        workspace: Path,
        callback: Callable[[Path], None],
        poll_interval: float = 5.0,
    ):
        self.watch_paths = watch_paths
        self.workspace = workspace
        self.callback = callback
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._file_mtimes: Dict[Path, float] = {}
    
    def _collect_files(self) -> Set[Path]:
        """Collect all files matching watch paths."""
        files = set()
        for pattern in self.watch_paths:
            # Resolve relative to workspace
            if pattern.startswith("/"):
                base = Path(pattern)
            else:
                base = self.workspace / pattern
            # If pattern is a directory, add all *.md files recursively
            if base.is_dir():
                for md_file in base.rglob("*.md"):
                    files.add(md_file)
            else:
                # Treat as glob pattern
                for match in base.parent.glob(base.name):
                    if match.is_file() and match.suffix == ".md":
                        files.add(match)
        return files
    
    async def _poll(self):
        """Poll files for changes."""
        while self._running:
            try:
                files = self._collect_files()
                for file_path in files:
                    try:
                        mtime = file_path.stat().st_mtime
                    except OSError:
                        continue
                    old_mtime = self._file_mtimes.get(file_path)
                    if old_mtime is None:
                        # New file, trigger callback for initial indexing?
                        # We'll treat as modified so it gets indexed
                        self._file_mtimes[file_path] = mtime
                        logger.debug(f"New file detected: {file_path}")
                        self.callback(file_path)
                    elif mtime > old_mtime:
                        logger.info(f"File modified: {file_path}")
                        self._file_mtimes[file_path] = mtime
                        self.callback(file_path)
                # Remove files that no longer exist
                for file_path in list(self._file_mtimes.keys()):
                    if file_path not in files:
                        del self._file_mtimes[file_path]
            except Exception as e:
                logger.error(f"Error while polling files: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def start(self):
        """Start the file watcher."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll())
        logger.info(f"File watcher started for {len(self.watch_paths)} paths")
    
    def stop(self):
        """Stop the file watcher."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("File watcher stopped")