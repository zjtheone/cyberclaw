"""Agent-to-Agent (A2A) communication types."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class MessageType(Enum):
    """Type of A2A message."""
    
    REQUEST = "request"           # Request (expects response)
    RESPONSE = "response"         # Response to a request
    NOTIFICATION = "notification" # Notification (no response needed)
    BROADCAST = "broadcast"       # Broadcast to all agents


class MessagePriority(Enum):
    """Message priority levels."""
    
    LOW = 0       # Low priority
    NORMAL = 1    # Normal priority
    HIGH = 2      # High priority
    URGENT = 3    # Urgent


@dataclass
class AgentMessage:
    """Message for direct agent-to-agent communication."""
    
    from_agent: str                              # Sender agent ID
    to_agent: str                                # Receiver agent ID
    type: MessageType                            # Message type
    content: str                                 # Message content
    priority: MessagePriority = MessagePriority.NORMAL
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id: str | None = None                # Linked request ID (for responses)
    timeout: int = 300                           # Timeout in seconds
    max_retries: int = 3                         # Max retry attempts
    retry_count: int = 0                         # Current retry count
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.timeout
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "type": self.type.value,
            "content": self.content[:200],  # Truncate for display
            "priority": self.priority.value,
            "request_id": self.request_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class A2ARequest:
    """Represents an A2A request with response tracking."""
    
    request_id: str
    from_agent: str
    to_agent: str
    content: str
    timeout: int
    created_at: datetime = field(default_factory=datetime.now)
    response: AgentMessage | None = None
    completed: bool = False
    error: str | None = None
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.timeout
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def remaining_time(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.timeout - self.elapsed_time)
