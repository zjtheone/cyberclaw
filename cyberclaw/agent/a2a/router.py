"""A2A (Agent-to-Agent) message router."""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from cyberclaw.agent.a2a.types import AgentMessage, MessageType, MessagePriority
from cyberclaw.agent.a2a.queue import AgentMailbox

if TYPE_CHECKING:
    from cyberclaw.agent.loop import AgentLoop


class A2ARouter:
    """Router for direct agent-to-agent communication.
    
    Features:
    - Route messages between agents
    - Track agent mailboxes
    - Support request-response pattern
    - Handle timeouts and retries
    """
    
    def __init__(self):
        """Initialize A2A router."""
        self._mailboxes: dict[str, AgentMailbox] = {}  # agent_id -> mailbox
        self._agents: dict[str, "AgentLoop"] = {}  # agent_id -> AgentLoop
        self._lock = asyncio.Lock()
    
    def register_agent(self, agent_id: str, agent: "AgentLoop") -> None:
        """
        Register an agent with the router.
        
        Args:
            agent_id: Agent identifier
            agent: Agent instance
        """
        self._agents[agent_id] = agent
        self._mailboxes[agent_id] = AgentMailbox(agent_id)
        logger.info("Registered agent {} for A2A communication", agent_id)
    
    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent from the router.
        
        Args:
            agent_id: Agent identifier
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._mailboxes:
            self._mailboxes[agent_id].clear()
            del self._mailboxes[agent_id]
        logger.info("Unregistered agent {} from A2A communication", agent_id)
    
    def get_mailbox(self, agent_id: str) -> AgentMailbox | None:
        """
        Get mailbox for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Agent mailbox or None if not registered
        """
        return self._mailboxes.get(agent_id)
    
    async def send_message(self, msg: AgentMessage) -> bool:
        """
        Send message to target agent.
        
        Args:
            msg: Agent message to send
        
        Returns:
            True if message was delivered, False otherwise
        
        Raises:
            ValueError: If target agent not found
        """
        mailbox = self.get_mailbox(msg.to_agent)
        if not mailbox:
            raise ValueError(f"Target agent '{msg.to_agent}' not found")
        
        await mailbox.send_message(msg)
        logger.info(
            "Delivered {} message from {} to {} (id: {})",
            msg.type.value,
            msg.from_agent,
            msg.to_agent,
            msg.message_id,
        )
        return True
    
    async def send_request(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        timeout: int = 1800,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """
        Send request and wait for response.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Receiver agent ID
            content: Request content
            timeout: Timeout in seconds
            priority: Message priority
        
        Returns:
            Response message
        
        Raises:
            ValueError: If target agent not found
            asyncio.TimeoutError: If request timed out
        """
        mailbox = self.get_mailbox(from_agent)
        if not mailbox:
            raise ValueError(f"Sender agent '{from_agent}' not found")
        
        # Create request message
        request = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            type=MessageType.REQUEST,
            content=content,
            priority=priority,
            timeout=timeout,
        )
        
        # Create future to track response
        response_future = mailbox.create_request_future(request.message_id)
        
        # Send request
        await self.send_message(request)
        logger.info(
            "Sent request from {} to {} (id: {}, timeout: {}s)",
            from_agent,
            to_agent,
            request.message_id,
            timeout,
        )
        
        # Wait for response
        try:
            response = await asyncio.wait_for(
                response_future,
                timeout=timeout
            )
            logger.info(
                "Received response for request {} from {}",
                request.message_id,
                to_agent,
            )
            return response
        except asyncio.TimeoutError:
            # Cancel the request
            mailbox.cancel_request(request.message_id)
            logger.error(
                "Request {} to {} timed out after {}s",
                request.message_id,
                to_agent,
                timeout,
            )
            raise
    
    async def send_response(
        self,
        from_agent: str,
        to_agent: str,
        request_id: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """
        Send response to a request.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Original requester agent ID
            request_id: Original request ID
            content: Response content
            priority: Message priority
        
        Returns:
            True if response was delivered
        """
        response = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            type=MessageType.RESPONSE,
            content=content,
            priority=priority,
            request_id=request_id,
        )
        
        await self.send_message(response)
        logger.info(
            "Sent response to request {} from {} to {}",
            request_id,
            from_agent,
            to_agent,
        )
        return True
    
    async def send_notification(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """
        Send notification (no response expected).
        
        Args:
            from_agent: Sender agent ID
            to_agent: Receiver agent ID
            content: Notification content
            priority: Message priority
        
        Returns:
            True if notification was delivered
        """
        notification = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            type=MessageType.NOTIFICATION,
            content=content,
            priority=priority,
        )
        
        await self.send_message(notification)
        logger.info(
            "Sent notification from {} to {}",
            from_agent,
            to_agent,
        )
        return True
    
    async def broadcast(
        self,
        from_agent: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        exclude: list[str] | None = None,
    ) -> int:
        """
        Broadcast message to all agents.
        
        Args:
            from_agent: Sender agent ID
            content: Broadcast content
            priority: Message priority
            exclude: List of agent IDs to exclude
        
        Returns:
            Number of agents that received the broadcast
        """
        exclude = exclude or []
        count = 0
        
        for agent_id in self._mailboxes.keys():
            if agent_id in exclude or agent_id == from_agent:
                continue
            
            notification = AgentMessage(
                from_agent=from_agent,
                to_agent=agent_id,
                type=MessageType.NOTIFICATION,
                content=content,
                priority=priority,
            )
            
            try:
                await self.send_message(notification)
                count += 1
            except Exception as e:
                logger.error(
                    "Failed to broadcast to agent {}: {}",
                    agent_id,
                    e,
                )
        
        logger.info(
            "Broadcast from {} delivered to {} agents",
            from_agent,
            count,
        )
        return count
    
    async def get_message(
        self,
        agent_id: str,
        timeout: float | None = None,
    ) -> AgentMessage:
        """
        Get next message for an agent.
        
        Args:
            agent_id: Agent identifier
            timeout: Maximum time to wait
        
        Returns:
            Next agent message
        
        Raises:
            ValueError: If agent not found
            asyncio.TimeoutError: If timeout exceeded
        """
        mailbox = self.get_mailbox(agent_id)
        if not mailbox:
            raise ValueError(f"Agent '{agent_id}' not found")
        
        return await mailbox.get_message(timeout=timeout)
    
    async def close(self) -> None:
        """Close router and clear all mailboxes."""
        async with self._lock:
            for agent_id in list(self._mailboxes.keys()):
                self.unregister_agent(agent_id)
            logger.info("A2A router closed")
