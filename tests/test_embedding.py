#!/usr/bin/env python3
"""Test embedding provider without asyncio loop."""
import sys
sys.path.insert(0, '.')

from cyberclaw.agent.memory_vector import EmbeddingProvider
import asyncio

async def test():
    config = {
        "embedding_fallback_chain": ["sentence_transformer", "none"],
    }
    provider = EmbeddingProvider(config)
    texts = ["Hello world", "This is a test"]
    embeddings = await provider.embed(texts)
    print(f"Got {len(embeddings)} embeddings")
    for i, emb in enumerate(embeddings):
        print(f"  {i}: length {len(emb)}")

if __name__ == "__main__":
    asyncio.run(test())