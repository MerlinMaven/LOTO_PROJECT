"""
vLLM provider — self-hosted OpenAI-compatible endpoint.

Requires: pip install openai>=1.0.0
Set VLLM_BASE_URL (e.g. http://localhost:8000/v1) and VLLM_MODEL in .env.
Supports both text and vision (multimodal) models.
"""

from __future__ import annotations

import time
from typing import Optional

from app.generation.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    Message,
)


class VLLMProvider(LLMProvider):
    """Calls a self-hosted vLLM server (OpenAI-compatible)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return "vllm"

    @property
    def default_model(self) -> str:
        return self._model

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
            from openai import AsyncOpenAI
        except ImportError:
            raise LLMProviderError(
                self.provider_name,
                "openai package not installed. Run: pip install openai>=1.0.0",
            )

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        model_id = model or self._model

        # Messages may contain multimodal content (list of dicts) — pass through as-is
        serialized = []
        for m in messages:
            if isinstance(m.content, list):
                serialized.append({"role": m.role.value, "content": m.content})
            else:
                serialized.append({"role": m.role.value, "content": m.content})

        kwargs: dict = {
            "model": model_id,
            "messages": serialized,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.perf_counter()
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMProviderError(self.provider_name, str(exc)) from exc

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model_id=model_id,
            provider=self.provider_name,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            latency_ms=self._elapsed_ms(t0),
            finish_reason=choice.finish_reason or "stop",
        )
