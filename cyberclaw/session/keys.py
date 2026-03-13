"""Session key format for Agent-to-Agent communication.

This module defines the session key format and parsing logic.

Format: agent:<agent_id>:<session_type>:<session_id>

Examples:
    - agent:main:main:default
    - agent:coding:subagent:abc123
    - agent:research:cron:daily-report
"""

from dataclasses import dataclass
from typing import Literal

SessionType = Literal["main", "subagent", "acp", "cron"]

# Legacy format support
LEGACY_SESSION_PREFIXES = (
    "cli:",
    "telegram:",
    "discord:",
    "whatsapp:",
    "slack:",
    "feishu:",
    "dingtalk:",
)


@dataclass
class SessionKey:
    """Structured session key for A2A communication.

    Attributes:
        agent_id: The agent identifier (e.g., "main", "coding", "research")
        session_type: Type of session ("main", "subagent", "acp", "cron")
        session_id: Unique session identifier
    """

    agent_id: str
    session_type: SessionType
    session_id: str

    def __str__(self) -> str:
        """Convert to string format."""
        return f"agent:{self.agent_id}:{self.session_type}:{self.session_id}"

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SessionKey):
            return NotImplemented
        return str(self) == str(other)

    @property
    def is_main(self) -> bool:
        """Check if this is a main session."""
        return self.session_type == "main"

    @property
    def is_subagent(self) -> bool:
        """Check if this is a subagent session."""
        return self.session_type == "subagent"

    @classmethod
    def parse(cls, key: str) -> "SessionKey":
        """Parse a session key string into a SessionKey object.

        Args:
            key: Session key string (new format or legacy format)

        Returns:
            SessionKey object

        Examples:
            >>> SessionKey.parse("agent:main:subagent:abc123")
            SessionKey(agent_id='main', session_type='subagent', session_id='abc123')

            >>> SessionKey.parse("cli:direct")
            SessionKey(agent_id='default', session_type='main', session_id='cli:direct')
        """
        if not key:
            raise ValueError("Session key cannot be empty")

        # Check for legacy format
        if not key.startswith("agent:"):
            # Legacy format: channel:chat_id
            return cls(
                agent_id="default",
                session_type="main",
                session_id=key,
            )

        # Parse new format: agent:<agent_id>:<session_type>:<session_id>
        parts = key.split(":")
        if len(parts) < 4 or parts[0] != "agent":
            raise ValueError(
                f"Invalid session key format: {key}. "
                f"Expected format: agent:<agent_id>:<session_type>:<session_id>"
            )

        agent_id = parts[1]
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        session_type = parts[2]
        session_id = ":".join(parts[3:])  # Handle session_id with colons

        # Validate session_type
        valid_types = {"main", "subagent", "acp", "cron"}
        if session_type not in valid_types:
            raise ValueError(
                f"Invalid session type: {session_type}. Must be one of: {', '.join(valid_types)}"
            )

        return cls(
            agent_id=agent_id,
            session_type=session_type,  # type: ignore
            session_id=session_id,
        )

    @classmethod
    def create(
        cls,
        agent_id: str,
        session_type: SessionType,
        session_id: str,
    ) -> "SessionKey":
        """Create a new session key.

        Args:
            agent_id: Agent identifier
            session_type: Session type
            session_id: Session identifier

        Returns:
            SessionKey object
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not session_id:
            raise ValueError("session_id cannot be empty")

        return cls(
            agent_id=agent_id,
            session_type=session_type,
            session_id=session_id,
        )

    @classmethod
    def create_main(cls, agent_id: str, session_id: str = "main") -> "SessionKey":
        """Create a main session key.

        Args:
            agent_id: Agent identifier
            session_id: Session identifier (default: "main")

        Returns:
            SessionKey object
        """
        return cls.create(agent_id, "main", session_id)

    @classmethod
    def create_subagent(cls, agent_id: str, subagent_id: str) -> "SessionKey":
        """Create a subagent session key.

        Args:
            agent_id: Agent identifier
            subagent_id: Unique subagent identifier

        Returns:
            SessionKey object
        """
        return cls.create(agent_id, "subagent", subagent_id)


def is_legacy_format(key: str) -> bool:
    """Check if a session key uses the legacy format.

    Args:
        key: Session key string

    Returns:
        True if legacy format, False if new format
    """
    return not key.startswith("agent:")


def normalize_session_key(key: str | SessionKey) -> SessionKey:
    """Normalize a session key to SessionKey object.

    Args:
        key: Session key string or SessionKey object

    Returns:
        SessionKey object
    """
    if isinstance(key, SessionKey):
        return key
    return SessionKey.parse(key)


def extract_agent_id(key: str | SessionKey) -> str:
    """Extract agent ID from a session key.

    Args:
        key: Session key string or SessionKey object

    Returns:
        Agent ID
    """
    if isinstance(key, SessionKey):
        return key.agent_id
    session_key = SessionKey.parse(key)
    return session_key.agent_id


def extract_session_type(key: str | SessionKey) -> SessionType:
    """Extract session type from a session key.

    Args:
        key: Session key string or SessionKey object

    Returns:
        Session type
    """
    if isinstance(key, SessionKey):
        return key.session_type
    session_key = SessionKey.parse(key)
    return session_key.session_type
