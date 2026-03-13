"""Tests for Orchestrator template and batch spawn functionality."""

import pytest
from cyberclaw.agent.team.orchestrator import OrchestratorTemplate, ORCHESTRATOR_SYSTEM_PROMPT
from cyberclaw.config.schema import AgentConfig, SubagentConfig


class TestOrchestratorTemplate:
    """Test OrchestratorTemplate configuration."""

    def test_orchestrator_template_config(self):
        """Test that orchestrator template applies correct config."""
        base_config = AgentConfig(id="test")

        orchestrator_config = OrchestratorTemplate.create_config(base_config)

        # Check subagent settings
        assert orchestrator_config.subagents.max_spawn_depth == 2
        assert orchestrator_config.subagents.max_children_per_agent == 10
        assert orchestrator_config.subagents.max_concurrent == 16

    def test_orchestrator_system_prompt(self):
        """Test that system prompt is not empty."""
        prompt = OrchestratorTemplate.get_system_prompt()

        assert prompt is not None
        assert len(prompt) > 0
        assert "任务协调者" in prompt
        assert "spawn" in prompt.lower()

    def test_apply_to_agent_alias(self):
        """Test that apply_to_agent is an alias for create_config."""
        base_config = AgentConfig(id="test")

        config1 = OrchestratorTemplate.create_config(base_config)
        config2 = OrchestratorTemplate.apply_to_agent(base_config)

        # Both should produce same result
        assert config1.subagents.max_spawn_depth == config2.subagents.max_spawn_depth
        assert config1.subagents.max_children_per_agent == config2.subagents.max_children_per_agent

    def test_orchestrator_preserves_base_config(self):
        """Test that orchestrator template preserves base config values."""
        base_config = AgentConfig(
            id="custom",
            model="anthropic/claude-opus-4-5",
            temperature=0.8,
            max_tokens=16384,
        )

        orchestrator_config = OrchestratorTemplate.create_config(base_config)

        # Should preserve base values
        assert orchestrator_config.id == "custom"
        assert orchestrator_config.model == "anthropic/claude-opus-4-5"
        assert orchestrator_config.temperature == 0.8
        assert orchestrator_config.max_tokens == 16384

        # Should override subagent settings
        assert orchestrator_config.subagents.max_spawn_depth == 2
        assert orchestrator_config.subagents.max_children_per_agent == 10

    def test_orchestrator_prompt_contains_best_practices(self):
        """Test that prompt contains best practices guidance."""
        prompt = OrchestratorTemplate.get_system_prompt()

        # Should mention key orchestrator concepts
        assert "分解" in prompt or "decompose" in prompt.lower()
        assert "并行" in prompt or "parallel" in prompt.lower()
        assert "spawn" in prompt.lower()
        assert "worker" in prompt.lower()
        assert "综合" in prompt or "聚合" in prompt or "aggregate" in prompt.lower()


class TestSpawnBatchParameters:
    """Test spawn tool batch parameters structure."""

    def test_parameters_include_batch_field(self):
        """Test that parameters include batch field."""
        from cyberclaw.agent.tools.spawn import SpawnTool
        from unittest.mock import Mock

        # Create mock manager
        mock_manager = Mock()

        tool = SpawnTool(manager=mock_manager)
        params = tool.parameters

        # Should have batch parameter
        assert "batch" in params["properties"]
        assert params["properties"]["batch"]["type"] == "array"

        # Batch items should have task and label
        items = params["properties"]["batch"]["items"]
        assert "task" in items["properties"]
        assert "label" in items["properties"]
        assert "task" in items["required"]

    def test_parameters_include_wait_and_timeout(self):
        """Test that parameters include wait and timeout fields."""
        from cyberclaw.agent.tools.spawn import SpawnTool
        from unittest.mock import Mock

        mock_manager = Mock()
        tool = SpawnTool(manager=mock_manager)
        params = tool.parameters

        # Should have wait parameter
        assert "wait" in params["properties"]
        assert params["properties"]["wait"]["type"] == "boolean"

        # Should have timeout parameter
        assert "timeout" in params["properties"]
        assert params["properties"]["timeout"]["type"] == "integer"


class TestAnnounceChainWaitForChildren:
    """Test announce chain wait_for_children functionality."""

    @pytest.mark.asyncio
    async def test_wait_for_children_no_children(self):
        """Test wait returns None when no children exist."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager

        manager = AnnounceChainManager()

        # Wait for non-existent parent
        result = await manager.wait_for_children(
            "parent:session",
            timeout=0.1,
            poll_interval=0.05,
        )

        # Should timeout and return None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_children_count(self):
        """Test getting children count."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager, create_announce_event

        manager = AnnounceChainManager()
        parent_key = "parent:session"

        # No children initially
        assert manager.get_children_count(parent_key) == 0
        assert not manager.has_children(parent_key)

        # Create and register child events
        event1 = create_announce_event(
            task_id="task1",
            task_label="Task 1",
            task_description="Description 1",
            result="Result 1",
            status="ok",
            depth=1,
            session_key="child:1",
            parent_session_key=parent_key,
            runtime_seconds=10.0,
        )

        event2 = create_announce_event(
            task_id="task2",
            task_label="Task 2",
            task_description="Description 2",
            result="Result 2",
            status="ok",
            depth=1,
            session_key="child:2",
            parent_session_key=parent_key,
            runtime_seconds=15.0,
        )

        manager.register_announce(event1)
        manager.register_announce(event2)

        # Should have 2 children
        assert manager.get_children_count(parent_key) == 2
        assert manager.has_children(parent_key)

    @pytest.mark.asyncio
    async def test_has_children(self):
        """Test has_children method."""
        from cyberclaw.agent.announce_chain import AnnounceChainManager

        manager = AnnounceChainManager()

        assert not manager.has_children("nonexistent:parent")

        # Register a child
        from cyberclaw.agent.announce_chain import create_announce_event

        event = create_announce_event(
            task_id="task1",
            task_label="Task 1",
            task_description="Description 1",
            result="Result 1",
            status="ok",
            depth=1,
            session_key="child:1",
            parent_session_key="parent:session",
            runtime_seconds=10.0,
        )

        manager.register_announce(event)

        assert manager.has_children("parent:session")
