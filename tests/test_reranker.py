import pytest
import os
import sys
from unittest.mock import MagicMock, patch
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cyberclaw.agent.memory_processing.reranker import Reranker, DummyReranker
from cyberclaw.agent.memory_vector import MemoryChunk

@pytest.fixture
def mock_cross_encoder():
    with patch('cyberclaw.agent.memory_processing.reranker.Reranker._load_model') as mock_load:
        # Create a Reranker with the _load_model mocked out
        # We manually set the model to a mock afterwards
        reranker = Reranker()
        
        mock_model = MagicMock()
        # predict returns a numpy array of scores
        mock_model.predict.return_value = np.array([0.1, 0.9, 0.5])
        
        reranker.model = mock_model
        return reranker

def test_dummy_reranker():
    """Test that dummy reranker returns input unchanged."""
    dummy = DummyReranker()
    assert dummy.is_available() is False

def test_reranker_availability(mock_cross_encoder):
    """Test availability check."""
    assert mock_cross_encoder.is_available() is True
    
    mock_cross_encoder.model = None
    assert mock_cross_encoder.is_available() is False

def test_rerank_basic(mock_cross_encoder):
    """Test basic reranking of strings."""
    query = "test query"
    documents = ["doc 1 text", "doc 2 text", "doc 3 text"]
    
    ranked = mock_cross_encoder.rerank(query, documents)
    
    # Check that model.predict was called correctly
    mock_cross_encoder.model.predict.assert_called_once()
    args, kwargs = mock_cross_encoder.model.predict.call_args
    
    # Check the pairs passed to predict
    pairs = args[0]
    assert len(pairs) == 3
    assert pairs[0] == ["test query", "doc 1 text"]
    assert pairs[1] == ["test query", "doc 2 text"]
    assert pairs[2] == ["test query", "doc 3 text"]
    
    # Check that results are sorted by score descending
    # Mock scores: [0.1, 0.9, 0.5]
    # Expected order: doc2 (idx 1), doc3 (idx 2), doc1 (idx 0)
    assert len(ranked) == 3
    assert ranked[0][0] == 1  # index 1
    assert ranked[0][1] == 0.9  # score 0.9
    
    assert ranked[1][0] == 2  # index 2
    assert ranked[1][1] == 0.5  # score 0.5
    
    assert ranked[2][0] == 0  # index 0
    assert ranked[2][1] == 0.1  # score 0.1

def test_rerank_with_top_k(mock_cross_encoder):
    """Test reranking with top_k limit."""
    query = "test query"
    documents = ["doc 1 text", "doc 2 text", "doc 3 text"]
    
    ranked = mock_cross_encoder.rerank(query, documents, top_k=2)
    
    assert len(ranked) == 2
    assert ranked[0][0] == 1  # index 1
    assert ranked[1][0] == 2  # index 2

def test_rerank_with_chunks(mock_cross_encoder):
    """Test reranking of MemoryChunk objects."""
    query = "test query"
    
    # Create mock chunks
    chunk1 = MagicMock(spec=MemoryChunk)
    chunk1.text = "chunk 1 text"
    
    chunk2 = MagicMock(spec=MemoryChunk)
    chunk2.text = "chunk 2 text"
    
    chunk3 = MagicMock(spec=MemoryChunk)
    chunk3.text = "chunk 3 text"
    
    # Input is list of (chunk, initial_score)
    chunks = [(chunk1, 0.8), (chunk2, 0.3), (chunk3, 0.5)]
    
    reranked = mock_cross_encoder.rerank_with_chunks(query, chunks)
    
    # Output should be reordered chunks with new scores
    # Mock scores: [0.1, 0.9, 0.5]
    # Expected order: chunk2, chunk3, chunk1
    assert len(reranked) == 3
    
    assert reranked[0][0] == chunk2
    assert reranked[0][1] == 0.9
    
    assert reranked[1][0] == chunk3
    assert reranked[1][1] == 0.5
    
    assert reranked[2][0] == chunk1
    assert reranked[2][1] == 0.1

def test_reranker_fallback_no_model(mock_cross_encoder):
    """Test fallback when model is not available."""
    mock_cross_encoder.model = None
    
    query = "test query"
    documents = ["doc 1 text", "doc 2 text", "doc 3 text"]
    
    ranked = mock_cross_encoder.rerank(query, documents)
    
    # Should return original order with dummy scores of 1.0
    assert len(ranked) == 3
    assert ranked[0][0] == 0
    assert ranked[0][1] == 1.0
    assert ranked[1][0] == 1
    assert ranked[1][1] == 1.0
    assert ranked[2][0] == 2
    assert ranked[2][1] == 1.0

def test_reranker_empty_input(mock_cross_encoder):
    """Test reranking with empty input list."""
    assert mock_cross_encoder.rerank("query", []) == []
    assert mock_cross_encoder.rerank_with_chunks("query", []) == []

def test_reranker_exception_handling(mock_cross_encoder):
    """Test fallback when model.predict raises an exception."""
    mock_cross_encoder.model.predict.side_effect = Exception("Model error")
    
    query = "test query"
    documents = ["doc 1 text", "doc 2 text", "doc 3 text"]
    
    ranked = mock_cross_encoder.rerank(query, documents)
    
    # Should fall back gracefully to original order with dummy scores
    assert len(ranked) == 3
    assert ranked[0][0] == 0
    assert ranked[0][1] == 1.0
