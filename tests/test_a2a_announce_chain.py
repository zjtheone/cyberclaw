"""Tests for Announce Chain management."""

import pytest
from cyberclaw.agent.announce_chain import (
    AnnounceChainManager,
    AnnounceEvent,
    AnnounceType,
    AggregatedResult,
    create_announce_event,
)


class TestAnnounceEvent:
    """Test AnnounceEvent class."""
    
    def test_create_event(self):
        """Test creating an announce event."""
        event = create_announce_event(
            task_id="task123",
            task_label="Test Task",
            task_description="Test Description",
            result="Task completed",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.5,
        )
        
        assert event.task_id == "task123"
        assert event.task_label == "Test Task"
        assert event.depth == 1
        assert event.status == "ok"
        assert event.event_type == AnnounceType.COMPLETION
    
    def test_create_error_event(self):
        """Test creating an error event."""
        event = create_announce_event(
            task_id="task123",
            task_label="Failed Task",
            task_description="Test",
            result="Error occurred",
            status="error",
            depth=2,
            session_key="agent:main:subagent:xyz",
            parent_session_key="agent:main:main:1",
            runtime_seconds=1.0,
        )
        
        assert event.status == "error"
        assert event.event_type == AnnounceType.ERROR
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = create_announce_event(
            task_id="task123",
            task_label="Test",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.0,
        )
        
        data = event.to_dict()
        assert data["task_id"] == "task123"
        assert data["depth"] == 1
        assert "created_at" in data


class TestAggregatedResult:
    """Test AggregatedResult class."""
    
    def test_create_aggregation(self):
        """Test creating an aggregation."""
        agg = AggregatedResult(parent_session_key="agent:main:main:1")
        assert agg.parent_session_key == "agent:main:main:1"
        assert len(agg.children) == 0
        assert agg.synthesis_complete is False
    
    def test_add_child(self):
        """Test adding child events."""
        agg = AggregatedResult(parent_session_key="agent:main:main:1")
        
        event1 = create_announce_event(
            task_id="task1",
            task_label="Task 1",
            task_description="Test 1",
            result="Result 1",
            status="ok",
            depth=2,
            session_key="agent:main:subagent:1",
            parent_session_key="agent:main:main:1",
            runtime_seconds=1.0,
        )
        
        event2 = create_announce_event(
            task_id="task2",
            task_label="Task 2",
            task_description="Test 2",
            result="Result 2",
            status="ok",
            depth=2,
            session_key="agent:main:subagent:2",
            parent_session_key="agent:main:main:1",
            runtime_seconds=2.0,
        )
        
        agg.add_child(event1)
        agg.add_child(event2)
        
        assert len(agg.children) == 2
    
    def test_get_summary(self):
        """Test getting aggregation summary."""
        agg = AggregatedResult(parent_session_key="agent:main:main:1")
        
        for i in range(3):
            event = create_announce_event(
                task_id=f"task{i}",
                task_label=f"Task {i}",
                task_description=f"Test {i}",
                result=f"Result {i}",
                status="ok",
                depth=2,
                session_key=f"agent:main:subagent:{i}",
                parent_session_key="agent:main:main:1",
                runtime_seconds=1.0,
            )
            agg.add_child(event)
        
        summary = agg.get_summary()
        assert "3 child(ren)" in summary
        assert "Task 0" in summary
        assert "Task 1" in summary
        assert "Task 2" in summary


class TestAnnounceChainManager:
    """Test AnnounceChainManager class."""
    
    def test_register_announce(self):
        """Test registering an announce event."""
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Test",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.0,
        )
        
        manager.register_announce(event)
        
        assert event.event_id in manager._events
        assert "agent:main:main:1" in manager._session_children
    
    def test_get_aggregation(self):
        """Test getting aggregation for a session."""
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Test",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.0,
        )
        
        manager.register_announce(event)
        
        agg = manager.get_aggregation("agent:main:main:1")
        assert agg is not None
        assert len(agg.children) == 1
    
    def test_get_child_events(self):
        """Test getting child events for a session."""
        manager = AnnounceChainManager()
        
        for i in range(3):
            event = create_announce_event(
                task_id=f"task{i}",
                task_label=f"Task {i}",
                task_description=f"Test {i}",
                result=f"Result {i}",
                status="ok",
                depth=2,
                session_key=f"agent:main:subagent:{i}",
                parent_session_key="agent:main:main:1",
                runtime_seconds=1.0,
            )
            manager.register_announce(event)
        
        children = manager.get_child_events("agent:main:main:1")
        assert len(children) == 3
    
    def test_format_announce_message(self):
        """Test formatting an announce message."""
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Test Task",
            task_description="Test Description",
            result="Test Result",
            status="ok",
            depth=2,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.5,
            token_usage={"input": 100, "output": 50},
        )
        
        message = manager.format_announce_message(event)
        assert "Test Task" in message
        assert "depth 2" in message
        assert "completed successfully" in message
        assert "Runtime: 5.5s" in message
        assert "Tokens:" in message
    
    def test_format_aggregation_message(self):
        """Test formatting an aggregation message."""
        manager = AnnounceChainManager()
        
        # Register multiple children
        for i in range(2):
            event = create_announce_event(
                task_id=f"task{i}",
                task_label=f"Task {i}",
                task_description=f"Test {i}",
                result=f"Result {i}",
                status="ok",
                depth=2,
                session_key=f"agent:main:subagent:{i}",
                parent_session_key="agent:main:main:1",
                runtime_seconds=1.0,
            )
            manager.register_announce(event)
        
        agg = manager.get_aggregation("agent:main:main:1")
        message = manager.format_aggregation_message(agg)
        
        assert "2 child result(s)" in message
        assert "Task 0" in message
        assert "Task 1" in message
    
    def test_cascade_stop(self):
        """Test cascade stop mechanism."""
        manager = AnnounceChainManager()
        
        # Create a tree: main → sub1 → sub2
        event1 = create_announce_event(
            task_id="task1",
            task_label="Sub 1",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:1",
            parent_session_key="agent:main:main:1",
            runtime_seconds=1.0,
        )
        manager.register_announce(event1)
        
        event2 = create_announce_event(
            task_id="task2",
            task_label="Sub 2",
            task_description="Test",
            result="Result",
            status="ok",
            depth=2,
            session_key="agent:main:subagent:2",
            parent_session_key="agent:main:subagent:1",
            runtime_seconds=1.0,
        )
        manager.register_announce(event2)
        
        # Get descendants of main
        descendants = manager.cascade_stop("agent:main:main:1")
        assert "agent:main:subagent:1" in descendants
        # Note: sub2 is child of sub1, not main directly
    
    def test_get_spawn_tree(self):
        """Test getting spawn tree structure."""
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Test",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.0,
        )
        manager.register_announce(event)
        
        tree = manager.get_spawn_tree("agent:main:main:1")
        assert tree["session_key"] == "agent:main:main:1"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["task_id"] == "task123"
    
    def test_clear(self):
        """Test clearing the manager."""
        manager = AnnounceChainManager()
        
        event = create_announce_event(
            task_id="task123",
            task_label="Test",
            task_description="Test",
            result="Result",
            status="ok",
            depth=1,
            session_key="agent:main:subagent:abc",
            parent_session_key="agent:main:main:1",
            runtime_seconds=5.0,
        )
        manager.register_announce(event)
        
        manager.clear()
        
        assert len(manager._events) == 0
        assert len(manager._aggregations) == 0
        assert len(manager._session_children) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
