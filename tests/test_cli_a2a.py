"""Tests for A2A CLI commands."""

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestSubagentsCLI:
    """Test subagents CLI commands."""
    
    def test_subagents_list(self):
        """Test subagents list command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["list"])
        assert result.exit_code == 0
        assert "Subagents list command" in result.stdout
    
    def test_subagents_kill(self):
        """Test subagents kill command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["kill", "abc123", "--force"])
        assert result.exit_code == 0
        assert "Kill subagent: abc123" in result.stdout
    
    def test_subagents_kill_all(self):
        """Test subagents kill all command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["kill", "all", "--force"])
        assert result.exit_code == 0
        assert "Kill subagent: all" in result.stdout
    
    def test_subagents_log(self):
        """Test subagents log command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["log", "abc123", "--limit", "10"])
        assert result.exit_code == 0
        assert "Log for subagent: abc123" in result.stdout
    
    def test_subagents_info(self):
        """Test subagents info command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["info", "abc123"])
        assert result.exit_code == 0
        assert "Info for subagent: abc123" in result.stdout
    
    def test_subagents_send(self):
        """Test subagents send command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(
            subagents_app,
            ["send", "abc123", "Please focus on error handling"]
        )
        assert result.exit_code == 0
        assert "Sending message to abc123" in result.stdout
    
    def test_subagents_steer(self):
        """Test subagents steer command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(
            subagents_app,
            ["steer", "abc123", "Focus on performance", "--priority", "high"]
        )
        assert result.exit_code == 0
        assert "Steering subagent abc123" in result.stdout
    
    def test_subagents_spawn(self):
        """Test subagents spawn command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(
            subagents_app,
            ["spawn", "coding", "Implement REST API", "--model", "claude-opus"]
        )
        assert result.exit_code == 0
        assert "Spawning subagent:" in result.stdout
        assert "coding" in result.stdout
    
    def test_subagents_tree(self):
        """Test subagents tree command."""
        from cyberclaw.cli.subagents import subagents_app
        
        result = runner.invoke(subagents_app, ["tree"])
        assert result.exit_code == 0
        assert "Spawn Tree" in result.stdout


class TestSessionsCLI:
    """Test sessions CLI commands."""
    
    def test_sessions_focus(self):
        """Test sessions focus command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(
            sessions_app,
            ["focus", "agent:main:subagent:abc123"]
        )
        assert result.exit_code == 0
        assert "Focusing on session:" in result.stdout
    
    def test_sessions_unfocus(self):
        """Test sessions unfocus command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["unfocus"])
        assert result.exit_code == 0
        assert "Unfocusing current thread" in result.stdout
    
    def test_sessions_idle_view(self):
        """Test sessions idle view command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["idle"])
        assert result.exit_code == 0
        assert "Current idle timeout" in result.stdout
    
    def test_sessions_idle_set(self):
        """Test sessions idle set command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["idle", "1h"])
        assert result.exit_code == 0
        assert "Setting idle timeout to:" in result.stdout
    
    def test_sessions_idle_off(self):
        """Test sessions idle off command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["idle", "off"])
        assert result.exit_code == 0
        assert "Disabling idle timeout" in result.stdout
    
    def test_sessions_max_age_view(self):
        """Test sessions max-age view command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["max-age"])
        assert result.exit_code == 0
        assert "Current maximum session age" in result.stdout
    
    def test_sessions_list(self):
        """Test sessions list command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["list"])
        assert result.exit_code == 0
        assert "Sessions" in result.stdout
    
    def test_sessions_info(self):
        """Test sessions info command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(
            sessions_app,
            ["info", "agent:main:main:1"]
        )
        assert result.exit_code == 0
        assert "Session Info:" in result.stdout
    
    def test_sessions_bindings(self):
        """Test sessions bindings command."""
        from cyberclaw.cli.sessions import sessions_app
        
        result = runner.invoke(sessions_app, ["bindings"])
        assert result.exit_code == 0
        assert "Active Thread Bindings" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
