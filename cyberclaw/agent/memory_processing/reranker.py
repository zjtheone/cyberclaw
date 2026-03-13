"""
Reranking module for enhanced hybrid retrieval.
Uses cross‑encoder models to reorder search results based on query‑document relevance.
"""
import logging
from typing import List, Tuple, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


class Reranker:
    """Re‑ranker based on a cross‑encoder model."""
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: Optional[str] = None,
        max_length: int = 512,
        **kwargs
    ):
        """
        Initialize a cross‑encoder reranker.
        
        Args:
            model_name: Hugging Face model identifier or local path.
            device: 'cpu', 'cuda', 'mps' etc. If None, auto‑detect.
            max_length: Maximum token length for model input.
            **kwargs: Additional arguments passed to the CrossEncoder constructor.
        """
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.model = None
        self._load_model(**kwargs)
    
    def _load_model(self, **kwargs):
        """Load the cross‑encoder model (optional dependency)."""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
                **kwargs
            )
            logger.info(f"Loaded cross‑encoder model: {self.model_name}")
        except ImportError:
            logger.warning(
                "sentence‑transformers not installed, reranking will be disabled. "
                "Install with: pip install sentence‑transformers"
            )
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load cross‑encoder model {self.model_name}: {e}")
            self.model = None
    
    def is_available(self) -> bool:
        """Return True if a functional cross‑encoder model is loaded."""
        return self.model is not None
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> List[Tuple[int, float]]:
        """
        Re‑rank documents with respect to the query.
        
        Args:
            query: Search query.
            documents: List of document texts.
            top_k: Number of top results to return. If None, return all in ranked order.
            batch_size: Batch size for model inference.
        
        Returns:
            List of (original_index, relevance_score) sorted descending by score.
        """
        if not self.is_available() or len(documents) == 0:
            # Fallback: return documents in original order with dummy scores
            scores = [1.0] * len(documents)
            ranked = list(enumerate(scores))
            if top_k is not None:
                ranked = ranked[:top_k]
            return ranked
        
        try:
            # Prepare query‑document pairs
            pairs = [[query, doc] for doc in documents]
            # Predict relevance scores
            scores = self.model.predict(
                pairs,
                batch_size=batch_size,
                convert_to_tensor=False,
                convert_to_numpy=True
            )
            # scores is a 1‑D numpy array
            scores = scores.tolist()
            # Combine indices and scores, sort descending
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            if top_k is not None:
                ranked = ranked[:top_k]
            return ranked
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback to original order
            scores = [1.0] * len(documents)
            ranked = list(enumerate(scores))
            if top_k is not None:
                ranked = ranked[:top_k]
            return ranked
    
    def rerank_with_chunks(
        self,
        query: str,
        chunks: List[Tuple["MemoryChunk", float]],  # type: ignore
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> List[Tuple["MemoryChunk", float]]:
        """
        Convenience method to re‑rank memory chunks.
        
        Args:
            query: Search query.
            chunks: List of (MemoryChunk, initial_score) tuples.
            top_k: Number of top results to return.
            batch_size: Batch size for inference.
        
        Returns:
            Re‑ordered list of (MemoryChunk, new_score) sorted descending.
        """
        if not chunks:
            return []
        documents = [chunk.text for chunk, _ in chunks]
        ranked_indices = self.rerank(query, documents, top_k=top_k, batch_size=batch_size)
        # Map back to chunks, using the cross‑encoder score as final relevance
        reranked = []
        for idx, score in ranked_indices:
            chunk, _ = chunks[idx]
            reranked.append((chunk, float(score)))
        return reranked


class DummyReranker:
    """No‑op reranker that returns the input unchanged."""
    
    def is_available(self) -> bool:
        return False
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> List[Tuple[int, float]]:
        scores = [1.0] * len(documents)
        ranked = list(enumerate(scores))
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked
    
    def rerank_with_chunks(
        self,
        query: str,
        chunks: List[Tuple["MemoryChunk", float]],
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> List[Tuple["MemoryChunk", float]]:
        if top_k is not None:
            return chunks[:top_k]
        return chunks


def create_reranker(config: dict) -> Union[Reranker, DummyReranker]:
    """
    Factory function to create a reranker based on configuration.
    
    Expected config keys:
        - reranker_enabled: bool (default False)
        - reranker_model: str (model name)
        - reranker_device: str (optional)
        - reranker_max_length: int (optional)
    """
    if not config.get("reranker_enabled", False):
        return DummyReranker()
    
    model_name = config.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    device = config.get("reranker_device", None)
    max_length = config.get("reranker_max_length", 512)
    
    return Reranker(
        model_name=model_name,
        device=device,
        max_length=max_length
    )
