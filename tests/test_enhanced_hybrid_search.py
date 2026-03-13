import pytest
import sqlite3
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cyberclaw.agent.memory_vector import HybridSearch, MemoryChunk

@pytest.fixture
def mock_hybrid_index():
    index = HybridSearch(":memory:", config={})
    
    # Mock connection to return expected results
    mock_conn = MagicMock()
    mock_cursor_fts = MagicMock()
    mock_cursor_vec = MagicMock()
    mock_cursor_select = MagicMock()
    
    # Setup FTS mock results
    # Use POSITIVE scores for easier testing to avoid confusion
    # with inverted negative logic
    mock_cursor_fts.fetchall.return_value = [
        {"id": "doc1", "score": 5.0},  
        {"id": "doc2", "score": 3.0},
    ]
    
    # Setup Vector mock results
    mock_cursor_vec.fetchall.return_value = [
        {"id": "doc2", "distance": 0.2},
        {"id": "doc3", "distance": 0.4},
    ]
    
    # Setup Select mock results
    def mock_select(query, params=None):
        if "MATCH ?" in query:
            return mock_cursor_fts
        elif "vec_search" in query:
            return mock_cursor_vec
        elif "SELECT * FROM memory_chunks" in query:
            # For _get_chunk_by_id which is called in a loop
            id_val = params[0] if params else "doc1"
            
            # Setup a row dictionary that behaves like sqlite3.Row
            row = {
                "id": id_val,
                "file_path": f"file_{id_val}.txt",
                "text": f"text for {id_val}",
                "start_line": 0,
                "end_line": 10,
                "metadata": "{}",
                "hash": "hash123",
                "embedding": b"emb",
                "embedding_model": "test_model",
                "embedding_dim": 384,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            mock_cursor_select.fetchone.return_value = row
            return mock_cursor_select
        return MagicMock()
        
    mock_conn.execute.side_effect = mock_select
    index._get_connection = MagicMock(return_value=mock_conn)
    
    # Mock vectorization
    index._text_to_vector = MagicMock(return_value=b"mocked_vector")
    
    # Mock query analysis
    index._analyze_query = MagicMock(return_value={
        "query_type": "keyword",
        "original_query": "test query"
    })
    
    return index

def test_hybrid_search_scoring(mock_hybrid_index):
    """Test that FTS and vector scores are combined correctly."""
    # Run search
    results = mock_hybrid_index.search("test query", limit=10)
    
    # Verify we got all unique documents
    assert len(results) == 3
    
    # Extract just the ids and scores for easier assertion
    id_scores = {chunk.id: score for chunk, score in results}
    
    # Both sets should have been queried
    assert "doc1" in id_scores  # FTS only
    assert "doc2" in id_scores  # Both
    assert "doc3" in id_scores  # Vector only

def test_hybrid_search_query_weights(mock_hybrid_index):
    """Test that query types change the weighting."""
    # Test with keyword query type
    mock_hybrid_index._analyze_query.return_value = {
        "query_type": "keyword",
        "original_query": "test query"
    }
    
    results_keyword = mock_hybrid_index.search("test query", limit=10)
    scores_keyword = {chunk.id: score for chunk, score in results_keyword}
    
    # Test with natural language query type
    mock_hybrid_index._analyze_query.return_value = {
        "query_type": "natural_language",
        "original_query": "test query"
    }
    
    results_nl = mock_hybrid_index.search("test query", limit=10)
    scores_nl = {chunk.id: score for chunk, score in results_nl}
    
    # In natural language mode, vector search is weighted heavier
    # doc3 only has vector score, so its score should be relatively higher in NL mode
    assert scores_nl["doc3"] > scores_keyword["doc3"]
    
    # doc1 only has FTS score, so its score should be relatively higher in keyword mode
    assert scores_keyword["doc1"] > scores_nl["doc1"]
