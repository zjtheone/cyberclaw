"""Query parser for hybrid search."""
import re
from typing import List, Optional
from .query_types import QueryAnalysis, Keyword, Phrase, IntentType


class QueryParser:
    """Parse user queries into keywords, phrases, and intent."""
    
    # Common stopwords (English)
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "can", "could", "may", "might", "must", "i", "you", "he",
        "she", "it", "we", "they", "me", "him", "her", "us", "them"
    }
    
    # Patterns
    PHRASE_PATTERN = r'"([^"]+)"'  # quoted phrases
    QUESTION_PATTERN = r'^(what|who|where|when|why|how|which)\b'
    
    def __init__(self, language: str = "en"):
        self.language = language
        
    def parse(self, query: str) -> QueryAnalysis:
        """Parse a raw query string."""
        query = query.strip()
        if not query:
            return QueryAnalysis(original_query=query, processed_text="")
        
        # Extract quoted phrases
        phrases = []
        for match in re.finditer(self.PHRASE_PATTERN, query):
            phrase_text = match.group(1)
            phrases.append(Phrase(
                text=phrase_text,
                start_pos=match.start(),
                end_pos=match.end()
            ))
        
        # Remove quoted parts from text to avoid double‑counting
        text_without_quotes = re.sub(self.PHRASE_PATTERN, "", query)
        
        # Tokenize (simple split on whitespace/punctuation)
        tokens = re.findall(r'\b\w+\b', text_without_quotes.lower())
        keywords = []
        for token in tokens:
            start = text_without_quotes.lower().find(token)
            end = start + len(token)
            is_stopword = token in self.STOPWORDS
            keywords.append(Keyword(
                text=token,
                start_pos=start,
                end_pos=end,
                is_stopword=is_stopword
            ))
        
        # Determine intent
        intent = self._detect_intent(query)
        
        # Build processed text (keywords + phrases)
        processed_parts = []
        if phrases:
            processed_parts.extend(p.text for p in phrases)
        if keywords:
            # Exclude stopwords from processed text for search
            non_stop_keywords = [k.text for k in keywords if not k.is_stopword]
            processed_parts.extend(non_stop_keywords)
        processed_text = " ".join(processed_parts)
        
        return QueryAnalysis(
            original_query=query,
            keywords=keywords,
            phrases=phrases,
            intent=intent,
            processed_text=processed_text
        )
    
    def _detect_intent(self, query: str) -> IntentType:
        """Heuristic intent detection."""
        lower = query.lower()
        if lower.startswith("how to") or "how do i" in lower or "step" in lower:
            return IntentType.PROCEDURAL
        if re.match(self.QUESTION_PATTERN, lower):
            return IntentType.FACTUAL
        if "what is" in lower or "define" in lower or "definition" in lower:
            return IntentType.DEFINITIONAL
        if any(word in lower for word in ["tell me", "explain", "describe"]):
            return IntentType.CONVERSATIONAL
        return IntentType.UNKNOWN