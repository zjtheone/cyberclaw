"""
Vector memory system for semantic retrieval, adapted from OpenClaw's memory module.
"""

import asyncio
import hashlib
import json
import sqlite3
import struct
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List, Tuple, Dict, Union
from enum import Enum
import logging

from loguru import logger

from .file_watcher import FileWatcher
from .reranker import create_reranker, Reranker, DummyReranker

# Optional imports
try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False
    logger.warning("sqlite-vec not installed, vector search will use numpy fallback")

try:
    import sqlite_vss
    SQLITE_VSS_AVAILABLE = True
except ImportError:
    SQLITE_VSS_AVAILABLE = False
    logger.warning("sqlite-vss not installed, vector search will fallback to sqlite-vec or numpy")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

# Query parser for enhanced hybrid search
try:
    from .memory_processing.query_parser import QueryParser
    QUERY_PARSER_AVAILABLE = True
except ImportError:
    QUERY_PARSER_AVAILABLE = False


@dataclass
class MemoryChunk:
    """A chunk of text with its metadata and embedding."""
    id: str
    file_path: str
    start_line: int
    end_line: int
    text: str
    hash: str
    embedding: Optional[bytes] = None  # blob of float32
    embedding_model: str = ""
    embedding_dim: int = 0
    created_at: datetime = None
    updated_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "text": self.text,
            "hash": self.hash,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EmbeddingProviderType(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL_SENTENCE_TRANSFORMER = "sentence_transformer"
    LOCAL_LLAMA = "local_llama"
    NONE = "none"


class EmbeddingProvider:
    """Wrapper for embedding models with fallback chain."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.fallback_chain = config.get("embedding_fallback_chain", ["openai", "gemini", "sentence_transformer", "local_llama", "none"])
        self._models = {}
        self._dimensions = {
            "openai": config.get("openai_model", "text-embedding-3-small"),
            "gemini": config.get("gemini_model", "models/text-embedding-004"),
            "sentence_transformer": config.get("sentence_transformer_model", "all-MiniLM-L6-v2"),
            "local_llama": config.get("llama_model_path", ""),
        }
    
    async def embed(self, texts: List[str], provider_name: str = None) -> List[List[float]]:
        """Embed a list of texts using the specified provider or fallback chain."""
        if provider_name:
            return await self._embed_with_provider(texts, provider_name)
        # Try fallback chain
        errors = []
        for provider in self.fallback_chain:
            try:
                return await self._embed_with_provider(texts, provider)
            except Exception as e:
                errors.append((provider, str(e)))
                logger.warning(f"Embedding provider {provider} failed: {e}")
                continue
        raise RuntimeError(f"All embedding providers failed: {errors}")
    
    async def _embed_with_provider(self, texts: List[str], provider: str) -> List[List[float]]:
        if provider == "openai":
            return await self._openai_embed(texts)
        elif provider == "gemini":
            return await self._gemini_embed(texts)
        elif provider == "sentence_transformer":
            return await self._sentence_transformer_embed(texts)
        elif provider == "local_llama":
            return await self._llama_embed(texts)
        elif provider == "none":
            # Return random embeddings as fallback
            dim = self.get_dimension(provider)
            return [np.random.randn(dim).tolist() for _ in texts]
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")
    
    async def _openai_embed(self, texts: List[str]) -> List[List[float]]:
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI client not installed")
        api_key = self.config.get("openai_api_key")
        api_base = self.config.get("openai_api_base", "https://api.openai.com/v1")
        model = self.config.get("openai_model", "text-embedding-3-small")
        client = OpenAI(api_key=api_key, base_url=api_base)
        # Use async? OpenAI client is sync; run in thread pool
        loop = asyncio.get_event_loop()
        def _embed():
            response = client.embeddings.create(input=texts, model=model)
            return [item.embedding for item in response.data]
        return await loop.run_in_executor(None, _embed)
    
    async def _gemini_embed(self, texts: List[str]) -> List[List[float]]:
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI not installed")
        api_key = self.config.get("gemini_api_key")
        if not api_key:
            raise ValueError("Gemini API key not configured")
        genai.configure(api_key=api_key)
        model_name = self.config.get("gemini_model", "models/text-embedding-004")
        # Use async? gemini is sync; run in thread pool
        loop = asyncio.get_event_loop()
        def _embed():
            model = genai.GenerativeModel(model_name)
            embeddings = []
            for text in texts:
                # Embedding via embed_content
                result = genai.embed_content(model=model_name, content=text)
                embeddings.append(result['embedding'])
            return embeddings
        return await loop.run_in_executor(None, _embed)
    
    async def _sentence_transformer_embed(self, texts: List[str]) -> List[List[float]]:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("Sentence transformers not installed")
        model_name = self.config.get("sentence_transformer_model", "all-MiniLM-L6-v2")
        loop = asyncio.get_event_loop()
        def _load_model():
            return SentenceTransformer(model_name)
        if model_name not in self._models:
            self._models[model_name] = await loop.run_in_executor(None, _load_model)
        model = self._models[model_name]
        # Embeddings are sync, run in executor
        def _embed():
            return model.encode(texts, convert_to_numpy=True).tolist()
        return await loop.run_in_executor(None, _embed)
    
    async def _llama_embed(self, texts: List[str]) -> List[List[float]]:
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("Llama-cpp-python not installed")
        model_path = self.config.get("llama_model_path")
        if not model_path:
            raise ValueError("Llama model path not configured")
        loop = asyncio.get_event_loop()
        if model_path not in self._models:
            def _load():
                return Llama(model_path=model_path, embedding=True, n_gpu_layers=self.config.get("llama_n_gpu_layers", -1))
            self._models[model_path] = await loop.run_in_executor(None, _load)
        model = self._models[model_path]
        # Embeddings are sync
        def _embed():
            embeddings = []
            for text in texts:
                emb = model.embed(text)
                embeddings.append(emb)
            return embeddings
        return await loop.run_in_executor(None, _embed)
    
    def get_dimension(self, provider: str) -> int:
        """Return embedding dimension for a provider."""
        if provider == "openai":
            return 1536  # text-embedding-3-small
        elif provider == "gemini":
            return 768
        elif provider == "sentence_transformer":
            # Default all-MiniLM-L6-v2
            return 384
        elif provider == "local_llama":
            # Depends on model; assume 4096
            return 4096
        elif provider == "none":
            return 128  # random embedding dimension
        else:
            return 0


class HybridSearch:
    """Combines BM25 (FTS) and vector similarity with weighted scoring."""
    
    def __init__(self, db_path: Path, config: Dict[str, Any]):
        self.db_path = db_path
        
        # Enhanced hybrid search config
        self.query_parser_enabled = config.get("query_parser_enabled", True)
        self.rerank_method = config.get("rerank_method", "none")
        self.rerank_top_k = config.get("rerank_top_k", 20)
        self.cross_encoder_model = config.get("cross_encoder_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.score_normalization = config.get("score_normalization", True)
        self.score_rescaling = config.get("score_rescaling", False)
        
        # Determine keyword and vector weights
        # If explicit weights provided, use them (normalize if sum != 1)
        kw = config.get("keyword_weight")
        vw = config.get("vector_weight")
        hw = config.get("hybrid_weight")
        if kw is not None or vw is not None:
            # At least one of the new weights is set
            kw = kw if kw is not None else 0.4
            vw = vw if vw is not None else 0.6
            total = kw + vw
            if total > 0:
                self.keyword_weight = kw / total
                self.vector_weight = vw / total
            else:
                self.keyword_weight = 0.4
                self.vector_weight = 0.6
        elif hw is not None:
            # Backward compatibility: hybrid_weight -> vector_weight
            self.vector_weight = float(hw)
            self.keyword_weight = 1.0 - self.vector_weight
        else:
            # Default
            self.keyword_weight = 0.4
            self.vector_weight = 0.6
        
        # For backward compatibility with existing code
        self.text_weight = self.keyword_weight
        self.vector_weight = self.vector_weight  # redundant but clear
        
        # Query parser instance (optional)
        self.query_parser = None
        if self.query_parser_enabled and QUERY_PARSER_AVAILABLE:
            try:
                self.query_parser = QueryParser()
            except Exception as e:
                logger.warning(f"Failed to initialize QueryParser: {e}")
                self.query_parser = None
        
        # Reranker instance (optional)
        self.reranker = None
        if self.rerank_method != "none":
            reranker_config = {
                "reranker_enabled": True,
                "reranker_model": self.cross_encoder_model,
                "reranker_device": None,
                "reranker_max_length": 512,
            }
            try:
                self.reranker = create_reranker(reranker_config)
                if not self.reranker.is_available():
                    logger.warning("Reranker is enabled but not available; will skip reranking.")
                    self.reranker = None
            except Exception as e:
                logger.warning(f"Failed to initialize reranker: {e}")
                self.reranker = None
        
        self._conn = None
    
    def _get_connection(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze query using QueryParser if available, else fallback to simple tokenization.
        Returns dict with keys: keywords, phrases, query_type, etc.
        """
        if self.query_parser:
            try:
                analysis = self.query_parser.parse(query)
                # Convert to dict for compatibility
                return {
                    "keywords": analysis.keywords,
                    "phrases": analysis.phrases,
                    "query_type": analysis.query_type,
                    "original_query": query,
                    "analyzed": True
                }
            except Exception as e:
                logger.warning(f"QueryParser failed to analyze '{query}': {e}")
        
        # Fallback: treat whole query as keyword (simple tokenization)
        import re
        tokens = re.findall(r'\w+', query.lower())
        return {
            "keywords": tokens,
            "phrases": [query] if len(query.split()) > 1 else [],
            "query_type": "keyword",
            "original_query": query,
            "analyzed": False
        }
    
    def search(self, query: str, limit: int = 10) -> List[Tuple[MemoryChunk, float]]:
        """Perform hybrid search and return chunks with relevance scores."""
        logger.info(f"HybridSearch searching for '{query}' (limit={limit})")
        # Analyze query (enhanced hybrid search)
        query_analysis = self._analyze_query(query)
        # For now, keep using original query for FTS/vector; later we can adjust
        effective_query = query_analysis.get("original_query", query)
        query_type = query_analysis.get("query_type", "keyword")
        # Compute adaptive weights based on query type (OpenClaw-style fusion)
        text_weight = self.keyword_weight
        vector_weight = self.vector_weight
        # Adjust based on query type (simple heuristics)
        if query_type == "keyword":
            text_weight *= 1.5
            vector_weight *= 0.8
        elif query_type == "natural_language":
            text_weight *= 0.8
            vector_weight *= 1.5
        elif query_type == "phrase":
            # slight boost to both
            text_weight *= 1.2
            vector_weight *= 1.2
        # Normalize so sum = 1
        total = text_weight + vector_weight
        if total > 0:
            text_weight /= total
            vector_weight /= total
        else:
            text_weight = self.keyword_weight
            vector_weight = self.vector_weight
        
        conn = self._get_connection()
        # Step 1: Full-text search (BM25) using SQLite FTS5
        # Assume we have an FTS table named 'memory_fts'
        fts_scores = {}
        try:
            cur = conn.execute("""
                SELECT id, bm25(memory_fts) AS score
                FROM memory_fts
                WHERE memory_fts MATCH ?
                ORDER BY bm25(memory_fts)
                LIMIT ?
            """, (effective_query, limit * 2))
            rows = cur.fetchall()
            for row in rows:
                fts_scores[row['id']] = row['score']
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS search failed: {e}")
            # FTS table may not exist; treat all scores as zero
            pass
        
        # Step 2: Vector search
        vector_scores = {}
        try:
            # Use sqlite-vec for vector similarity
            cur = conn.execute("""
                SELECT id, distance
                FROM vec_memory
                WHERE vec_search(embedding, ?)
                ORDER BY distance
                LIMIT ?
            """, (self._text_to_vector(effective_query), limit * 2))
            rows = cur.fetchall()
            for row in rows:
                vector_scores[row['id']] = row['distance']
        except (sqlite3.OperationalError, AttributeError) as e:
            logger.warning(f"Vector search failed: {e}")
            # fallback: no vector scores
        
        # Combine scores
        all_ids = set(list(fts_scores.keys()) + list(vector_scores.keys()))
        scored = []
        for chunk_id in all_ids:
            fts_score = fts_scores.get(chunk_id, 0.0)
            vector_score = vector_scores.get(chunk_id, 0.0)
            # Normalize? For simplicity, just weight
            combined = text_weight * fts_score + vector_weight * (1.0 - vector_score)  # invert distance
            scored.append((chunk_id, combined))
        scored.sort(key=lambda x: x[1], reverse=True)
        top_ids = [id_ for id_, _ in scored[:limit]]
        # Create a mapping from id to combined score
        score_map = {chunk_id: score for chunk_id, score in scored}
        
        # Retrieve chunks
        chunks = []
        for chunk_id in top_ids:
            chunk = self._get_chunk_by_id(chunk_id)
            if chunk:
                chunks.append((chunk, score_map.get(chunk_id, 0.0)))
        return chunks
    
    def _text_to_vector(self, text: str) -> bytes:
        """Convert text to embedding blob (placeholder)."""
        # In real implementation, we would embed the query using same provider
        # For now return zero vector
        return b''
    
    def _get_chunk_by_id(self, chunk_id: str) -> Optional[MemoryChunk]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM memory_chunks WHERE id = ?", (chunk_id,))
        row = cur.fetchone()
        if row:
            return self._row_to_chunk(row)
        return None
    
    def _row_to_chunk(self, row) -> MemoryChunk:
        return MemoryChunk(
            id=row['id'],
            file_path=row['file_path'],
            start_line=row['start_line'],
            end_line=row['end_line'],
            text=row['text'],
            hash=row['hash'],
            embedding=row['embedding'],
            embedding_model=row['embedding_model'],
            embedding_dim=row['embedding_dim'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


class MemoryIndexManager:
    """Core manager for indexing, syncing, and retrieving memory chunks."""
    
    def __init__(self, workspace: Path, config: Dict[str, Any]):
        self.workspace = workspace
        self.config = config
        self.memory_dir = workspace / "memory"
        # Determine watch paths: default to memory directory
        watch_paths = config.get("watch_paths", ["memory"])
        self.watch_paths = [Path(p) if Path(p).is_absolute() else workspace / p for p in watch_paths]
        db_path_str = config.get("storage_path", workspace / "memory/vector/memory.db")
        self.db_path = Path(db_path_str)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Chunking configuration
        self.chunk_size = config.get("chunk_size", 20)
        self.chunk_overlap = config.get("chunk_overlap", 0)
        self.chunk_boundary = config.get("chunk_boundary", "line")
        self.semantic_boundary_threshold = config.get("semantic_boundary_threshold", 0.7)
        self.embedding_provider = EmbeddingProvider(config)
        self.hybrid_search = HybridSearch(self.db_path, config)
        self._setup_database()
    
    def _setup_database(self):
        """Initialize SQLite tables and sqlite‑vec extension."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable sqlite-vec extension if available
        if SQLITE_VEC_AVAILABLE:
            conn.enable_load_extension(True)
            conn.load_extension("vec")
            conn.enable_load_extension(False)
        
        # Create memory_chunks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL,
                hash TEXT NOT NULL,
                embedding BLOB,
                embedding_model TEXT,
                embedding_dim INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create FTS5 virtual table for full‑text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
            USING fts5(id UNINDEXED, text, content='memory_chunks', content_rowid='rowid')
        """)
        # Triggers to keep FTS in sync with content table
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_fts_ai AFTER INSERT ON memory_chunks BEGIN
                INSERT INTO memory_fts(rowid, id, text) VALUES (new.rowid, new.id, new.text);
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_fts_au AFTER UPDATE ON memory_chunks BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, id, text) VALUES('delete', old.rowid, old.id, old.text);
                INSERT INTO memory_fts(rowid, id, text) VALUES (new.rowid, new.id, new.text);
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memory_fts_ad AFTER DELETE ON memory_chunks BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, id, text) VALUES('delete', old.rowid, old.id, old.text);
            END;
        """)
        
        # File sync state for incremental indexing
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_sync_state (
                file_path TEXT PRIMARY KEY,
                last_modified REAL,
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create vec0 virtual table for vector search
        if SQLITE_VEC_AVAILABLE:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory
                USING vec0(
                    id,
                    embedding FLOAT32[?]
                )
            """, (self.embedding_provider.get_dimension("openai"),))
        
        conn.commit()
        conn.close()
    
    def _split_semantic(self, text: str, threshold: float = 0.7) -> List[tuple[int, int, str]]:
        """Split text into semantic units based on sentence similarity.
        
        Uses sentence embeddings and detects topic shifts where cosine similarity
        drops below threshold.
        
        Returns list of (start_line, end_line, unit_text).
        """
        # First split into sentences using the existing sentence boundary method
        sentences = self._split_by_boundary(text, "sentence")
        if len(sentences) <= 1:
            return sentences  # no need to split further
        
        # Extract sentence texts and line ranges
        sent_texts = [s[2] for s in sentences]
        # Compute embeddings for each sentence in batch
        embeddings = []
        try:
            # Use the same event‑loop pattern as index_file
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # Running loop detected, create a new loop for embedding to avoid deadlock
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    embeddings = new_loop.run_until_complete(
                        self.embedding_provider.embed(sent_texts, provider_name="sentence_transformer")
                    )
                finally:
                    new_loop.close()
                    asyncio.set_event_loop(loop)  # restore original loop
            except RuntimeError:
                # No running loop, create new one
                loop = asyncio.new_event_loop()
                try:
                    embeddings = loop.run_until_complete(
                        self.embedding_provider.embed(sent_texts, provider_name="sentence_transformer")
                    )
                finally:
                    loop.close()
        except Exception as e:
            logger.warning(f"Embedding failed in semantic chunking: {e}. Falling back to sentence units.")
            # Return sentences as units (no merging)
            return sentences
        
        # Compute cosine similarity between consecutive sentences
        # Use numpy for vector ops, but fallback to manual if not available
        try:
            import numpy as np
            numpy_available = True
        except ImportError:
            numpy_available = False
        
        units = []
        current_start_idx = 0
        current_lines = [sentences[0][2]]
        for i in range(1, len(sentences)):
            # compute cosine similarity between embeddings[i-1] and embeddings[i]
            if numpy_available:
                a = np.array(embeddings[i-1])
                b = np.array(embeddings[i])
                cosine = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
            else:
                # manual dot product and norm
                a = embeddings[i-1]
                b = embeddings[i]
                dot = sum(x * y for x, y in zip(a, b))
                norm_a = sum(x * x for x in a) ** 0.5
                norm_b = sum(y * y for y in b) ** 0.5
                cosine = dot / (norm_a * norm_b + 1e-10)
            
            if cosine < threshold:
                # boundary detected, finalize current unit
                unit_text = " ".join(current_lines)
                start_line = sentences[current_start_idx][0]
                end_line = sentences[i-1][1]
                units.append((start_line, end_line, unit_text))
                # start new unit
                current_start_idx = i
                current_lines = [sentences[i][2]]
            else:
                current_lines.append(sentences[i][2])
        # final unit
        unit_text = " ".join(current_lines)
        start_line = sentences[current_start_idx][0]
        end_line = sentences[-1][1]
        units.append((start_line, end_line, unit_text))
        return units

    def _split_by_boundary(self, text: str, boundary: str) -> List[tuple[int, int, str]]:
        """Split text into units according to boundary.
        
        Returns list of (start_line, end_line, unit_text).
        Start and end lines are 0‑based inclusive.
        """
        lines = text.splitlines()
        if boundary == "line":
            # Each line is a unit
            units = []
            for i, line in enumerate(lines):
                units.append((i, i, line))
            return units
        elif boundary == "paragraph":
            # Paragraphs are separated by blank lines (one or more empty lines)
            units = []
            current_start = 0
            current_lines = []
            for i, line in enumerate(lines):
                if line.strip() == "":
                    if current_lines:
                        unit_text = "\n".join(current_lines)
                        units.append((current_start, i - 1, unit_text))
                        current_lines = []
                        current_start = i + 1
                    else:
                        current_start = i + 1  # skip consecutive empty lines
                else:
                    current_lines.append(line)
            # trailing paragraph
            if current_lines:
                unit_text = "\n".join(current_lines)
                units.append((current_start, len(lines) - 1, unit_text))
            return units
        elif boundary == "sentence":
            # Simple sentence splitting by punctuation followed by whitespace
            import re
            # Combine lines into single string with preserved line breaks
            full_text = text  # original with line breaks
            # Split by sentence boundaries (. ! ?) followed by whitespace or end
            pattern = r'(?<=[.!?])\s+'
            sentences = re.split(pattern, full_text)
            # Map each sentence to line range (approximation)
            units = []
            line_pos = 0  # current line index
            char_pos = 0  # character position in full_text
            for sent in sentences:
                if not sent.strip():
                    continue
                # Find start and end line of this sentence
                sent_start = full_text.find(sent, char_pos)
                if sent_start == -1:
                    # fallback: assign to current line
                    units.append((line_pos, line_pos, sent.strip()))
                    char_pos += len(sent)
                    continue
                sent_end = sent_start + len(sent)
                # Count newlines up to sent_start and sent_end
                start_line = full_text.count('\n', 0, sent_start)
                end_line = full_text.count('\n', 0, sent_end)
                units.append((start_line, end_line, sent.strip()))
                char_pos = sent_end
            return units
        elif boundary == "semantic":
            # Use semantic similarity clustering
            return self._split_semantic(text, self.semantic_boundary_threshold)
        else:
            # fallback to line
            return [(i, i, line) for i, line in enumerate(lines)]
    
    def index_file(self, file_path: Path) -> int:
        """Index a single memory file (full reindex). Returns number of chunks."""
        if not file_path.exists():
            logger.warning(f"File {file_path} does not exist")
            return 0
        
        # Read file content
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return 0
        
        # Split into units according to boundary
        units = self._split_by_boundary(text, self.chunk_boundary)
        chunks = []
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap
        if overlap >= chunk_size:
            overlap = chunk_size - 1  # prevent zero or negative step
        step = chunk_size - overlap
        for i in range(0, len(units), step):
            chunk_units = units[i:i+chunk_size]
            # Merge unit texts
            chunk_text = "\n".join([unit[2] for unit in chunk_units])
            if not chunk_text.strip():
                continue
            # Compute overall line range
            start_line = chunk_units[0][0] if chunk_units else 0
            end_line = chunk_units[-1][1] if chunk_units else 0
            chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()
            chunk_id = f"{file_path.relative_to(self.workspace)}_{start_line}_{end_line}"
            chunks.append({
                "id": chunk_id,
                "file_path": str(file_path.relative_to(self.workspace)),
                "start_line": start_line,
                "end_line": end_line,
                "text": chunk_text,
                "hash": chunk_hash,
            })
        
        # Embed chunks (batch)
        logger.info(f"Embedding {len(chunks)} chunks...")
        texts = [chunk["text"] for chunk in chunks]
        try:
            # Check if an event loop is already running
            loop = asyncio.get_running_loop()
            # Loop is already running, we cannot call run_until_complete.
            # Create a new loop for embedding to avoid deadlock.
            logger.info(f"Running loop detected, using new loop for embedding")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                embeddings = new_loop.run_until_complete(self.embedding_provider.embed(texts))
            finally:
                new_loop.close()
                asyncio.set_event_loop(loop)  # restore original loop
        except RuntimeError:
            # No running loop, create new one
            logger.info(f"No running loop, creating new event loop for embedding")
            loop = asyncio.new_event_loop()
            try:
                embeddings = loop.run_until_complete(self.embedding_provider.embed(texts))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            embeddings = [None] * len(chunks)
        logger.info(f"Embedding completed, got {len(embeddings)} vectors")
        
        # Insert into database
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        count = 0
        for idx, chunk in enumerate(chunks):
            embedding = embeddings[idx] if idx < len(embeddings) else None
            embedding_blob = self._embedding_to_blob(embedding) if embedding is not None else None
            conn.execute("""
                INSERT OR REPLACE INTO memory_chunks (id, file_path, start_line, end_line, text, hash, embedding, embedding_model, embedding_dim)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk["id"],
                chunk["file_path"],
                chunk["start_line"],
                chunk["end_line"],
                chunk["text"],
                chunk["hash"],
                embedding_blob,
                self.embedding_provider.fallback_chain[0],
                self.embedding_provider.get_dimension(self.embedding_provider.fallback_chain[0]),
            ))
            count += 1
        conn.commit()
        conn.close()
        
        logger.info(f"Indexed {count} chunks from {file_path}")
        return count
    
    def index_all(self) -> int:
        """Index all memory files across watch paths."""
        total = 0
        for md_file in self._collect_md_files():
            total += self.index_file(md_file)
        return total
    
    def _collect_md_files(self) -> List[Path]:
        """Collect all .md files from watch paths."""
        files = []
        for watch_path in self.watch_paths:
            if watch_path.is_dir():
                for md_file in watch_path.rglob("*.md"):
                    files.append(md_file)
            else:
                # treat as glob pattern (not implemented, fallback to dir)
                if watch_path.exists() and watch_path.is_file() and watch_path.suffix == ".md":
                    files.append(watch_path)
        return files

    def _should_reindex(self, file_path: Path) -> bool:
        """Return True if file has been modified since last indexed."""
        if not file_path.exists():
            return False
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT last_modified, last_indexed FROM file_sync_state WHERE file_path = ?",
            (str(file_path.relative_to(self.workspace)),)
        )
        row = cur.fetchone()
        conn.close()
        if row is None:
            return True  # never indexed
        last_modified_db = row['last_modified']
        # Compare with file's last modification time
        file_mtime = file_path.stat().st_mtime
        return file_mtime > last_modified_db

    def sync_incremental(self) -> int:
        """Incremental sync based on file modification times."""
        total = 0
        for md_file in self._collect_md_files():
            if self._should_reindex(md_file):
                logger.info(f"Reindexing {md_file} (modified)")
                total += self.index_file(md_file)
                # Update sync state
                conn = sqlite3.connect(self.db_path)
                conn.execute(
                    "INSERT OR REPLACE INTO file_sync_state (file_path, last_modified, last_indexed) VALUES (?, ?, ?)",
                    (str(md_file.relative_to(self.workspace)), md_file.stat().st_mtime, datetime.now(timezone.utc))
                )
                conn.commit()
                conn.close()
        return total

    def remove_file(self, file_path: Path):
        """Remove all chunks belonging to a file from the index."""
        if not file_path.exists():
            # file already gone, still remove from index
            pass
        rel_path = str(file_path.relative_to(self.workspace))
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM memory_chunks WHERE file_path = ?", (rel_path,))
            conn.execute("DELETE FROM file_sync_state WHERE file_path = ?", (rel_path,))
            conn.commit()
            logger.info(f"Removed {rel_path} from vector index")
        except Exception as e:
            logger.error(f"Failed to remove {rel_path}: {e}")
        finally:
            conn.close()
    
    def search(self, query: str, limit: int = 5, hybrid: bool = True) -> List[Dict[str, Any]]:
        """Search memory with optional hybrid retrieval and fallback to keyword search."""
        # First try hybrid search if enabled
        results = []
        if hybrid:
            results = self.hybrid_search.search(query, limit=limit)
        else:
            # Simple vector search only (placeholder)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM memory_chunks WHERE text LIKE ? LIMIT ?", (f"%{query}%", limit))
            rows = cur.fetchall()
            results = [(self._row_to_chunk(row), 1.0) for row in rows]
            conn.close()
        
        # Fallback chain: if results are insufficient, try keyword-only search
        min_results = 2  # threshold
        if len(results) < min_results:
            logger.info(f"Hybrid search returned only {len(results)} results, falling back to keyword search")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM memory_chunks 
                WHERE text LIKE ? 
                ORDER BY length(text)  -- prefer shorter, more relevant chunks
                LIMIT ?
            """, (f"%{query}%", limit))
            rows = cur.fetchall()
            fallback_results = [(self._row_to_chunk(row), 0.5) for row in rows]  # lower confidence
            conn.close()
            # Combine results, avoid duplicates
            existing_ids = {chunk.id for chunk, _ in results}
            for chunk, score in fallback_results:
                if chunk.id not in existing_ids:
                    results.append((chunk, score))
                    existing_ids.add(chunk.id)
            # Keep top by score
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:limit]
        
        return [
            {
                "chunk": chunk.to_dict(),
                "score": score,
            }
            for chunk, score in results
        ]
    
    def _embedding_to_blob(self, embedding: List[float]) -> bytes:
        """Convert list of floats to binary blob."""
        return struct.pack(f'{len(embedding)}f', *embedding)
    
    def _row_to_chunk(self, row) -> MemoryChunk:
        return MemoryChunk(
            id=row['id'],
            file_path=row['file_path'],
            start_line=row['start_line'],
            end_line=row['end_line'],
            text=row['text'],
            hash=row['hash'],
            embedding=row['embedding'],
            embedding_model=row['embedding_model'],
            embedding_dim=row['embedding_dim'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


class VectorMemoryAdapter:
    """Adapter for integrating vector memory into Cyberclaw's memory system."""
    
    def __init__(self, workspace: Path, config: Dict[str, Any]):
        self.workspace = workspace
        self.config = config
        self.enabled = config.get("enabled", False)
        self.manager = None
        self.watcher = None
        if self.enabled:
            try:
                self.manager = MemoryIndexManager(workspace, config)
                # initialize file watcher if watch paths are configured
                watch_paths = config.get("watch_paths", [])
                if watch_paths:
                    from .file_watcher import FileWatcher
                    self.watcher = FileWatcher(
                        watch_paths=[str(p) for p in watch_paths],
                        workspace=self.workspace,
                        callback=self._on_file_change,
                        poll_interval=config.get("watch_interval", 5.0)
                    )
            except Exception as e:
                logger.error(f"Failed to initialize vector memory: {e}")
                self.enabled = False
    
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Semantic search interface."""
        if not self.enabled or not self.manager:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.manager.search(query, limit=limit))
    
    def sync(self, full: bool = False) -> bool:
        """Trigger indexing sync."""
        if not self.enabled or not self.manager:
            return False
        try:
            if full:
                self.manager.index_all()
            else:
                self.manager.sync_incremental()
            return True
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
    
    def _on_file_change(self, file_path: Path):
        """Callback for file watcher events."""
        if not self.enabled or not self.manager:
            return
        if file_path.exists():
            logger.info(f"File modified: {file_path}")
            try:
                self.manager.index_file(file_path)
                logger.info(f"Indexed {file_path}")
            except Exception as e:
                logger.error(f"Failed to index {file_path}: {e}")
        else:
            logger.info(f"File deleted: {file_path}")
            try:
                self.manager.remove_file(file_path)
                logger.info(f"Removed {file_path} from index")
            except Exception as e:
                logger.error(f"Failed to remove {file_path}: {e}")

    def start(self):
        """Start file watcher if configured."""
        if self.enabled and self.watcher:
            self.watcher.start()
            logger.info("Vector memory file watcher started")

    def stop(self):
        """Stop file watcher."""
        if self.enabled and self.watcher:
            self.watcher.stop()
            logger.info("Vector memory file watcher stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return status of vector memory."""
        if not self.enabled:
            return {"enabled": False}
        conn = sqlite3.connect(self.manager.db_path)
        cur = conn.execute("SELECT COUNT(*) FROM memory_chunks")
        count = cur.fetchone()[0]
        conn.close()
        return {"enabled": True, "indexed_chunks": count}