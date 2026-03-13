"""Direct OpenAI-compatible provider — bypasses LiteLLM."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import json_repair
from openai import AsyncOpenAI

from cyberclaw.providers.base import LLMProvider, LLMResponse, LLMStreamChunk, ToolCallRequest


class CustomProvider(LLMProvider):
    """Custom provider using OpenAI SDK directly for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str = "no-key",
        api_base: str = "http://localhost:8000/v1",
        default_model: str = "default",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        # Keep affinity stable for this provider instance to improve backend cache locality.
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            default_headers={"x-session-affinity": uuid.uuid4().hex},
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        reasoning_effort: str | None = None,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        """Non-streaming chat completion."""
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        try:
            return self._parse(await self._client.chat.completions.create(**kwargs))
        except Exception as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def _parse(self, response: Any) -> LLMResponse:
        """Parse OpenAI API response into our standard format."""
        choice = response.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCallRequest(
                id=tc.id,
                name=tc.function.name,
                arguments=json_repair.loads(tc.function.arguments)
                if isinstance(tc.function.arguments, str)
                else tc.function.arguments,
            )
            for tc in (msg.tool_calls or [])
        ]
        u = response.usage
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens,
            }
            if u
            else {},
            reasoning_content=getattr(msg, "reasoning_content", None) or None,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        thinking_budget: int = 0,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream a chat completion, yielding chunks as they arrive."""
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    # Usage-only chunk (final)
                    if hasattr(chunk, "usage") and chunk.usage:
                        yield LLMStreamChunk(
                            usage={
                                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                                "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                            }
                        )
                    continue

                delta = chunk.choices[0].delta
                finish = chunk.choices[0].finish_reason

                sc = LLMStreamChunk(finish_reason=finish)

                # Reasoning content (for models that support it)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    sc.reasoning_content = delta.reasoning_content

                # Text content
                if hasattr(delta, "content") and delta.content:
                    sc.delta_content = delta.content

                # Tool call deltas
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_chunk = LLMStreamChunk(finish_reason=finish)
                        tc_chunk.tool_call_index = tc.index if hasattr(tc, "index") else 0
                        if hasattr(tc, "id") and tc.id:
                            tc_chunk.tool_call_id = tc.id
                        if hasattr(tc, "function"):
                            if hasattr(tc.function, "name") and tc.function.name:
                                tc_chunk.tool_call_name = tc.function.name
                            if hasattr(tc.function, "arguments") and tc.function.arguments:
                                tc_chunk.tool_call_arguments_delta = tc.function.arguments
                        # Carry text content only on the first tool call chunk
                        if (
                            tc == delta.tool_calls[0]
                            and hasattr(delta, "content")
                            and delta.content
                        ):
                            tc_chunk.delta_content = sc.delta_content
                        yield tc_chunk
                    continue

                yield sc
        except Exception as e:
            yield LLMStreamChunk(
                delta_content=f"Error: {e}",
                finish_reason="error",
            )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
