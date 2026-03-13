from typing import Any
import asyncio

from cyberclaw.agent.tools.base import Tool
from cyberclaw.agent.memory import MemoryStore

class MemorySearchTool(Tool):
    """Tool for searching the agent's long-term vector memory."""
    
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return "Search your long-term memory for past conversations, scripts, facts, and context."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g., 'MongoDB backup script', 'user preferences')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5, max: 15)",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, limit: int = 5, **kwargs: Any) -> str:
        limit = min(max(1, limit), 15)
        
        if not self.memory_store.vector_memory or not self.memory_store.vector_memory.enabled:
            return "Vector memory search is currently disabled in the configuration."
            
        results = await self.memory_store.semantic_search(query, limit=limit)
        
        if not results:
            return f"No memories found matching '{query}'."
            
        output = [f"Found {len(results)} relevant memories for '{query}':\n"]
        
        for i, res in enumerate(results, 1):
            score = res.get("score", 0.0)
            chunk = res.get("chunk", {})
            text = chunk.get("text", "")
            file_path = chunk.get("file_path", "unknown")
            
            output.append(f"--- Result {i} (Score: {score:.3f}, File: {file_path}) ---")
            output.append(text)
            output.append("")
            
        return "\n".join(output)
