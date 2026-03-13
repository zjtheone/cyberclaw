"""Agent-to-Agent communication flow management.

This module implements:
- Ping-pong dialog between agents
- Multi-turn conversation coordination
- Result aggregation
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger

from cyberclaw.bus.events import InboundMessage
from cyberclaw.bus.queue import MessageBus
from cyberclaw.session.keys import SessionKey, extract_agent_id


@dataclass
class PingPongTurn:
    """Represents a single turn in a ping-pong conversation."""

    turn_number: int
    from_agent: str
    to_agent: str
    message: str
    response: str | None = None


class AgentToAgentFlow:
    """Manages Agent-to-Agent communication flows.

    Features:
    - Ping-pong multi-turn conversations
    - Turn limits enforcement
    - Timeout handling
    - Result aggregation
    """

    def __init__(
        self,
        bus: MessageBus,
        max_turns: int = 5,
        timeout_seconds: int = 30,
    ):
        """
        Initialize the A2A flow manager.

        Args:
            bus: Message bus for communication
            max_turns: Maximum number of ping-pong turns
            timeout_seconds: Timeout per turn
        """
        self.bus = bus
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self._turns: list[PingPongTurn] = []

    async def run_ping_pong(
        self,
        requester_session_key: str,
        target_session_key: str,
        initial_message: str,
        request_callback: Any,
    ) -> str:
        """
        Run a ping-pong conversation between two agents.

        Args:
            requester_session_key: Session that initiated the conversation
            target_session_key: Target session to talk to
            initial_message: Initial message to send
            request_callback: Async callback to send message to target
                              Signature: (session_key, message, timeout) -> response

        Returns:
            Final response from the conversation
        """
        requester_agent = extract_agent_id(requester_session_key)
        target_agent = extract_agent_id(target_session_key)

        logger.info(
            "Starting ping-pong conversation: {} → {} (max {} turns)",
            requester_agent,
            target_agent,
            self.max_turns,
        )

        current_message = initial_message
        current_target = target_session_key
        current_requester = requester_session_key

        for turn in range(1, self.max_turns + 1):
            logger.debug("Ping-pong turn {}/{}", turn, self.max_turns)

            # Send message to target
            try:
                response = await asyncio.wait_for(
                    request_callback(current_target, current_message, self.timeout_seconds),
                    timeout=self.timeout_seconds + 5,  # Extra buffer
                )
            except asyncio.TimeoutError:
                logger.warning("Ping-pong turn {} timed out", turn)
                return f"[Conversation timed out at turn {turn}/{self.max_turns}]"

            # Record the turn
            self._turns.append(
                PingPongTurn(
                    turn_number=turn,
                    from_agent=extract_agent_id(current_requester),
                    to_agent=extract_agent_id(current_target),
                    message=current_message,
                    response=response,
                )
            )

            # Check if target wants to stop (REPLY_SKIP convention)
            if "REPLY_SKIP" in response or "[SKIP]" in response:
                logger.info("Ping-pong stopped at turn {} (SKIP signal)", turn)
                break

            # Swap roles for next turn
            current_message = response
            current_target, current_requester = current_requester, current_target

        # Return final response
        if self._turns:
            final_turn = self._turns[-1]
            return final_turn.response or "[No response]"

        return "[No conversation occurred]"

    def get_turn_history(self) -> list[dict[str, Any]]:
        """Get the history of all turns.

        Returns:
            List of turn dictionaries
        """
        return [
            {
                "turn": turn.turn_number,
                "from": turn.from_agent,
                "to": turn.to_agent,
                "message": turn.message,
                "response": turn.response,
            }
            for turn in self._turns
        ]

    def get_summary(self) -> str:
        """Get a summary of the conversation.

        Returns:
            Summary string
        """
        if not self._turns:
            return "No conversation occurred"

        lines = [
            f"Ping-pong conversation ({len(self._turns)}/{self.max_turns} turns):",
        ]

        for turn in self._turns:
            lines.append(f"  Turn {turn.turn_number}: {turn.from_agent} → {turn.to_agent}")
            if turn.response:
                preview = turn.response[:100] + "..." if len(turn.response) > 100 else turn.response
                lines.append(f"    Response: {preview}")

        return "\n".join(lines)


async def send_message_to_session(
    session_key: str,
    message: str,
    timeout_seconds: int = 30,
    # In a real implementation, this would use the session manager
    # For now, this is a placeholder
) -> str:
    """
    Send a message to a session and get the response.

    This is a placeholder that should be replaced with actual session messaging.

    Args:
        session_key: Target session key
        message: Message to send
        timeout_seconds: Timeout

    Returns:
        Response message
    """
    logger.warning(
        "send_message_to_session called (placeholder) - session: {}, message: {}",
        session_key,
        message[:50],
    )
    # This should be implemented using the actual session/agent system
    # For now, return a placeholder response
    return f"[Placeholder response for: {message[:50]}]"


async def run_a2a_ping_pong(
    requester_session: str,
    target_session: str,
    message: str,
    max_turns: int = 5,
    timeout_seconds: int = 30,
    bus: MessageBus | None = None,
) -> str:
    """
    Convenience function to run a ping-pong conversation.

    Args:
        requester_session: Requester session key
        target_session: Target session key
        message: Initial message
        max_turns: Maximum turns
        timeout_seconds: Timeout per turn
        bus: Optional message bus

    Returns:
        Final response
    """
    flow = AgentToAgentFlow(
        bus=bus or MessageBus(),
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
    )

    return await flow.run_ping_pong(
        requester_session_key=requester_session,
        target_session_key=target_session,
        initial_message=message,
        request_callback=send_message_to_session,
    )
