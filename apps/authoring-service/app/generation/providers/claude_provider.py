"""
Anthropic Claude provider.

Requires: pip install anthropic>=0.30.0
Add ANTHROPIC_API_KEY to .env.
"""

from __future__ import annotations

import time
from typing import Optional

from app.generation.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    Message,
    MessageRole,
)


class ClaudeProvider(LLMProvider):
    """
    Calls the Anthropic Messages API.

    Claude is instructed to return JSON via a prefill technique:
    The last assistant turn starts with `{` to force JSON output.
    Recommended model: claude-sonnet-4-6 (production) or claude-haiku-4-5 (fast/cheap).
    """

    def __init__(self, api_key: str, default_model: str = "claude-sonnet-4-6") -> None:
        self._api_key = api_key
        self._default_model = default_model

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def default_model(self) -> str:
        return self._default_model

    async def complete(
        self,
        messages: list[Message],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        try:
            import anthropic
        except ImportError:
            raise LLMProviderError(
                self.provider_name,
                "anthropic package not installed. Run: pip install anthropic>=0.30.0",
            )

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        model_id = model or self._default_model

        # Anthropic API uses system prompt separately
        system = next((m.content for m in messages if m.role == MessageRole.SYSTEM), "")
        user_messages = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]

        # Prefill JSON when structured output requested
        if response_format == "json_object":
            user_messages.append({"role": "assistant", "content": "{"})

        t0 = time.perf_counter()
        try:
            kwargs: dict = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": user_messages,
            }
            if system:
                kwargs["system"] = system
            response = await client.messages.create(**kwargs)
        except Exception as exc:
            raise LLMProviderError(self.provider_name, str(exc)) from exc

        raw = response.content[0].text if response.content else ""

        # Re-attach the prefill `{` stripped by Anthropic
        if response_format == "json_object" and not raw.startswith("{"):
            raw = "{" + raw

        return LLMResponse(
            content=raw,
            model_id=model_id,
            provider=self.provider_name,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            latency_ms=self._elapsed_ms(t0),
            finish_reason=response.stop_reason or "stop",
        )
