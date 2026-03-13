"""Tests for A2A communication and team collaboration."""

import pytest
import asyncio

from cyberclaw.agent.a2a.router import A2ARouter
from cyberclaw.agent.a2a.types import MessageType


@pytest.mark.asyncio
async def test_a2a_request_response():
    """Test request-response between two agents via A2A router."""
    router = A2ARouter()

    router.register_agent("agent_a", None)
    router.register_agent("agent_b", None)

    async def agent_b_listener():
        msg = await router.get_message("agent_b", timeout=5)
        assert msg.type == MessageType.REQUEST
        assert msg.from_agent == "agent_a"
        await router.send_response(
            from_agent="agent_b",
            to_agent="agent_a",
            request_id=msg.message_id,
            content=f"Got it: {msg.content}",
        )

    listener_task = asyncio.create_task(agent_b_listener())

    response = await router.send_request(
        from_agent="agent_a",
        to_agent="agent_b",
        content="Hello from A",
        timeout=5,
    )

    assert response.content == "Got it: Hello from A"
    assert response.from_agent == "agent_b"

    await listener_task
    await router.close()


@pytest.mark.asyncio
async def test_a2a_broadcast():
    """Test broadcasting a message to all agents."""
    router = A2ARouter()
    router.register_agent("sender", None)
    router.register_agent("worker1", None)
    router.register_agent("worker2", None)

    count = await router.broadcast(
        from_agent="sender",
        content="Do this task",
    )

    assert count == 2  # worker1 + worker2 (sender excluded)

    msg1 = await router.get_message("worker1", timeout=1)
    msg2 = await router.get_message("worker2", timeout=1)
    assert msg1.content == "Do this task"
    assert msg2.content == "Do this task"

    await router.close()


@pytest.mark.asyncio
async def test_a2a_unregistered_agent_raises():
    """Sending to an unregistered agent should raise ValueError."""
    router = A2ARouter()
    router.register_agent("agent_a", None)

    with pytest.raises(ValueError, match="not found"):
        await router.send_request(
            from_agent="agent_a",
            to_agent="nonexistent",
            content="hello",
            timeout=1,
        )

    await router.close()


@pytest.mark.asyncio
async def test_a2a_request_timeout():
    """Request with no listener should timeout."""
    router = A2ARouter()
    router.register_agent("agent_a", None)
    router.register_agent("agent_b", None)

    with pytest.raises(asyncio.TimeoutError):
        await router.send_request(
            from_agent="agent_a",
            to_agent="agent_b",
            content="hello",
            timeout=1,
        )

    await router.close()


@pytest.mark.asyncio
async def test_team_task_tool_parallel():
    """Test TeamTaskTool parallel strategy with mock agents."""
    from unittest.mock import MagicMock
    from cyberclaw.agent.tools.team_task import TeamTaskTool
    from cyberclaw.config.schema import TeamConfig

    router = A2ARouter()
    router.register_agent("orchestrator", None)
    router.register_agent("coder", None)
    router.register_agent("reviewer", None)

    mock_loop = MagicMock()
    mock_loop.agent_id = "orchestrator"
    mock_loop.a2a_router = router
    mock_loop._agents_config = MagicMock()

    team_config = TeamConfig(
        name="dev-team",
        members=["coder", "reviewer"],
        strategy="parallel",
    )
    mock_loop._agents_config.get_team.return_value = team_config
    mock_loop._agents_config.teams = [team_config]
    mock_loop._agents_config.has_agent.return_value = True

    tool = TeamTaskTool(mock_loop)

    async def auto_reply(agent_id, reply_content):
        msg = await router.get_message(agent_id, timeout=5)
        await router.send_response(
            from_agent=agent_id,
            to_agent=msg.from_agent,
            request_id=msg.message_id,
            content=reply_content,
        )

    coder_task = asyncio.create_task(auto_reply("coder", "Code done!"))
    reviewer_task = asyncio.create_task(auto_reply("reviewer", "Review done!"))

    result = await tool.execute(team="dev-team", task="Build feature X")

    assert result["success"] is True
    assert result["strategy"] == "parallel"
    assert len(result["results"]) == 2

    results_by_agent = {r["agent"]: r for r in result["results"]}
    assert results_by_agent["coder"]["result"] == "Code done!"
    assert results_by_agent["reviewer"]["result"] == "Review done!"

    await coder_task
    await reviewer_task
    await router.close()


