"""Conversation compaction: summarize old context to free up token space."""

from typing import Any

from loguru import logger


class ConversationCompactor:
    """
    Compresses long conversations by summarizing old messages.

    Two-tier strategy:
    - Tier 1 (cheap): Truncate long tool outputs (existing _trim_context logic)
    - Tier 2 (smart): When context exceeds threshold, call LLM to summarize old messages
    """

    SUMMARY_PROMPT = (
        "Summarize the following conversation history concisely. "
        "Preserve: key decisions, file paths mentioned, errors encountered, "
        "current task state, and any important context the assistant needs. "
        "Be brief but complete — this summary replaces the original messages."
    )

    def __init__(self, provider: Any, model: str | None = None):
        self._provider = provider
        self._model = model

    async def compact(
        self,
        messages: list[dict[str, Any]],
        keep_recent: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Compact a conversation by summarizing old messages.

        Args:
            messages: Full message list (system + history + recent).
            keep_recent: Number of recent messages to preserve verbatim.

        Returns:
            Compacted message list with summary replacing old context.
        """
        # CRITICAL: Ensure tool results stay with their tool calls
        # Find split point that keeps tool_call + tool_result pairs together
        recent = messages[-keep_recent:]
        tool_call_ids_in_recent = {m.get("tool_call_id") for m in recent if m.get("role") == "tool"}
        
        # Scan backwards to find assistant messages with tool_calls referenced in recent
        split_point = len(messages) - keep_recent
        for i in range(len(messages) - keep_recent - 1, 0, -1):
            msg = messages[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                assistant_tool_ids = {tc.get("id") for tc in msg.get("tool_calls", [])}
                if assistant_tool_ids & tool_call_ids_in_recent:
                    # Must keep this assistant message to avoid orphaning tool results
                    split_point = i
                    break
        
        system = messages[0]  # Always preserve system prompt
        old = messages[1:split_point]
        kept_recent = messages[split_point:]

        if not old:
            return messages

        # Build summary request
        old_text = self._messages_to_text(old)
        if not old_text.strip():
            return messages

        summary = await self._generate_summary(old_text)
        if not summary:
            return messages

        # Reconstruct: system + summary + recent messages
        summary_msg = {
            "role": "user",
            "content": f"[Conversation summary — earlier messages were compacted]\n\n{summary}",
        }

        compacted = [system, summary_msg] + kept_recent
        old_chars = sum(len(str(m.get("content", ""))) for m in messages)
        new_chars = sum(len(str(m.get("content", ""))) for m in compacted)
        logger.info(f"Compacted conversation: {old_chars} -> {new_chars} chars ({len(old)} messages summarized)")

        return compacted

    async def _generate_summary(self, conversation_text: str) -> str | None:
        """Call LLM to generate a conversation summary."""
        try:
            summary_messages = [
                {"role": "system", "content": self.SUMMARY_PROMPT},
                {"role": "user", "content": conversation_text},
            ]
            response = await self._provider.chat(
                messages=summary_messages,
                model=self._model,
                max_tokens=2048,
                temperature=0.3,
            )
            return response.content
        except Exception as e:
            logger.error(f"Compaction summary failed: {e}")
            return None

    def _messages_to_text(self, messages: list[dict[str, Any]]) -> str:
        """Convert messages to a readable text format for summarization."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "tool":
                name = msg.get("name", "tool")
                # Truncate long tool outputs for the summary input
                if len(str(content)) > 500:
                    content = str(content)[:500] + "..."
                parts.append(f"[Tool: {name}] {content}")
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    tc_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
                    parts.append(f"Assistant: {content or ''} [called: {', '.join(tc_names)}]")
                else:
                    parts.append(f"Assistant: {content}")
            else:
                parts.append(f"{role.capitalize()}: {content}")

        return "\n".join(parts)
