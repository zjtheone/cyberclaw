"""Session management for conversation history."""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from cyberclaw.config.paths import get_legacy_sessions_dir
from cyberclaw.utils.helpers import ensure_dir, safe_filename
from cyberclaw.session.keys import SessionKey, normalize_session_key, is_legacy_format


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str | SessionKey  # Session key (string or SessionKey object)
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # Number of messages already consolidated to files
    spawn_depth: int = 0  # Agent spawn depth (0=main, 1=subagent, 2=sub-subagent)
    parent_session_key: str | None = None  # Parent session key for nested subagents

    @property
    def session_key(self) -> SessionKey:
        """Get session key as SessionKey object."""
        return normalize_session_key(self.key)

    @property
    def agent_id(self) -> str:
        """Get agent ID from session key."""
        return self.session_key.agent_id

    @property
    def session_type(self) -> str:
        """Get session type."""
        return self.session_key.session_type

    @property
    def is_main_session(self) -> bool:
        """Check if this is a main session."""
        return self.session_key.is_main

    @property
    def is_subagent_session(self) -> bool:
        """Check if this is a subagent session."""
        return self.session_key.is_subagent

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), **kwargs}
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        unconsolidated = self.messages[self.last_consolidated :]
        sliced = unconsolidated[-max_messages:]

        # Drop leading non-user messages to avoid orphaned tool_result blocks
        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}

    def _get_session_path(self, key: str | SessionKey) -> Path:
        """Get the file path for a session."""
        if isinstance(key, SessionKey):
            key_str = str(key)
        else:
            key_str = key
        safe_key = safe_filename(key_str.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        """Legacy global session path (~/.cyberclaw/sessions/)."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(
        self,
        key: str | SessionKey,
        spawn_depth: int = 0,
        parent_session_key: str | None = None,
    ) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (string or SessionKey object).
            spawn_depth: Spawn depth for subagent sessions.
            parent_session_key: Parent session key for nested subagents.

        Returns:
            The session.
        """
        # Normalize key to string for cache lookup
        key_str = str(key) if isinstance(key, SessionKey) else key

        if key_str in self._cache:
            return self._cache[key_str]

        session = self._load(key_str)
        if session is None:
            session = Session(
                key=key,
                spawn_depth=spawn_depth,
                parent_session_key=parent_session_key,
            )
        else:
            # Update spawn_depth and parent if provided
            if spawn_depth > 0:
                session.spawn_depth = spawn_depth
            if parent_session_key:
                session.parent_session_key = parent_session_key

        self._cache[key_str] = session
        return session

    def create(
        self,
        key: str | SessionKey,
        spawn_depth: int = 0,
        parent_session_key: str | None = None,
    ) -> Session:
        """
        Create a new session (overwrites if exists).

        Args:
            key: Session key (string or SessionKey object).
            spawn_depth: Spawn depth for subagent sessions.
            parent_session_key: Parent session key for nested subagents.

        Returns:
            The new session.
        """
        key_str = str(key) if isinstance(key, SessionKey) else key
        session = Session(
            key=key,
            spawn_depth=spawn_depth,
            parent_session_key=parent_session_key,
        )
        self._cache[key_str] = session
        return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)
        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            updated_at = None
            last_consolidated = 0
            spawn_depth = 0
            parent_session_key = None

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                        updated_at = (
                            datetime.fromisoformat(data["updated_at"])
                            if data.get("updated_at")
                            else None
                        )
                        last_consolidated = data.get("last_consolidated", 0)
                        spawn_depth = data.get("spawn_depth", 0)
                        parent_session_key = data.get("parent_session_key")
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
                updated_at=updated_at or created_at or datetime.now(),
                spawn_depth=spawn_depth,
                parent_session_key=parent_session_key,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)

        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": str(session.key) if isinstance(session.key, SessionKey) else session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
                "spawn_depth": session.spawn_depth,
                "parent_session_key": session.parent_session_key,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        key_str = str(session.key) if isinstance(session.key, SessionKey) else session.key
        self._cache[key_str] = session

    def invalidate(self, key: str | SessionKey) -> None:
        """Remove a session from the in-memory cache."""
        key_str = str(key) if isinstance(key, SessionKey) else key
        self._cache.pop(key_str, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            sessions.append(
                                {
                                    "key": key,
                                    "created_at": data.get("created_at"),
                                    "updated_at": data.get("updated_at"),
                                    "path": str(path),
                                    "spawn_depth": data.get("spawn_depth", 0),
                                    "agent_id": self._extract_agent_id(key),
                                }
                            )
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def _extract_agent_id(self, key: str) -> str:
        """Extract agent ID from session key."""
        try:
            session_key = SessionKey.parse(key)
            return session_key.agent_id
        except Exception:
            return "default"

    def get_sessions_by_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """
        Get all sessions for a specific agent.

        Args:
            agent_id: Agent ID to filter by.

        Returns:
            List of session info dicts for the agent.
        """
        all_sessions = self.list_sessions()
        return [s for s in all_sessions if s.get("agent_id") == agent_id]

    def get_child_sessions(self, parent_session_key: str) -> list[Session]:
        """
        Get all child sessions spawned by a parent session.

        Args:
            parent_session_key: Parent session key.

        Returns:
            List of child Session objects.
        """
        children = []
        for session in self._cache.values():
            if session.parent_session_key == parent_session_key:
                children.append(session)
        return children
