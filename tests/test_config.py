import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cyberclaw.config.schema import Config, MemorySearchConfig

def test_memory_search_config_defaults():
    """Test the default values of the MemorySearchConfig schema."""
    config = MemorySearchConfig()
    
    # Check new chunking configuration defaults
    assert config.chunk_size == 20
    assert config.chunk_overlap == 0
    assert config.chunk_boundary == "line"
    assert config.semantic_boundary_threshold == 0.7
    
    # Check enhanced hybrid search options defaults
    assert config.query_parser_enabled is True
    assert config.keyword_weight == 0.4
    assert config.vector_weight == 0.6
    assert config.rerank_method == "none"
    assert config.rerank_top_k == 20
    assert config.cross_encoder_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert config.score_normalization is True
    assert config.score_rescaling is False
    
    # Check embedding fallback chain
    assert "openai" in config.embedding_fallback_chain
    assert "sentence_transformer" in config.embedding_fallback_chain
    assert "local_llama" in config.embedding_fallback_chain
    
    # Check reranker options
    assert config.reranker_device == "cpu"
    assert config.reranker_max_length == 512

def test_config_instantiation():
    """Test that the full config can be instantiated without errors."""
    config = Config()
    assert config is not None
    assert config.memory_search is not None
    assert config.memory_search.query_parser_enabled is True

