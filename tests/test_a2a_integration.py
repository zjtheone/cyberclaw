"""Integration tests for Agent-to-Agent protocol."""

import pytest
import asyncio
import sys
import os

# Add cyberclaw to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestA2AWorkflow:
    """Test complete A2A workflow."""
    
    def test_orchestrator_pattern(self):
        """Test orchestrator pattern workflow."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager, create_announce_event
        from cyberclaw.agent.policy_engine import AgentToAgentPolicyEngine
        from pydantic import BaseModel, Field
        
        # Simple policy model for testing
        class TestPolicy(BaseModel):
            deny: list = Field(default_factory=list)
            enabled: bool = True
            allow: list = Field(default_factory=list)
            max_ping_pong_turns: int = 2
        
        # Setup
        manager = AnnounceChainManager()
        policy = TestPolicy(enabled=True, allow=["*"])
        policy_engine = AgentToAgentPolicyEngine(policy)
        
        # Simulate workflow
        main_session = "agent:main:main:1"
        orchestrator_session = "agent:main:subagent:orch1"
        
        # Check spawn allowed
        spawn_result = policy_engine.check_spawn_allowed("main", "main", 0)
        assert spawn_result.is_allowed
        
        # Register worker announcements
        for i in range(3):
            event = create_announce_event(
                task_id=f"worker{i}",
                task_label=f"Worker {i}",
                task_description=f"Task {i}",
                result=f"Result from worker {i}",
                status="ok",
                depth=2,
                session_key=f"agent:main:subagent:w{i}",
                parent_session_key=orchestrator_session,
                runtime_seconds=10.0,
            )
            manager.register_announce(event)
        
        # Verify aggregation
        agg = manager.get_aggregation(orchestrator_session)
        assert agg is not None
        assert len(agg.children) == 3
        
        print("✅ Orchestrator pattern test successful")
    
    def test_policy_enforcement(self):
        """Test policy enforcement."""
        from cyberclaw.agent.policy_engine import AgentToAgentPolicyEngine
        from pydantic import BaseModel, Field
        
        class TestPolicy(BaseModel):
            deny: list = Field(default_factory=list)
            enabled: bool = True
            allow: list = Field(default_factory=list)
            deny: list = Field(default_factory=list)
            max_ping_pong_turns: int = 2
        
        # Test allowlist
        policy = TestPolicy(enabled=True, allow=["main", "coding"])
        engine = AgentToAgentPolicyEngine(policy)
        
        result = engine.check_spawn_allowed("main", "coding", 0)
        assert result.is_allowed
        
        result = engine.check_spawn_allowed("main", "unknown", 0)
        assert result.is_denied
        
        # Test denylist
        policy = TestPolicy(enabled=True, allow=["*"], deny=["bad"])
        engine = AgentToAgentPolicyEngine(policy)
        
        result = engine.check_spawn_allowed("main", "bad", 0)
        assert result.is_denied
        
        print("✅ Policy enforcement test successful")


class TestSessionKey:
    """Test session key functionality."""
    
    def test_parse_legacy_format(self):
        """Test parsing legacy format."""
        from cyberclaw.session.keys import SessionKey
        
        key = SessionKey.parse("cli:direct")
        assert key.agent_id == "default"
        assert key.session_type == "main"
        assert key.session_id == "cli:direct"
    
    def test_parse_new_format(self):
        """Test parsing new format."""
        from cyberclaw.session.keys import SessionKey
        
        key = SessionKey.parse("agent:main:subagent:abc123")
        assert key.agent_id == "main"
        assert key.session_type == "subagent"
        assert key.session_id == "abc123"
    
    def test_create_methods(self):
        """Test create methods."""
        from cyberclaw.session.keys import SessionKey
        
        key = SessionKey.create_main("main", "default")
        assert str(key) == "agent:main:main:default"
        
        key = SessionKey.create_subagent("coding", "xyz789")
        assert str(key) == "agent:coding:subagent:xyz789"
    
    print("✅ Session key tests successful")


class TestAnnounceChain:
    """Test announce chain functionality."""
    
    def test_message_formatting(self):
        """Test message formatting."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager, create_announce_event
        
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Research",
            task_description="Research topic",
            result="Found information",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=15.5,
            token_usage={"input": 1000, "output": 500},
        )
        
        manager.register_announce(event)
        message = manager.format_announce_message(event, include_stats=True)
        
        assert "Research" in message
        assert "15.5s" in message
        assert "Tokens:" in message
    
    def test_cascade_stop(self):
        """Test cascade stop."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager, create_announce_event
        
        manager = AnnounceChainManager()
        
        # Create parent-child relationship
        parent = create_announce_event(
            task_id="parent",
            task_label="Parent",
            task_description="Parent task",
            result="Done",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:parent",
            parent_session_key="agent:main:main:1",
            runtime_seconds=1.0,
        )
        manager.register_announce(parent)
        
        child = create_announce_event(
            task_id="child",
            task_label="Child",
            task_description="Child task",
            result="Done",
            status="ok",
            depth=2,
            session_key="agent:main:subagent:child",
            parent_session_key="agent:main:subagent:parent",
            runtime_seconds=1.0,
        )
        manager.register_announce(child)
        
        # Get descendants
        descendants = manager.cascade_stop("agent:main:main:1")
        assert "agent:main:subagent:parent" in descendants
        
        print("✅ Cascade stop test successful")


class TestPingPongDialog:
    """Test ping-pong dialog functionality."""
    
    @pytest.mark.asyncio
    async def test_dialog_flow(self):
        """Test dialog flow."""
        from cyberclaw.agent.pingpong_dialog import PingPongDialog
        
        turn_count = [0]
        
        async def mock_send(session, message, timeout):
            turn_count[0] += 1
            if turn_count[0] <= 2:
                return f"Response {turn_count[0]}"
            else:
                return "REPLY_SKIP"
        
        dialog = PingPongDialog(max_turns=5, timeout_seconds=10)
        
        result = await dialog.run(
            requester_session="agent:main:main:1",
            target_session="agent:coding:main:2",
            initial_message="Hello",
            send_callback=mock_send,
        )
        
        assert result.turn_count == 3
        assert result.stopped_early is True
        assert result.stop_reason == "SKIP signal received"
    
    @pytest.mark.asyncio
    async def test_max_turns(self):
        """Test max turns reached."""
        from cyberclaw.agent.pingpong_dialog import PingPongDialog
        
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
        
        print("✅ PingPong dialog tests successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
