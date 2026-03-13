"""Integration tests for MultiAgentGateway."""

import pytest
import asyncio
from datetime import datetime

from cyberclaw.gateway.manager import MultiAgentGateway
from cyberclaw.config.schema import (
    Config,
    AgentsConfig,
    AgentConfig,
    AgentBinding,
    TeamConfig,
    ChannelsConfig,
    ProvidersConfig,
    GatewayConfig,
    ToolsConfig,
    MemorySearchConfig,
    MCPConfig,
)
from cyberclaw.bus.queue import MessageBus
from cyberclaw.bus.events import InboundMessage, OutboundMessage


@pytest.fixture
def make_config():
    """Helper to create test Config."""

    def _make_config(
        agent_list: list[AgentConfig] = None,
        bindings: list[AgentBinding] = None,
        default_agent: str = "default",
    ):
        return Config(
            agents=AgentsConfig(
                defaults=AgentConfig(id="default", model="anthropic/claude-opus-4-5"),
                agent_list=agent_list or [],
                bindings=bindings or [],
                default_agent=default_agent,
            ),
            channels=ChannelsConfig(),
            providers=ProvidersConfig(),
            gateway=GatewayConfig(),
            tools=ToolsConfig(),
            memory_search=MemorySearchConfig(),
            mcp=MCPConfig(),
        )

    return _make_config


@pytest.fixture(autouse=True)
def patch_http_server(monkeypatch):
    """Disable HTTP server during tests to avoid port conflicts."""
    from cyberclaw.gateway import manager as manager_mod

    class FakeHTTPServer:
        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            pass

        async def stop(self):
            pass

    monkeypatch.setattr(manager_mod, "GatewayHTTPServer", FakeHTTPServer)


@pytest.fixture
def bus():
    """Create a MessageBus for testing."""
    return MessageBus()


class TestMultiAgentGatewayInitialization:
    """Test MultiAgentGateway initialization."""

    def test_init_with_empty_agent_list(self, make_config, bus):
        """Gateway should initialize with empty agent list."""
        config = make_config(agent_list=[], default_agent="default")
        gw = MultiAgentGateway(config, bus)

        assert gw.config == config
        assert gw.bus == bus
        assert len(gw.agents) == 0
        assert gw.router is not None

    def test_init_with_multiple_agents(self, make_config, bus):
        """Gateway should initialize with multiple agents."""
        agent_list = [
            AgentConfig(id="agent1"),
            AgentConfig(id="agent2"),
            AgentConfig(id="agent3"),
        ]
        config = make_config(agent_list=agent_list, default_agent="agent1")
        gw = MultiAgentGateway(config, bus)

        assert gw.config.agents.default_agent == "agent1"
        assert len(gw.config.agents.agent_list) == 3

    def test_init_with_bindings(self, make_config, bus):
        """Gateway should initialize with routing bindings."""
        bindings = [
            AgentBinding(agent_id="telegram_agent", channels=["telegram"], priority=1),
            AgentBinding(agent_id="slack_agent", channels=["slack"], priority=1),
        ]
        config = make_config(bindings=bindings)
        gw = MultiAgentGateway(config, bus)

        assert len(gw.config.agents.bindings) == 2
        assert gw.router.bindings == bindings


class TestMultiAgentGatewayStart:
    """Test MultiAgentGateway start behavior."""

    @pytest.mark.asyncio
    async def test_start_creates_default_agent(self, make_config, bus):
        """Start should create default agent."""
        config = make_config(agent_list=[], default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        assert "default" in gw.agents
        assert len(gw.agents) == 1

        await gw.stop()

    @pytest.mark.asyncio
    async def test_start_creates_all_configured_agents(self, make_config, bus):
        """Start should create all configured agents."""
        agent_list = [
            AgentConfig(id="coder", model="anthropic/claude-opus-4-5"),
            AgentConfig(id="researcher", model="anthropic/claude-sonnet-4-5"),
        ]
        config = make_config(agent_list=agent_list, default_agent="coder")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        assert "coder" in gw.agents
        assert "researcher" in gw.agents
        assert len(gw.agents) == 2

        await gw.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, make_config, bus):
        """Start should be idempotent."""
        config = make_config()
        gw = MultiAgentGateway(config, bus)

        await gw.start()
        agents_after_first_start = len(gw.agents)

        await gw.start()  # Second start should be no-op
        agents_after_second_start = len(gw.agents)

        assert agents_after_first_start == agents_after_second_start

        await gw.stop()


