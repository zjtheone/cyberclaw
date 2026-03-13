"""Tests for Ping-Pong Dialog."""

import pytest
import asyncio
from cyberclaw.agent.pingpong_dialog import (
    PingPongDialog,
    DialogTurn,
    DialogResult,
    run_ping_pong_dialog,
    format_ping_pong_summary,
)


class TestDialogTurn:
    """Test DialogTurn class."""
    
    def test_create_turn(self):
        """Test creating a dialog turn."""
        turn = DialogTurn(
            turn_number=1,
            from_session="agent:main:main:1",
            from_agent="main",
            to_session="agent:coding:main:2",
            to_agent="coding",
            message="Hello",
            response="Hi there",
            duration_seconds=2.5,
        )
        
        assert turn.turn_number == 1
        assert turn.from_agent == "main"
        assert turn.to_agent == "coding"
        assert turn.response == "Hi there"


class TestDialogResult:
    """Test DialogResult class."""
    
    def test_create_result(self):
        """Test creating a dialog result."""
        result = DialogResult()
        assert result.turn_count == 0
        assert result.stopped_early is False
    
    def test_turn_count(self):
        """Test turn count property."""
        result = DialogResult()
        result.turns.append(DialogTurn(
            turn_number=1,
            from_session="a",
            from_agent="a",
            to_session="b",
            to_agent="b",
            message="m",
            response="r",
        ))
        result.turns.append(DialogTurn(
            turn_number=2,
            from_session="b",
            from_agent="b",
            to_session="a",
            to_agent="a",
            message="m",
            response="r",
        ))
        
        assert result.turn_count == 2
    
    def test_get_summary(self):
        """Test getting result summary."""
        result = DialogResult()
        
        for i in range(3):
            result.turns.append(DialogTurn(
                turn_number=i+1,
                from_session="a",
                from_agent="main",
                to_session="b",
                to_agent="coding",
                message=f"Message {i}",
                response=f"Response {i}",
                duration_seconds=1.0,
            ))
        
        summary = result.get_summary()
        assert "3 turn(s)" in summary
        assert "main" in summary
        assert "coding" in summary


class TestPingPongDialog:
    """Test PingPongDialog class."""
    
    @pytest.mark.asyncio
    async def test_run_dialog(self):
        """Test running a dialog."""
        async def mock_send(session, message, timeout):
            return f"Response to: {message}"
        
        dialog = PingPongDialog(max_turns=3, timeout_seconds=10)
        
        result = await dialog.run(
            requester_session="agent:main:main:1",
            target_session="agent:coding:main:2",
            initial_message="Hello",
            send_callback=mock_send,
        )
        
        assert result.turn_count == 3
        assert result.stopped_early is False
    
    @pytest.mark.asyncio
    async def test_run_dialog_with_skip(self):
        """Test dialog with early stop."""
        async def mock_send(session, message, timeout):
            if "STOP" in message:
                return "REPLY_SKIP - No need to continue"
            return f"Response to: {message}. STOP"
        
        dialog = PingPongDialog(max_turns=5, timeout_seconds=10)
        
        result = await dialog.run(
            requester_session="agent:main:main:1",
            target_session="agent:coding:main:2",
            initial_message="Hello STOP",
            send_callback=mock_send,
        )
        
        assert result.stopped_early is True
        assert result.stop_reason == "SKIP signal received"
        assert result.turn_count == 1
    
    @pytest.mark.asyncio
    async def test_run_dialog_reaches_max_turns(self):
        """Test dialog reaches max turns."""
        async def mock_send(session, message, timeout):
            return f"Response: {message}"
        
        dialog = PingPongDialog(max_turns=2, timeout_seconds=10)
        
        result = await dialog.run(
            requester_session="agent:main:main:1",
            target_session="agent:coding:main:2",
            initial_message="Hello",
            send_callback=mock_send,
        )
        
        assert result.turn_count == 2
        assert result.stopped_early is False
    
    def test_should_stop(self):
        """Test early stop detection."""
        dialog = PingPongDialog()
        
        assert dialog._should_stop("REPLY_SKIP") is True
        assert dialog._should_stop("[SKIP]") is True
        assert dialog._should_stop("[STOP]") is True
        assert dialog._should_stop("NO_REPLY_NEEDED") is True
        assert dialog._should_stop("Please continue") is False
    
    def test_get_turn_history(self):
        """Test getting turn history."""
        dialog = PingPongDialog()
        dialog._turns.append(DialogTurn(
            turn_number=1,
            from_session="a",
            from_agent="main",
            to_session="b",
            to_agent="coding",
            message="Hello",
            response="Hi",
            duration_seconds=1.5,
        ))
        
        history = dialog.get_turn_history()
        assert len(history) == 1
        assert history[0]["turn"] == 1
        assert history[0]["from_agent"] == "main"
    
    def test_clear(self):
        """Test clearing dialog."""
        dialog = PingPongDialog()
        dialog._turns.append(DialogTurn(
            turn_number=1,
            from_session="a",
            from_agent="main",
            to_session="b",
            to_agent="coding",
            message="m",
            response="r",
        ))
        
        dialog.clear()
        assert len(dialog._turns) == 0


class TestRunPingPongDialog:
    """Test run_ping_pong_dialog convenience function."""
    
    @pytest.mark.asyncio
    async def test_run_convenience(self):
        """Test running dialog with convenience function."""
        async def mock_send(session, message, timeout):
            return f"Response: {message}"
        
        result = await run_ping_pong_dialog(
            requester_session="agent:main:main:1",
            target_session="agent:coding:main:2",
            message="Hello",
            send_callback=mock_send,
            max_turns=2,
            timeout_seconds=10,
        )
        
        assert result.turn_count == 2


class TestFormatSummary:
    """Test format_ping_pong_summary function."""
    
    def test_format_summary(self):
        """Test formatting a summary."""
        result = DialogResult()
        result.total_duration_seconds = 5.5
        
        result.turns.append(DialogTurn(
            turn_number=1,
            from_session="a",
            from_agent="main",
            to_session="b",
            to_agent="coding",
            message="Hello",
            response="Hi there",
            duration_seconds=2.0,
        ))
        
        result.final_response = "Final answer"
        
        summary = format_ping_pong_summary(result)
        
        assert "**Ping-Pong Dialog Summary**" in summary
        assert "**Turns**: 1" in summary
        assert "**Duration**: 5.5s" in summary
        assert "main" in summary
        assert "coding" in summary
        assert "Final answer" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
