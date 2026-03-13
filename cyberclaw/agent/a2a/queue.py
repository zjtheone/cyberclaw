"""Priority message queue for A2A communication."""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from cyberclaw.agent.a2a.types import AgentMessage, MessagePriority, MessageType

if TYPE_CHECKING:
    from collections import deque


class PriorityMessageQueue:
    """Priority-based message queue for A2A communication.
    
    Features:
    - Multiple priority levels (URGENT > HIGH > NORMAL > LOW)
    - Thread-safe async operations
    - Timeout support
    - Message expiration checking
    """
    
    def __init__(self, max_size: int = 0):
        """
        Initialize priority message queue.
        
        Args:
            max_size: Maximum queue size (0 = unlimited)
        """
        self._queues: dict[MessagePriority, asyncio.PriorityQueue] = {
            priority: asyncio.PriorityQueue(maxsize=max_size)
            for priority in MessagePriority
        }
        self._not_empty = asyncio.Condition()
    
    async def put(self, msg: AgentMessage) -> None:
        """
        Put message into queue with priority.
        
        Args:
            msg: Agent message to enqueue
        """
        # Use negative priority so higher priority comes first
        priority_value = -msg.priority.value
        
        async with self._not_empty:
            await self._queues[msg.priority].put((priority_value, msg.created_at, msg))
            logger.debug(
                "Queued {} message from {} to {} (priority: {})",
                msg.type.value,
                msg.from_agent,
                msg.to_agent,
                msg.priority.name,
            )
            self._not_empty.notify()
    
    async def get(self, timeout: float | None = None) -> AgentMessage:
        """
        Get highest priority message from queue.
        
        Args:
            timeout: Maximum time to wait (None = wait forever)
        
        Returns:
            Highest priority agent message
        
        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        async with self._not_empty:
            # Wait until at least one queue has messages
            while self._all_empty():
                try:
                    if timeout is not None:
                        await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
                    else:
                        await self._not_empty.wait()
                except asyncio.TimeoutError:
                    raise
        
        # Get from highest priority queue (URGENT=3, HIGH=2, NORMAL=1, LOW=0)
        # Iterate from highest to lowest priority
        for priority in sorted(MessagePriority, key=lambda p: -p.value):
            if not self._queues[priority].empty():
                _, _, msg = await self._queues[priority].get()
                
                # Check if message is expired
                if msg.is_expired():
                    logger.warning(
                        "Discarding expired message from {} to {}",
                        msg.from_agent,
                        msg.to_agent,
                    )
                    # Try to get next message
                    return await self.get(timeout=timeout)
                
                logger.debug(
                    "Dequeued {} message from {} to {}",
                    msg.type.value,
                    msg.from_agent,
                    msg.to_agent,
                )
                return msg
        
        # Should not reach here, but handle gracefully
        raise RuntimeError("Queue is empty after waiting")
    
    def _all_empty(self) -> bool:
        """Check if all priority queues are empty."""
        return all(queue.empty() for queue in self._queues.values())
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._all_empty()
    
    def qsize(self) -> int:
        """Get total number of messages in all queues."""
        return sum(queue.qsize() for queue in self._queues.values())
    
    async def clear(self) -> None:
        """Clear all messages from all queues."""
        async with self._not_empty:
            for priority in MessagePriority:
                while not self._queues[priority].empty():
                    try:
                        self._queues[priority].get_nowait()
                    except asyncio.QueueEmpty:
                        break
            logger.info("Cleared all A2A message queues")


class AgentMailbox:
    """Personal mailbox for a single agent.
    
    Each agent has its own mailbox to receive messages from other agents.
    """
    
    def __init__(self, agent_id: str, max_size: int = 0):
        """
        Initialize agent mailbox.
        
        Args:
            agent_id: Agent identifier
            max_size: Maximum mailbox size
        """
        self.agent_id = agent_id
        self.queue = PriorityMessageQueue(max_size=max_size)
        self._request_responses: dict[str, asyncio.Future] = {}  # request_id -> Future
    
    async def send_message(self, msg: AgentMessage) -> None:
        """
        Send message to this mailbox.
        
        Args:
            msg: Agent message
        """
        if msg.to_agent != self.agent_id:
            raise ValueError(f"Message to_agent ({msg.to_agent}) doesn't match mailbox agent ({self.agent_id})")
        
        # If this is a response, fulfill the waiting request
        if msg.type == MessageType.RESPONSE and msg.request_id:
            if msg.request_id in self._request_responses:
                future = self._request_responses[msg.request_id]
                if not future.done():
                    future.set_result(msg)
                    del self._request_responses[msg.request_id]
                    logger.debug(
                        "Fulfilled request {} with response",
                        msg.request_id,
                    )
                    return
        
        # Otherwise, queue the message
        await self.queue.put(msg)
    
    def create_request_future(self, request_id: str) -> asyncio.Future:
        """
        Create a future for tracking a request's response.
        
        Args:
            request_id: Request identifier
        
        Returns:
            Future that will be fulfilled when response arrives
        """
        future: asyncio.Future = asyncio.Future()
        self._request_responses[request_id] = future
        return future
    
    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a pending request.
        
        Args:
            request_id: Request identifier
        
        Returns:
            True if request was cancelled, False if not found
        """
        if request_id in self._request_responses:
            future = self._request_responses[request_id]
            if not future.done():
                future.cancel()
            del self._request_responses[request_id]
            logger.debug("Cancelled request {}", request_id)
            return True
        return False
    
    async def get_message(self, timeout: float | None = None) -> AgentMessage:
        """
        Get next message from mailbox.
        
        Args:
            timeout: Maximum time to wait
        
        Returns:
            Next agent message
        """
        return await self.queue.get(timeout=timeout)
    
    def clear(self) -> None:
        """Clear all pending messages and requests."""
        # Cancel all pending requests
        for request_id, future in self._request_responses.items():
            if not future.done():
                future.cancel()
        self._request_responses.clear()
        
        # Clear the queue
        asyncio.create_task(self.queue.clear())
