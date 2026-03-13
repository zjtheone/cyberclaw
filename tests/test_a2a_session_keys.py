"""Tests for Agent-to-Agent session key functionality."""

import pytest
from cyberclaw.session.keys import (
    SessionKey,
    is_legacy_format,
    normalize_session_key,
    extract_agent_id,
    extract_session_type,
)


class TestSessionKey:
    """Test SessionKey class."""
    
    def test_create_main_session(self):
        """Test creating a main session key."""
        key = SessionKey.create_main("main", "default")
        assert key.agent_id == "main"
        assert key.session_type == "main"
        assert key.session_id == "default"
        assert str(key) == "agent:main:main:default"
    
    def test_create_subagent_session(self):
        """Test creating a subagent session key."""
        key = SessionKey.create_subagent("coding", "abc123")
        assert key.agent_id == "coding"
        assert key.session_type == "subagent"
        assert key.session_id == "abc123"
        assert str(key) == "agent:coding:subagent:abc123"
    
    def test_parse_new_format(self):
        """Test parsing new format session key."""
        key = SessionKey.parse("agent:main:subagent:abc123")
        assert key.agent_id == "main"
        assert key.session_type == "subagent"
        assert key.session_id == "abc123"
    
    def test_parse_legacy_format(self):
        """Test parsing legacy format session key (converts to default agent)."""
        key = SessionKey.parse("cli:direct")
        assert key.agent_id == "default"
        assert key.session_type == "main"
        assert key.session_id == "cli:direct"
    
    def test_parse_invalid_format(self):
        """Test parsing invalid format raises error."""
        # Invalid session type should raise error
        with pytest.raises(ValueError) as exc_info:
            SessionKey.parse("agent:main:invalid:abc123")
        assert "Invalid session type: invalid" in str(exc_info.value)
        
        # Empty agent_id should raise error
        with pytest.raises(ValueError):
            SessionKey.parse("agent::main:abc123")
    
    def test_is_main_session(self):
        """Test is_main_session property."""
        main_key = SessionKey.create_main("main")
        assert main_key.is_main is True
        
        subagent_key = SessionKey.create_subagent("main", "abc123")
        assert subagent_key.is_main is False
    
    def test_is_subagent_session(self):
        """Test is_subagent_session property."""
        main_key = SessionKey.create_main("main")
        assert main_key.is_subagent is False
        
        subagent_key = SessionKey.create_subagent("main", "abc123")
        assert subagent_key.is_subagent is True
    
    def test_equality(self):
        """Test equality comparison."""
        key1 = SessionKey.create_main("main", "default")
        key2 = SessionKey.create_main("main", "default")
        key3 = SessionKey.create_main("coding", "default")
        
        assert key1 == key2
        assert key1 != key3
    
    def test_hash(self):
        """Test hash for use in sets and dicts."""
        key1 = SessionKey.create_main("main", "default")
        key2 = SessionKey.create_main("main", "default")
        
        assert hash(key1) == hash(key2)
        assert key1 in {key2}


class TestLegacyFormat:
    """Test legacy format detection."""
    
    def test_detect_legacy_format(self):
        """Test detecting legacy format."""
        assert is_legacy_format("cli:direct") is True
        assert is_legacy_format("telegram:123456") is True
        assert is_legacy_format("discord:789012") is True
    
    def test_detect_new_format(self):
        """Test detecting new format."""
        assert is_legacy_format("agent:main:main:default") is False
        assert is_legacy_format("agent:coding:subagent:abc123") is False


class TestNormalizeSessionKey:
    """Test normalize_session_key function."""
    
    def test_normalize_string(self):
        """Test normalizing string key."""
        key = normalize_session_key("agent:main:subagent:abc123")
        assert isinstance(key, SessionKey)
        assert key.agent_id == "main"
    
    def test_normalize_session_key_object(self):
        """Test normalizing SessionKey object."""
        original = SessionKey.create_main("main")
        result = normalize_session_key(original)
        assert result is original


class TestExtractFunctions:
    """Test extraction helper functions."""
    
    def test_extract_agent_id_string(self):
        """Test extracting agent ID from string."""
        assert extract_agent_id("agent:main:subagent:abc123") == "main"
        assert extract_agent_id("cli:direct") == "default"
    
    def test_extract_agent_id_object(self):
        """Test extracting agent ID from SessionKey."""
        key = SessionKey.create_subagent("coding", "abc123")
        assert extract_agent_id(key) == "coding"
    
    def test_extract_session_type(self):
        """Test extracting session type."""
        assert extract_session_type("agent:main:main:default") == "main"
        assert extract_session_type("agent:main:subagent:abc123") == "subagent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