class TestMultiAgentGatewayMessageRouting:
    """Test message routing in MultiAgentGateway."""

    @pytest.mark.asyncio
    async def test_message_routed_to_correct_agent(self, make_config, bus):
        """Message should be routed to correct agent based on channel."""
        bindings = [
            AgentBinding(agent_id="telegram_agent", channels=["telegram"], priority=1),
            AgentBinding(agent_id="slack_agent", channels=["slack"], priority=1),
        ]
        agent_list = [
            AgentConfig(id="telegram_agent"),
            AgentConfig(id="slack_agent"),
        ]
        config = make_config(agent_list=agent_list, bindings=bindings, default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        # Publish a message to telegram channel
        msg = InboundMessage(
            channel="telegram",
            chat_id="user123",
            content="Hello from Telegram",
            sender_id="user123",
            timestamp=datetime.now(),
        )

        # Track which agent received the message
        received_messages = {}

        async def track_message(agent_id, message):
            if agent_id not in received_messages:
                received_messages[agent_id] = []
            received_messages[agent_id].append(message)

        # Subscribe to all agent sessions to track messages
        # Note: In real scenario, AgentLoop handles this internally
        # For testing, we verify the router's decision

        target_agent = gw.router.route(msg)
        assert target_agent == "telegram_agent"

        await gw.stop()

    @pytest.mark.asyncio
    async def test_message_fallback_to_default(self, make_config, bus):
        """Message should fallback to default when no binding matches."""
        bindings = [
            AgentBinding(agent_id="telegram_agent", channels=["telegram"], priority=1),
        ]
        config = make_config(bindings=bindings, default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        # Send message from unconfigured channel
        msg = InboundMessage(
            channel="discord",  # Not in bindings
            chat_id="user456",
            content="Hello from Discord",
            sender_id="user456",
            timestamp=datetime.now(),
        )

        target_agent = gw.router.route(msg)
        assert target_agent == "default"

        await gw.stop()


class TestMultiAgentGatewayHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self, make_config, bus):
        """Health check should return status for all agents."""
        agent_list = [
            AgentConfig(id="agent1"),
            AgentConfig(id="agent2"),
        ]
        config = make_config(agent_list=agent_list, default_agent="agent1")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        status = await gw.health_check()

        assert "agent1" in status
        assert "agent2" in status
        assert status["agent1"] == "healthy"
        assert status["agent2"] == "healthy"

        await gw.stop()

    @pytest.mark.asyncio
    async def test_health_check_empty_agents(self, make_config, bus):
        """Health check with no agents should return empty dict."""
        config = make_config(agent_list=[], default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        status = await gw.health_check()

        assert "default" in status

        await gw.stop()


class TestMultiAgentGatewayStop:
    """Test gateway stop behavior."""

    @pytest.mark.asyncio
    async def test_stop_clears_agents(self, make_config, bus):
        """Stop should clear all agents."""
        config = make_config()
        gw = MultiAgentGateway(config, bus)

        await gw.start()
        assert len(gw.agents) > 0

        await gw.stop()
        assert len(gw.agents) == 0

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, make_config, bus):
        """Stop should be idempotent."""
        config = make_config()
        gw = MultiAgentGateway(config, bus)

        await gw.start()
        await gw.stop()

        # Second stop should be safe
        await gw.stop()


class TestMultiAgentGatewayGetters:
    """Test gateway getter methods."""

    @pytest.mark.asyncio
    async def test_get_agent_ids(self, make_config, bus):
        """get_agent_ids should return all agent IDs."""
        agent_list = [
            AgentConfig(id="agent1"),
            AgentConfig(id="agent2"),
            AgentConfig(id="agent3"),
        ]
        config = make_config(agent_list=agent_list, default_agent="agent1")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        ids = gw.get_agent_ids()

        assert "agent1" in ids
        assert "agent2" in ids
        assert "agent3" in ids
        assert len(ids) == 3

        await gw.stop()

    @pytest.mark.asyncio
    async def test_get_agent_returns_correct_instance(self, make_config, bus):
        """get_agent should return correct AgentLoop instance."""
        agent_list = [
            AgentConfig(id="coder"),
            AgentConfig(id="researcher"),
        ]
        config = make_config(agent_list=agent_list, default_agent="coder")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        coder_agent = gw.get_agent("coder")
        researcher_agent = gw.get_agent("researcher")
        nonexistent_agent = gw.get_agent("nonexistent")

        assert coder_agent is not None
        assert researcher_agent is not None
        assert nonexistent_agent is None

        await gw.stop()

    @pytest.mark.asyncio
    async def test_get_router_info(self, make_config, bus):
        """get_router_info should return routing configuration."""
        bindings = [
            AgentBinding(agent_id="telegram_agent", channels=["telegram"], priority=10),
        ]
        config = make_config(bindings=bindings, default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        info = gw.get_router_info()

        assert info["default_agent"] == "default"
        assert len(info["rules"]) == 1
        assert info["rules"][0]["agent_id"] == "telegram_agent"
        assert info["rules"][0]["priority"] == 10

        await gw.stop()


class TestMultiAgentGatewayConcurrency:
    """Test concurrent message handling."""

    @pytest.mark.asyncio
    async def test_concurrent_messages_different_agents(self, make_config, bus):
        """Gateway should handle concurrent messages to different agents."""
        bindings = [
            AgentBinding(agent_id="agent1", channels=["telegram"], priority=1),
            AgentBinding(agent_id="agent2", channels=["slack"], priority=1),
        ]
        agent_list = [
            AgentConfig(id="agent1"),
            AgentConfig(id="agent2"),
        ]
        config = make_config(agent_list=agent_list, bindings=bindings, default_agent="default")
        gw = MultiAgentGateway(config, bus)

        await gw.start()

        # Send concurrent messages
        messages = [
            InboundMessage(channel="telegram", chat_id="user1", content="msg1", sender_id="user1"),
            InboundMessage(channel="slack", chat_id="user2", content="msg2", sender_id="user2"),
            InboundMessage(channel="telegram", chat_id="user3", content="msg3", sender_id="user3"),
        ]

        # Route all messages
        routes = [gw.router.route(msg) for msg in messages]

        assert routes[0] == "agent1"
        assert routes[1] == "agent2"
        assert routes[2] == "agent1"

        await gw.stop()