@pytest.mark.asyncio
async def test_team_task_tool_sequential():
    """Test TeamTaskTool sequential strategy."""
    from unittest.mock import MagicMock
    from cyberclaw.agent.tools.team_task import TeamTaskTool
    from cyberclaw.config.schema import TeamConfig

    router = A2ARouter()
    router.register_agent("orchestrator", None)
    router.register_agent("writer", None)
    router.register_agent("editor", None)

    mock_loop = MagicMock()
    mock_loop.agent_id = "orchestrator"
    mock_loop.a2a_router = router
    mock_loop._agents_config = MagicMock()

    team_config = TeamConfig(
        name="writing-team",
        members=["writer", "editor"],
        strategy="sequential",
    )
    mock_loop._agents_config.get_team.return_value = team_config
    mock_loop._agents_config.teams = [team_config]
    mock_loop._agents_config.has_agent.return_value = True

    tool = TeamTaskTool(mock_loop)

    # Sequential: writer runs first, then editor
    async def auto_reply(agent_id, reply_content):
        msg = await router.get_message(agent_id, timeout=5)
        await router.send_response(
            from_agent=agent_id,
            to_agent=msg.from_agent,
            request_id=msg.message_id,
            content=reply_content,
        )

    writer_task = asyncio.create_task(auto_reply("writer", "Draft written"))
    editor_task = asyncio.create_task(auto_reply("editor", "Draft polished"))

    result = await tool.execute(team="writing-team", task="Write an article")

    assert result["success"] is True
    assert result["strategy"] == "sequential"
    assert len(result["results"]) == 2
    assert result["results"][0]["agent"] == "writer"
    assert result["results"][1]["agent"] == "editor"

    await writer_task
    await editor_task
    await router.close()


@pytest.mark.asyncio
async def test_team_task_tool_missing_member():
    """TeamTaskTool should fail if members are not registered in A2A."""
    from unittest.mock import MagicMock
    from cyberclaw.agent.tools.team_task import TeamTaskTool
    from cyberclaw.config.schema import TeamConfig

    router = A2ARouter()
    router.register_agent("orchestrator", None)
    # Note: "ghost" is NOT registered

    mock_loop = MagicMock()
    mock_loop.agent_id = "orchestrator"
    mock_loop.a2a_router = router
    mock_loop._agents_config = MagicMock()

    team_config = TeamConfig(
        name="broken-team",
        members=["ghost"],
        strategy="parallel",
    )
    mock_loop._agents_config.get_team.return_value = team_config
    mock_loop._agents_config.teams = [team_config]
    mock_loop._agents_config.has_agent.return_value = True

    tool = TeamTaskTool(mock_loop)
    result = await tool.execute(team="broken-team", task="Do something")

    assert result["success"] is False
    assert "not registered" in result["error"]

    await router.close()


@pytest.mark.asyncio
async def test_a2a_multiple_concurrent_requests():
    """Test multiple concurrent request-response pairs."""
    router = A2ARouter()
    router.register_agent("client", None)
    router.register_agent("server1", None)
    router.register_agent("server2", None)
    router.register_agent("server3", None)

    async def auto_reply(agent_id):
        msg = await router.get_message(agent_id, timeout=5)
        await router.send_response(
            from_agent=agent_id,
            to_agent=msg.from_agent,
            request_id=msg.message_id,
            content=f"Reply from {agent_id}",
        )

    # Start all listeners
    listeners = [
        asyncio.create_task(auto_reply(sid))
        for sid in ["server1", "server2", "server3"]
    ]

    # Send concurrent requests
    responses = await asyncio.gather(
        router.send_request(from_agent="client", to_agent="server1", content="req1", timeout=5),
        router.send_request(from_agent="client", to_agent="server2", content="req2", timeout=5),
        router.send_request(from_agent="client", to_agent="server3", content="req3", timeout=5),
    )

    assert len(responses) == 3
    contents = {r.content for r in responses}
    assert contents == {"Reply from server1", "Reply from server2", "Reply from server3"}

    await asyncio.gather(*listeners)
    await router.close()
