"""
Mistral AI provider.

Requires: pip install mistralai>=1.0.0
Add MISTRAL_API_KEY to .env.
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


class MistralProvider(LLMProvider):
    """Calls the Mistral AI API."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "mistral-small-latest",
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model

    @property
    def provider_name(self) -> str:
        return "mistral"

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
            from mistralai.client import Mistral
        except ImportError:
            raise LLMProviderError(
                self.provider_name,
                "mistralai package not installed. Run: pip install mistralai>=1.0.0",
            )

        client = Mistral(api_key=self._api_key)
        model_id = model or self._default_model

        kwargs: dict = {
            "model": model_id,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.perf_counter()
        try:
            response = await client.chat.complete_async(**kwargs)
        except Exception as exc:
            raise LLMProviderError(self.provider_name, str(exc)) from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        if isinstance(content, list):
            content = " ".join(
                part.text if hasattr(part, "text") else str(part) for part in content
            )

        return LLMResponse(
            content=content,
            model_id=model_id,
            provider=self.provider_name,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            latency_ms=self._elapsed_ms(t0),
            finish_reason=str(choice.finish_reason) if choice.finish_reason else "stop",
        )
