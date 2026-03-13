"""Unit tests for query_parser.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cyberclaw.agent.memory_processing.query_parser import QueryParser
from cyberclaw.agent.memory_processing.query_types import QueryAnalysis, Keyword, Phrase, IntentType


def test_parser_empty():
    """Empty query should return empty analysis."""
    parser = QueryParser()
    result = parser.parse("")
    assert result.original_query == ""
    assert result.processed_text == ""
    assert len(result.keywords) == 0
    assert len(result.phrases) == 0
    assert result.intent == IntentType.UNKNOWN


def test_parser_simple_keywords():
    """Simple keyword extraction."""
    parser = QueryParser()
    result = parser.parse("hello world")
    assert result.original_query == "hello world"
    assert len(result.keywords) == 2
    assert result.keywords[0].text == "hello"
    assert result.keywords[0].is_stopword is False
    assert result.keywords[1].text == "world"
    assert result.processed_text == "hello world"


def test_parser_stopwords():
    """Stopwords are identified and excluded from processed text."""
    parser = QueryParser()
    result = parser.parse("the quick brown fox")
    # "the" is a stopword
    assert any(k.text == "the" and k.is_stopword for k in result.keywords)
    # processed text should not contain "the"
    assert "the" not in result.processed_text
    assert "quick brown fox" in result.processed_text


def test_parser_phrases():
    """Quoted phrases are extracted."""
    parser = QueryParser()
    result = parser.parse('search for "exact phrase" and another')
    assert len(result.phrases) == 1
    phrase = result.phrases[0]
    assert phrase.text == "exact phrase"
    assert phrase.start_pos == 11  # position of opening quote
    assert phrase.end_pos == 25    # position after closing quote
    # phrase should appear in processed text
    assert "exact phrase" in result.processed_text
    # keywords should not contain words from phrase
    assert all(k.text != "exact" and k.text != "phrase" for k in result.keywords)


def test_parser_intent_factual():
    """Detect factual question intent."""
    parser = QueryParser()
    # "what is ..."
    result = parser.parse("what is the capital of France")
    assert result.intent == IntentType.FACTUAL
    # "who"
    result = parser.parse("who invented Python")
    assert result.intent == IntentType.FACTUAL
    # "where"
    result = parser.parse("where is Paris")
    assert result.intent == IntentType.FACTUAL


def test_parser_intent_procedural():
    """Detect procedural intent."""
    parser = QueryParser()
    result = parser.parse("how to install python")
    assert result.intent == IntentType.PROCEDURAL
    result = parser.parse("how do I fix this error")
    assert result.intent == IntentType.PROCEDURAL
    result = parser.parse("step by step guide")
    assert result.intent == IntentType.PROCEDURAL


def test_parser_intent_definitional():
    """Detect definitional intent."""
    parser = QueryParser()
    result = parser.parse("what is artificial intelligence")
    assert result.intent == IntentType.FACTUAL  # "what" triggers factual
    result = parser.parse("define machine learning")
    assert result.intent == IntentType.DEFINITIONAL
    result = parser.parse("definition of neural network")
    assert result.intent == IntentType.DEFINITIONAL


def test_parser_intent_conversational():
    """Detect conversational intent."""
    parser = QueryParser()
    result = parser.parse("tell me about the weather")
    assert result.intent == IntentType.CONVERSATIONAL
    result = parser.parse("explain quantum computing")
    assert result.intent == IntentType.CONVERSATIONAL
    result = parser.parse("describe the process")
    assert result.intent == IntentType.CONVERSATIONAL


def test_parser_mixed_phrase_keyword():
    """Mix of phrases and keywords."""
    parser = QueryParser()
    result = parser.parse('"deep learning" tutorial for beginners')
    assert len(result.phrases) == 1
    assert result.phrases[0].text == "deep learning"
    # Count non-stopword keywords (tutorial, beginners)
    non_stop_keywords = [k for k in result.keywords if not k.is_stopword]
    assert len(non_stop_keywords) == 2
    assert "deep learning tutorial beginners" in result.processed_text


def test_parser_case_insensitive():
    """Case insensitivity."""
    parser = QueryParser()
    result = parser.parse("THE QUICK BROWN FOX")
    # stopword "the" should be recognized regardless of case
    assert any(k.text == "the" and k.is_stopword for k in result.keywords)
    assert "the" not in result.processed_text.lower()


def test_parser_punctuation():
    """Punctuation handling."""
    parser = QueryParser()
    result = parser.parse("Hello, world! How's it going?")
    # punctuation should be stripped
    assert all(k.text.isalpha() for k in result.keywords)
    assert result.processed_text == "hello world how s going"


if __name__ == "__main__":
    test_parser_empty()
    print("✓ test_parser_empty")
    test_parser_simple_keywords()
    print("✓ test_parser_simple_keywords")
    test_parser_stopwords()
    print("✓ test_parser_stopwords")
    test_parser_phrases()
    print("✓ test_parser_phrases")
    test_parser_intent_factual()
    print("✓ test_parser_intent_factual")
    test_parser_intent_procedural()
    print("✓ test_parser_intent_procedural")
    test_parser_intent_definitional()
    print("✓ test_parser_intent_definitional")
    test_parser_intent_conversational()
    print("✓ test_parser_intent_conversational")
    test_parser_mixed_phrase_keyword()
    print("✓ test_parser_mixed_phrase_keyword")
    test_parser_case_insensitive()
    print("✓ test_parser_case_insensitive")
    test_parser_punctuation()
    print("✓ test_parser_punctuation")
    print("All tests passed!")