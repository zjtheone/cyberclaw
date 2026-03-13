"""File checkpoint system for safe editing with undo support."""

import difflib
import hashlib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class FileChange:
    """Record of a single file modification."""
    path: str
    checkpoint_id: str
    timestamp: float
    backup_path: str
    original_hash: str


class CheckpointManager:
    """
    Manages file snapshots for safe editing with rollback support.

    Before any file modification, call snapshot() to save the original.
    If something goes wrong, rollback() restores the file.
    """

    MAX_CHECKPOINTS_PER_FILE = 3  # Only keep last N checkpoints per file

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._store = workspace / ".cyberclaw" / "checkpoints"
        self._store.mkdir(parents=True, exist_ok=True)
        self._changes: dict[str, list[FileChange]] = {}  # path -> [changes]
        self._cleanup_orphans()

    def snapshot(self, path: Path) -> str:
        """
        Save a snapshot of a file before editing.

        Args:
            path: The file to snapshot.

        Returns:
            A checkpoint_id that can be used for rollback.
        """
        resolved = path.resolve()
        key = str(resolved)

        # Generate checkpoint ID
        ts = time.time()
        raw = f"{key}:{ts}"
        checkpoint_id = hashlib.sha1(raw.encode()).hexdigest()[:12]

        # Copy file to backup location
        backup_path = self._store / f"{checkpoint_id}_{resolved.name}"

        if resolved.exists():
            shutil.copy2(resolved, backup_path)
            original_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()[:16]
        else:
            # File doesn't exist yet (new file) — store empty marker
            backup_path.write_text("")
            original_hash = "new_file"

        change = FileChange(
            path=key,
            checkpoint_id=checkpoint_id,
            timestamp=ts,
            backup_path=str(backup_path),
            original_hash=original_hash,
        )

        changes = self._changes.setdefault(key, [])
        changes.append(change)

        # Evict oldest checkpoints if over limit
        while len(changes) > self.MAX_CHECKPOINTS_PER_FILE:
            old = changes.pop(0)
            bp = Path(old.backup_path)
            if bp.exists():
                bp.unlink()

        logger.debug(f"Checkpoint {checkpoint_id} for {resolved.name}")
        return checkpoint_id

    def rollback(self, path: Path, checkpoint_id: str | None = None) -> bool:
        """
        Rollback a file to a previous checkpoint.

        Args:
            path: The file to rollback.
            checkpoint_id: Specific checkpoint to restore. If None, uses the most recent.

        Returns:
            True if rollback succeeded.
        """
        resolved = path.resolve()
        key = str(resolved)
        changes = self._changes.get(key, [])

        if not changes:
            return False

        if checkpoint_id:
            target = next((c for c in changes if c.checkpoint_id == checkpoint_id), None)
        else:
            target = changes[-1]

        if not target:
            return False

        backup = Path(target.backup_path)
        if not backup.exists():
            return False

        if target.original_hash == "new_file":
            # File was newly created — remove it
            if resolved.exists():
                resolved.unlink()
        else:
            shutil.copy2(backup, resolved)

        # Remove this and all later checkpoints for this file
        idx = changes.index(target)
        removed = changes[idx:]
        self._changes[key] = changes[:idx]

        # Clean up backup files
        for c in removed:
            bp = Path(c.backup_path)
            if bp.exists():
                bp.unlink()

        logger.info(f"Rolled back {resolved.name} to checkpoint {target.checkpoint_id}")
        return True

    def rollback_all(self) -> int:
        """
        Rollback all modified files to their original state.

        Returns:
            Number of files rolled back.
        """
        count = 0
        for key in list(self._changes.keys()):
            changes = self._changes[key]
            if not changes:
                continue
            # Rollback to the first (oldest) checkpoint
            first = changes[0]
            backup = Path(first.backup_path)
            resolved = Path(key)

            if backup.exists():
                if first.original_hash == "new_file":
                    if resolved.exists():
                        resolved.unlink()
                else:
                    shutil.copy2(backup, resolved)
                count += 1

            # Clean up all backups for this file
            for c in changes:
                bp = Path(c.backup_path)
                if bp.exists():
                    bp.unlink()

            self._changes[key] = []

        logger.info(f"Rolled back {count} files")
        return count

    def get_diff(self, path: Path) -> str:
        """
        Get unified diff between the original snapshot and current file content.

        Args:
            path: The file to diff.

        Returns:
            Unified diff string, or empty string if no changes.
        """
        resolved = path.resolve()
        key = str(resolved)
        changes = self._changes.get(key, [])

        if not changes:
            return ""

        # Use the most recent snapshot as "original"
        latest = changes[-1]
        backup = Path(latest.backup_path)

        if not backup.exists():
            return ""

        original = backup.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if resolved.exists():
            current = resolved.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        else:
            current = []

        diff = difflib.unified_diff(
            original, current,
            fromfile=f"a/{resolved.name}",
            tofile=f"b/{resolved.name}",
        )
        return "".join(diff)

    def list_changes(self) -> list[FileChange]:
        """List all file changes in this session."""
        result = []
        for changes in self._changes.values():
            if changes:
                result.append(changes[-1])
        return sorted(result, key=lambda c: c.timestamp)

    def _cleanup_orphans(self) -> None:
        """Remove orphaned checkpoint files left by previous abnormal exits."""
        try:
            count = 0
            for f in self._store.iterdir():
                if f.is_file():
                    f.unlink()
                    count += 1
            if count:
                logger.info(f"Cleaned up {count} orphaned checkpoint files")
        except Exception:
            pass

    def cleanup(self) -> None:
        """Remove all checkpoint backup files."""
        for changes in self._changes.values():
            for c in changes:
                bp = Path(c.backup_path)
                if bp.exists():
                    bp.unlink()
        self._changes.clear()
