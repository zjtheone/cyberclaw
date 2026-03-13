"""Tests for prompt construction."""

from __future__ import annotations

from pathlib import Path

from cyberclaw.agent.context import ContextBuilder


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    return workspace


def test_system_prompt_contains_identity(tmp_path) -> None:
    """System prompt should contain core identity."""
    workspace = _make_workspace(tmp_path)
    builder = ContextBuilder(workspace)

    prompt = builder.build_system_prompt()

    assert "cyberclaw" in prompt
    assert "Current Time" in prompt


def test_build_messages_includes_system_and_user(tmp_path) -> None:
    """build_messages should include system prompt and user message."""
    workspace = _make_workspace(tmp_path)
    builder = ContextBuilder(workspace)

    messages = builder.build_messages(
        history=[],
        current_message="Return exactly: OK",
        channel="cli",
        chat_id="direct",
    )

    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert "Return exactly: OK" in messages[-1]["content"]
