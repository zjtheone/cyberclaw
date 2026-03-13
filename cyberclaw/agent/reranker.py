"""
Reranking module for memory vector search.
Provides reranking of retrieved results using cross‑encoder models.
"""

from typing import List, Tuple, Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class Reranker:
    """Base reranker interface."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", **kwargs):
        self.model_name = model_name
        self.initialized = False
        self.model = None
        self.tokenizer = None
        
    def init(self):
        """Lazy initialization of the model."""
        if self.initialized:
            return
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            self.initialized = True
            logger.info(f"Loaded reranker model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, reranking will be dummy")
            self.model = None
            self.initialized = True
    
    def rerank(self, query: str, documents: List[str], scores: Optional[List[float]] = None,
               top_k: Optional[int] = None) -> List[Tuple[int, float]]:
        """
        Rerank documents based on relevance to query.
        Returns list of (original_index, new_score) sorted descending.
        """
        self.init()
        if self.model is None:
            # Dummy fallback: preserve original order and scores
            if scores is None:
                scores = [1.0] * len(documents)
            result = list(enumerate(scores))
            result.sort(key=lambda x: x[1], reverse=True)
            if top_k is not None:
                result = result[:top_k]
            return result
        
        # Prepare pairs for cross‑encoder
        pairs = [[query, doc] for doc in documents]
        # Predict scores
        predicted_scores = self.model.predict(pairs)
        # Combine with original scores (optional)
        if scores is not None:
            # Simple average for hybrid scoring
            combined = [(predicted_scores[i] + scores[i]) / 2 for i in range(len(scores))]
        else:
            combined = predicted_scores
        # Sort by combined score descending
        ranked = sorted(enumerate(combined), key=lambda x: x[1], reverse=True)
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked


class DummyReranker(Reranker):
    """Reranker that does nothing, returns original order."""
    
    def __init__(self):
        super().__init__("dummy")
        self.initialized = True
        self.model = None
    
    def rerank(self, query: str, documents: List[str], scores: Optional[List[float]] = None,
               top_k: Optional[int] = None) -> List[Tuple[int, float]]:
        if scores is None:
            scores = [1.0] * len(documents)
        result = list(enumerate(scores))
        result.sort(key=lambda x: x[1], reverse=True)
        if top_k is not None:
            result = result[:top_k]
        return result


def create_reranker(config: Dict[str, Any]) -> Reranker:
    """Factory function to create a reranker based on config."""
    reranker_type = config.get("reranker_type", "cross_encoder")
    if reranker_type == "cross_encoder":
        model_name = config.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        return Reranker(model_name)
    elif reranker_type == "dummy":
        return DummyReranker()
    else:
        logger.warning(f"Unknown reranker type: {reranker_type}, falling back to dummy")
        return DummyReranker()


# For backward compatibility
__all__ = ["Reranker", "DummyReranker", "create_reranker"]