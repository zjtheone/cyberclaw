"""Tests for the MessageRouter."""

import pytest
from datetime import datetime

from cyberclaw.gateway.router import MessageRouter
from cyberclaw.config.schema import AgentBinding
from cyberclaw.bus.events import InboundMessage


def make_message(
    channel: str = "telegram",
    chat_id: str = "123456",
    content: str = "Hello",
    sender_id: str = "user1",
) -> InboundMessage:
    """Helper to create InboundMessage for testing."""
    return InboundMessage(
        channel=channel,
        chat_id=chat_id,
        content=content,
        sender_id=sender_id,
        timestamp=datetime.now(),
    )


class TestRouteByChannel:
    """Test routing by channel name."""

    def test_route_by_channel_match(self):
        """Message should route to agent matching channel."""
        bindings = [
            AgentBinding(
                agent_id="telegram_agent",
                channels=["telegram"],
                priority=1,
            ),
            AgentBinding(
                agent_id="slack_agent",
                channels=["slack"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(channel="telegram")
        result = router.route(msg)

        assert result == "telegram_agent"

    def test_route_by_channel_no_match_fallback(self):
        """Message should fallback to default when channel doesn't match."""
        bindings = [
            AgentBinding(
                agent_id="telegram_agent",
                channels=["telegram"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(channel="slack")
        result = router.route(msg)

        assert result == "default"

    def test_route_by_channel_empty_list_matches_all(self):
        """Empty channels list should match any channel."""
        bindings = [
            AgentBinding(
                agent_id="catch_all",
                channels=[],  # Empty = match all
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(channel="any_channel")
        result = router.route(msg)

        assert result == "catch_all"


class TestRouteByChatId:
    """Test routing by chat_id."""

    def test_route_by_chat_id_exact_match(self):
        """Message should route to agent matching chat_id."""
        bindings = [
            AgentBinding(
                agent_id="vip_agent",
                chat_ids=["vip_user_123"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="vip_user_123")
        result = router.route(msg)

        assert result == "vip_agent"

    def test_route_by_chat_id_no_match_fallback(self):
        """Message should fallback to default when chat_id doesn't match."""
        bindings = [
            AgentBinding(
                agent_id="vip_agent",
                chat_ids=["vip_user_123"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="regular_user")
        result = router.route(msg)

        assert result == "default"

    def test_route_by_chat_id_empty_list_matches_all(self):
        """Empty chat_ids list should match any chat_id."""
        bindings = [
            AgentBinding(
                agent_id="catch_all",
                chat_ids=[],  # Empty = match all
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="any_chat")
        result = router.route(msg)

        assert result == "catch_all"


class TestRouteByPattern:
    """Test routing by chat_pattern (regex)."""

    def test_route_by_pattern_match(self):
        """Message should route to agent matching chat_pattern."""
        bindings = [
            AgentBinding(
                agent_id="group_agent",
                chat_pattern=r"^group_.*",
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="group_12345")
        result = router.route(msg)

        assert result == "group_agent"

    def test_route_by_pattern_no_match_fallback(self):
        """Message should fallback when chat_pattern doesn't match."""
        bindings = [
            AgentBinding(
                agent_id="group_agent",
                chat_pattern=r"^group_.*",
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="dm_user_123")
        result = router.route(msg)

        assert result == "default"

    def test_route_by_pattern_invalid_regex_skips(self):
        """Invalid regex should be skipped, not cause error."""
        bindings = [
            AgentBinding(
                agent_id="bad_pattern_agent",
                chat_pattern="[invalid(regex",  # Invalid regex
                priority=1,
            ),
            AgentBinding(
                agent_id="fallback_agent",
                channels=[],  # Match all
                priority=0,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(chat_id="any_chat")
        result = router.route(msg)

        # Should skip the invalid pattern and match the fallback
        assert result == "fallback_agent"


class TestRouteByKeyword:
    """Test routing by keywords in message content."""

    def test_route_by_keyword_match(self):
        """Message should route to agent matching keyword."""
        bindings = [
            AgentBinding(
                agent_id="research_agent",
                keywords=["搜索", "查找", "research"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(content="请帮我搜索一下这个主题")
        result = router.route(msg)

        assert result == "research_agent"

    def test_route_by_keyword_case_insensitive(self):
        """Keyword matching should be case-insensitive."""
        bindings = [
            AgentBinding(
                agent_id="research_agent",
                keywords=["Research"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(content="Can you research this topic?")
        result = router.route(msg)

        assert result == "research_agent"

    def test_route_by_keyword_no_match_fallback(self):
        """Message should fallback when no keywords match."""
        bindings = [
            AgentBinding(
                agent_id="research_agent",
                keywords=["搜索", "查找"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(content="Just a casual message")
        result = router.route(msg)

        assert result == "default"

    def test_route_by_keyword_empty_list_matches_all(self):
        """Empty keywords list should match any content."""
        bindings = [
            AgentBinding(
                agent_id="catch_all",
                keywords=[],  # Empty = match all
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(content="Any content here")
        result = router.route(msg)

        assert result == "catch_all"


class TestRoutePriority:
    """Test routing priority."""

    def test_route_priority_higher_wins(self):
        """Higher priority binding should win."""
        bindings = [
            AgentBinding(
                agent_id="low_priority",
                channels=["telegram"],
                priority=1,
            ),
            AgentBinding(
                agent_id="high_priority",
                channels=["telegram"],
                priority=10,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(channel="telegram")
        result = router.route(msg)

        assert result == "high_priority"

    def test_route_priority_first_match_wins(self):
        """First matching binding (by priority order) should win."""
        bindings = [
            AgentBinding(
                agent_id="agent1",
                keywords=["help"],
                priority=5,
            ),
            AgentBinding(
                agent_id="agent2",
                keywords=["help", "urgent"],
                priority=5,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        # Both match, but agent2 is more specific
        # However, since they have same priority, first one wins
        msg = make_message(content="help me with something urgent")
        result = router.route(msg)

        # First matching binding wins
        assert result == "agent1"


class TestRouteFallback:
    """Test fallback behavior."""

    def test_route_fallback_default(self):
        """No matching bindings should fallback to default."""
        bindings = [
            AgentBinding(
                agent_id="telegram_agent",
                channels=["telegram"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="my_default")

        msg = make_message(channel="slack")
        result = router.route(msg)

        assert result == "my_default"

    def test_route_no_bindings_uses_default(self):
        """Empty bindings list should use default."""
        router = MessageRouter(bindings=[], default_agent="only_default")

        msg = make_message(channel="telegram")
        result = router.route(msg)

        assert result == "only_default"


class TestRouteComplexConditions:
    """Test complex condition matching (AND logic)."""

    def test_route_all_conditions_must_match(self):
        """All specified conditions must match (AND logic)."""
        bindings = [
            AgentBinding(
                agent_id="vip_telegram",
                channels=["telegram"],
                chat_ids=["vip_123"],
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        # Channel matches but chat_id doesn't
        msg1 = make_message(channel="telegram", chat_id="regular_456")
        result1 = router.route(msg1)
        assert result1 == "default"

        # Chat_id matches but channel doesn't
        msg2 = make_message(channel="slack", chat_id="vip_123")
        result2 = router.route(msg2)
        assert result2 == "default"

        # Both match
        msg3 = make_message(channel="telegram", chat_id="vip_123")
        result3 = router.route(msg3)
        assert result3 == "vip_telegram"

    def test_route_empty_lists_match_all(self):
        """Empty lists should not restrict matching."""
        bindings = [
            AgentBinding(
                agent_id="unrestricted",
                channels=[],  # Match all channels
                chat_ids=[],  # Match all chat_ids
                keywords=[],  # Match all content
                priority=1,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        msg = make_message(channel="any", chat_id="any", content="anything")
        result = router.route(msg)

        assert result == "unrestricted"


class TestGetRoutingInfo:
    """Test routing info retrieval."""

    def test_get_routing_info_structure(self):
        """get_routing_info should return structured data."""
        bindings = [
            AgentBinding(
                agent_id="test_agent",
                channels=["telegram"],
                priority=5,
            ),
        ]
        router = MessageRouter(bindings, default_agent="default")

        info = router.get_routing_info()

        assert "default_agent" in info
        assert "rules" in info
        assert info["default_agent"] == "default"
        assert len(info["rules"]) == 1
        assert info["rules"][0]["agent_id"] == "test_agent"
        assert info["rules"][0]["priority"] == 5
