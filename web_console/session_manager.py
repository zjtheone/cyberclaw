"""Session management for Web Console."""

import uuid
import json
import time
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Session:
    """Represents a chat session."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "messages": self.messages,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
        )

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to the session."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(message)
        self.last_active = datetime.now()

    def is_expired(self, timeout_hours: int) -> bool:
        """Check if session has expired."""
        timeout = timedelta(hours=timeout_hours)
        return datetime.now() - self.last_active > timeout


class SessionManager:
    """Manages chat sessions."""

    def __init__(self, session_dir: Optional[Path] = None, max_sessions: int = 100, session_timeout_hours: int = 24):
        """Initialize session manager."""
        self.session_dir = session_dir or Path("/tmp/cyberclaw_sessions")
        self.max_sessions = max_sessions
        self.session_timeout_hours = session_timeout_hours
        self.sessions: dict[str, Session] = {}
        self.current_session_id: Optional[str] = None

        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Load existing sessions
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        if not self.session_dir.exists():
            return

        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, "r") as f:
                    data = json.load(f)
                    session = Session.from_dict(data)

                    # Skip expired sessions
                    if not session.is_expired(self.session_timeout_hours):
                        self.sessions[session.session_id] = session
            except Exception as e:
                print(f"Warning: Failed to load session {session_file}: {e}")

        # Cleanup old sessions
        self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        expired = [
            sid for sid, session in self.sessions.items() if session.is_expired(self.session_timeout_hours)
        ]
        for sid in expired:
            self.delete_session(sid)

        # If still over limit, remove oldest sessions
        while len(self.sessions) > self.max_sessions:
            oldest = min(self.sessions.items(), key=lambda x: x[1].last_active)
            self.delete_session(oldest[0])

    def create_session(self, metadata: Optional[dict[str, Any]] = None) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())[:8]
        session = Session(session_id=session_id, metadata=metadata or {})
        self.sessions[session_id] = session
        self.current_session_id = session_id
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session."""
        if self.current_session_id:
            return self.sessions.get(self.current_session_id)
        return None

    def set_current_session(self, session_id: str) -> bool:
        """Set the current active session."""
        if session_id in self.sessions:
            self.current_session_id = session_id
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id not in self.sessions:
            return False

        # Remove from memory
        del self.sessions[session_id]

        # Remove from disk
        session_file = self.session_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()

        # Update current session if needed
        if self.current_session_id == session_id:
            self.current_session_id = None

        return True

    def _save_session(self, session: Session) -> None:
        """Save session to disk."""
        session_file = self.session_dir / f"{session.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def save_all_sessions(self) -> None:
        """Save all sessions to disk."""
        for session in self.sessions.values():
            self._save_session(session)

    def list_sessions(self) -> list[Session]:
        """List all active sessions."""
        return sorted(self.sessions.values(), key=lambda s: s.last_active, reverse=True)

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        now = datetime.now()
        sessions_24h = sum(
            1 for s in self.sessions.values() if now - s.created_at < timedelta(hours=24)
        )
        total_messages = sum(len(s.messages) for s in self.sessions.values())

        return {
            "total_sessions": len(self.sessions),
            "sessions_24h": sessions_24h,
            "total_messages": total_messages,
            "avg_messages_per_session": total_messages / len(self.sessions) if self.sessions else 0,
        }
