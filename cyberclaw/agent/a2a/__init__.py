"""Agent-to-Agent (A2A) direct communication module.

This module provides:
- Direct message passing between agents
- Request-response pattern with timeout
- Priority-based message queuing
- Broadcast and notification support

Usage:
    # Get A2A router from agent
    router = agent.a2a_router
    
    # Send request and wait for response
    response = await router.send_request(
        from_agent="coding",
        to_agent="reviewer",
        content="Please review this code...",
        timeout=300,
    )
    
    # Send notification
    await router.send_notification(
        from_agent="coding",
        to_agent="debugger",
        content="Code is ready for testing",
    )
    
    # Broadcast to all agents
    await router.broadcast(
        from_agent="orchestrator",
        content="System maintenance in 5 minutes",
        priority=MessagePriority.URGENT,
    )
"""

from cyberclaw.agent.a2a.types import (
    AgentMessage,
    A2ARequest,
    MessageType,
    MessagePriority,
)
from cyberclaw.agent.a2a.queue import (
    PriorityMessageQueue,
    AgentMailbox,
)
from cyberclaw.agent.a2a.router import A2ARouter

__all__ = [
    "AgentMessage",
    "A2ARequest",
    "MessageType",
    "MessagePriority",
    "PriorityMessageQueue",
    "AgentMailbox",
    "A2ARouter",
]
