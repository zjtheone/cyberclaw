"""Tests for Agent-to-Agent policy engine."""

import pytest
from cyberclaw.agent.policy_engine import (
    AgentToAgentPolicyEngine,
    SessionVisibilityEngine,
    PolicyCheckResult,
    PolicyDecision,
)
from pydantic import BaseModel, Field


class AgentToAgentPolicy(BaseModel):
    enabled: bool = False
    allow: list = Field(default_factory=list)
    deny: list = Field(default_factory=list)
    max_ping_pong_turns: int = 5


class SessionVisibilityPolicy(BaseModel):
    visibility: str = "tree"
    
    @property
    def is_all(self):
        return self.visibility == "all"
    
    @property
    def is_self(self):
        return self.visibility == "self"
    
    @property
    def is_agent(self):
        return self.visibility == "agent"
    
    @property
    def is_tree(self):
        return self.visibility == "tree"


class TestAgentToAgentPolicyEngine:
    """Test A2A policy engine."""
    
    def test_spawn_allowed_same_agent_disabled(self):
        policy = AgentToAgentPolicy(enabled=False)
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "main", current_depth=0)
        assert result.is_allowed
    
    def test_spawn_denied_cross_agent_disabled(self):
        policy = AgentToAgentPolicy(enabled=False)
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "coding", current_depth=0)
        assert result.is_denied
        assert result.result == PolicyCheckResult.DISABLED
    
    def test_spawn_allowed_with_allowlist(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["main", "coding"])
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "coding", current_depth=0)
        assert result.is_allowed
    
    def test_spawn_denied_not_in_allowlist(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["main"])
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "coding", current_depth=0)
        assert result.is_denied
        assert result.result == PolicyCheckResult.NOT_IN_ALLOWLIST
    
    def test_spawn_denied_in_denylist(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["*"], deny=["bad-agent"])
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "bad-agent", current_depth=0)
        assert result.is_denied
        assert result.result == PolicyCheckResult.IN_DENYLIST
    
    def test_spawn_denied_depth_exceeded(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["*"], max_ping_pong_turns=2)
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "coding", current_depth=2)
        assert result.is_denied
        assert result.result == PolicyCheckResult.DEPTH_EXCEEDED
    
    def test_spawn_allowed_within_depth(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["*"], max_ping_pong_turns=2)
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("main", "coding", current_depth=1)
        assert result.is_allowed
    
    def test_wildcard_allowlist(self):
        policy = AgentToAgentPolicy(enabled=True, allow=["*"])
        engine = AgentToAgentPolicyEngine(policy)
        result = engine.check_spawn_allowed("any", "agent", current_depth=0)
        assert result.is_allowed
    
    def test_get_max_spawn_depth(self):
        policy = AgentToAgentPolicy(max_ping_pong_turns=3)
        engine = AgentToAgentPolicyEngine(policy)
        assert engine.get_max_spawn_depth() == 3
    
    def test_is_enabled(self):
        policy_enabled = AgentToAgentPolicy(enabled=True)
        policy_disabled = AgentToAgentPolicy(enabled=False)
        assert AgentToAgentPolicyEngine(policy_enabled).is_enabled() is True
        assert AgentToAgentPolicyEngine(policy_disabled).is_enabled() is False


class TestSessionVisibilityEngine:
    """Test session visibility engine."""
    
    def test_visibility_all(self):
        policy = SessionVisibilityPolicy(visibility="all")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session("main", "agent:main:main:1", "agent:coding:main:2", "coding")
        assert result.is_allowed
    
    def test_visibility_self_same_session(self):
        policy = SessionVisibilityPolicy(visibility="self")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session("main", "agent:main:main:1", "agent:main:main:1", "main")
        assert result.is_allowed
    
    def test_visibility_self_different_session(self):
        policy = SessionVisibilityPolicy(visibility="self")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session("main", "agent:main:main:1", "agent:main:subagent:abc", "main")
        assert result.is_denied
    
    def test_visibility_agent_same_agent(self):
        policy = SessionVisibilityPolicy(visibility="agent")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session("main", "agent:main:main:1", "agent:main:subagent:abc", "main")
        assert result.is_allowed
    
    def test_visibility_agent_different_agent(self):
        policy = SessionVisibilityPolicy(visibility="agent")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session("main", "agent:main:main:1", "agent:coding:main:2", "coding")
        assert result.is_denied
    
    def test_visibility_tree_child_session(self):
        policy = SessionVisibilityPolicy(visibility="tree")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session(
            "main", "agent:main:main:1", "agent:main:subagent:abc", "main",
            parent_session_key="agent:main:main:1"
        )
        assert result.is_allowed
    
    def test_visibility_tree_unrelated_session(self):
        policy = SessionVisibilityPolicy(visibility="tree")
        engine = SessionVisibilityEngine(policy)
        result = engine.can_see_session(
            "main", "agent:main:main:1", "agent:main:subagent:xyz", "main",
            parent_session_key="agent:main:main:999"
        )
        assert result.is_denied


class TestPolicyDecision:
    """Test PolicyDecision class."""
    
    def test_is_allowed_property(self):
        decision = PolicyDecision(result=PolicyCheckResult.ALLOWED, message="Allowed")
        assert decision.is_allowed is True
        assert decision.is_denied is False
    
    def test_is_denied_property(self):
        for result in [PolicyCheckResult.DENIED, PolicyCheckResult.DISABLED,
                      PolicyCheckResult.DEPTH_EXCEEDED, PolicyCheckResult.NOT_IN_ALLOWLIST,
                      PolicyCheckResult.IN_DENYLIST]:
            decision = PolicyDecision(result=result, message="Denied")
            assert decision.is_denied is True
            assert decision.is_allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
