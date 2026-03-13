"""Data classes for query analysis."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class IntentType(str, Enum):
    """Type of query intent."""
    FACTUAL = "factual"
    DEFINITIONAL = "definitional"
    PROCEDURAL = "procedural"
    CONVERSATIONAL = "conversational"
    UNKNOWN = "unknown"


@dataclass
class Keyword:
    """A single keyword token."""
    text: str
    start_pos: int
    end_pos: int
    is_stopword: bool = False


@dataclass
class Phrase:
    """A multi‑word phrase (e.g., inside quotes)."""
    text: str
    start_pos: int
    end_pos: int


@dataclass
class QueryAnalysis:
    """Result of parsing a user query."""
    original_query: str
    keywords: List[Keyword] = field(default_factory=list)
    phrases: List[Phrase] = field(default_factory=list)
    intent: IntentType = IntentType.UNKNOWN
    query_type: str = "keyword"
    processed_text: str = ""  # cleaned version for search