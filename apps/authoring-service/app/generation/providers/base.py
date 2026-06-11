"""
LLM Provider abstraction.

All providers implement the same interface.
Swapping OpenAI for Claude (or vice versa) requires changing exactly one
line in GenerationService — the provider injection.

The LLM layer is purely responsible for completing prompts.
It does NOT parse, validate, or interpret responses — that is
the KnowledgeExtractor's job.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from app.compat import StrEnum
from typing import Optional, Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    SYSTEM    = "system"
    USER      = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: MessageRole
    content: Any


class LLMResponse(BaseModel):
    """Raw response from an LLM provider."""
    content: str = Field(..., description="The text completion returned by the model.")
    model_id: str = Field(..., description="The model identifier used.")
    provider: str = Field(..., description="Provider name: openai | claude | stub | ...")
    prompt_tokens: int = Field(0, ge=0)
    completion_tokens: int = Field(0, ge=0)
    latency_ms: float = Field(0.0, ge=0.0, description="Wall-clock latency in milliseconds.")
    finish_reason: str = Field("stop", description="stop | length | content_filter | error")

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMProvider(ABC):
    """
    Interface for LLM completion providers.

    Each implementation wraps one external API.
    All implementations must handle:
    - Authentication (API keys from config, never hardcoded)
    - Retry / rate-limit logic
    - Timeout
    - Provider-specific error translation to LLMProviderError
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging and audit."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model ID to use when none is specified."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """
        Send messages and return the completion.

        Args:
            messages:        Ordered list of system/user/assistant messages.
            model:           Override default model. None = use default_model.
            temperature:     0.0 = deterministic, 1.0 = creative. Use 0.1 for
                             structured extraction to maximise reproducibility.
            max_tokens:      Maximum tokens in the completion.
            response_format: "json_object" to request structured JSON output
                             (supported by OpenAI and Claude).
        """

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return (time.perf_counter() - start) * 1000


class LLMProviderError(Exception):
    """Raised when an LLM provider returns an error or unexpected response."""

    def __init__(self, provider: str, message: str, raw_response: str = "") -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.raw_response = raw_response
