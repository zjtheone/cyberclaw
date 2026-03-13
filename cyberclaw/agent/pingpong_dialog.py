"""Agent-to-Agent ping-pong dialog implementation.

This module implements multi-turn conversations between agents
with automatic turn management and result synthesis.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

from cyberclaw.session.keys import SessionKey, extract_agent_id


@dataclass
class DialogTurn:
    """Represents a single turn in the dialog."""

    turn_number: int
    from_session: str
    from_agent: str
    to_session: str
    to_agent: str
    message: str
    response: str | None = None
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0


@dataclass
class DialogResult:
    """Result of a ping-pong dialog."""

    turns: list[DialogTurn] = field(default_factory=list)
    final_response: str = ""
    stopped_early: bool = False
    stop_reason: str = ""
    total_duration_seconds: float = 0.0

    @property
    def turn_count(self) -> int:
        """Get number of turns."""
        return len(self.turns)

    def get_summary(self) -> str:
        """Get a summary of the dialog."""
        if not self.turns:
            return "No dialog occurred"

        lines = [
            f"Ping-pong dialog completed ({self.turn_count} turn(s))",
            "",
        ]

        for turn in self.turns:
            status = "✅" if turn.response else "❌"
            lines.append(f"{status} Turn {turn.turn_number}: {turn.from_agent} → {turn.to_agent}")
            if turn.response:
                preview = turn.response[:100] + "..." if len(turn.response) > 100 else turn.response
                lines.append(f"   Response: {preview}")

        if self.stopped_early:
            lines.append("")
            lines.append(f"Stopped early: {self.stop_reason}")

        lines.append("")
        lines.append(f"Final response: {self.final_response[:200]}...")

        return "\n".join(lines)


class PingPongDialog:
    """Manages ping-pong dialog between two agents.

    Features:
    - Automatic turn management
    - Timeout handling
    - Early stop detection (REPLY_SKIP)
    - Result aggregation
    """

    def __init__(
        self,
        max_turns: int = 5,
        timeout_seconds: int = 30,
    ):
        """
        Initialize the dialog manager.

        Args:
            max_turns: Maximum number of turns
            timeout_seconds: Timeout per turn
        """
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self._turns: list[DialogTurn] = []

    async def run(
        self,
        requester_session: str,
        target_session: str,
        initial_message: str,
        send_callback: Callable[[str, str, int], Awaitable[str]],
    ) -> DialogResult:
        """
        Run the ping-pong dialog.

        Args:
            requester_session: Session that initiated the dialog
            target_session: Target session to talk to
            initial_message: Initial message to send
            send_callback: Async callback to send message
                          Signature: (session_key, message, timeout) -> response

        Returns:
            DialogResult with all turns and final response
        """
        start_time = time.time()
        result = DialogResult()

        requester_agent = extract_agent_id(requester_session)
        target_agent = extract_agent_id(target_session)

        logger.info(
            "Starting ping-pong dialog: {} → {} (max {} turns, {}s timeout)",
            requester_agent,
            target_agent,
            self.max_turns,
            self.timeout_seconds,
        )

        current_message = initial_message
        current_from_session = requester_session
        current_to_session = target_session

        for turn_num in range(1, self.max_turns + 1):
            turn_start = time.time()

            logger.debug("Dialog turn {}/{}", turn_num, self.max_turns)

            try:
                # Send message and get response
                response = await asyncio.wait_for(
                    send_callback(current_to_session, current_message, self.timeout_seconds),
                    timeout=self.timeout_seconds + 5,  # Extra buffer
                )

                turn_duration = time.time() - turn_start

                # Record the turn
                turn = DialogTurn(
                    turn_number=turn_num,
                    from_session=current_from_session,
                    from_agent=extract_agent_id(current_from_session),
                    to_session=current_to_session,
                    to_agent=extract_agent_id(current_to_session),
                    message=current_message,
                    response=response,
                    duration_seconds=turn_duration,
                )
                self._turns.append(turn)
                result.turns.append(turn)

                # Check for early stop signal
                if self._should_stop(response):
                    result.stopped_early = True
                    result.stop_reason = "SKIP signal received"
                    result.final_response = response
                    logger.info("Dialog stopped early at turn {} (SKIP signal)", turn_num)
                    break

                # Prepare for next turn (swap roles)
                current_message = response
                current_from_session, current_to_session = current_to_session, current_from_session

            except asyncio.TimeoutError:
                logger.warning("Dialog turn {} timed out", turn_num)
                result.stopped_early = True
                result.stop_reason = f"Timeout at turn {turn_num}"
                result.final_response = f"[Dialog timed out at turn {turn_num}/{self.max_turns}]"
                break
            except Exception as e:
                logger.error("Dialog turn {} failed: {}", turn_num, e)
                result.stopped_early = True
                result.stop_reason = f"Error at turn {turn_num}: {str(e)}"
                result.final_response = f"[Dialog failed at turn {turn_num}: {str(e)}]"
                break

        # Set final response if not already set
        if not result.final_response and self._turns:
            result.final_response = self._turns[-1].response or "[No response]"

        result.total_duration_seconds = time.time() - start_time

        logger.info(
            "Dialog completed: {} turn(s), {}s",
            result.turn_count,
            result.total_duration_seconds,
        )

        return result

    def _should_stop(self, response: str) -> bool:
        """
        Check if the dialog should stop early.

        Args:
            response: Response from the other agent

        Returns:
            True if dialog should stop
        """
        stop_signals = [
            "REPLY_SKIP",
            "[SKIP]",
            "[STOP]",
            "NO_REPLY_NEEDED",
        ]

        return any(signal in response.upper() for signal in stop_signals)

    def get_turn_history(self) -> list[dict[str, Any]]:
        """
        Get the history of all turns.

        Returns:
            List of turn dictionaries
        """
        return [
            {
                "turn": turn.turn_number,
                "from_session": turn.from_session,
                "from_agent": turn.from_agent,
                "to_session": turn.to_session,
                "to_agent": turn.to_agent,
                "message": turn.message,
                "response": turn.response,
                "duration": turn.duration_seconds,
            }
            for turn in self._turns
        ]

    def clear(self) -> None:
        """Clear all turns."""
        self._turns.clear()


async def run_ping_pong_dialog(
    requester_session: str,
    target_session: str,
    message: str,
    send_callback: Callable[[str, str, int], Awaitable[str]],
    max_turns: int = 5,
    timeout_seconds: int = 30,
) -> DialogResult:
    """
    Convenience function to run a ping-pong dialog.

    Args:
        requester_session: Requester session key
        target_session: Target session key
        message: Initial message
        send_callback: Async callback to send message
        max_turns: Maximum turns
        timeout_seconds: Timeout per turn

    Returns:
        DialogResult
    """
    dialog = PingPongDialog(
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
    )

    return await dialog.run(
        requester_session=requester_session,
        target_session=target_session,
        initial_message=message,
        send_callback=send_callback,
    )


def format_ping_pong_summary(result: DialogResult) -> str:
    """
    Format a dialog result into a summary message.

    Args:
        result: Dialog result

    Returns:
        Formatted summary string
    """
    lines = [
        f"**Ping-Pong Dialog Summary**",
        f"",
        f"**Turns**: {result.turn_count} / {result.max_turns if hasattr(result, 'max_turns') else '?'}",
        f"**Duration**: {result.total_duration_seconds:.1f}s",
        f"",
    ]

    if result.stopped_early:
        lines.append(f"**Stopped Early**: {result.stop_reason}")
        lines.append("")

    lines.append("**Conversation Flow**:")
    lines.append("")

    for turn in result.turns:
        status_icon = "✅" if turn.response else "❌"
        lines.append(
            f"{status_icon} **Turn {turn.turn_number}**: {turn.from_agent} → {turn.to_agent}"
        )
        if turn.response:
            preview = turn.response[:150] + "..." if len(turn.response) > 150 else turn.response
            lines.append(f"   > {preview}")

    lines.append("")
    lines.append("**Final Response**:")
    lines.append(result.final_response)

    return "\n".join(lines)
