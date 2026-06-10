"""
Document Adapter abstraction.

The adapter layer normalises any input source into an ExtractedDocument,
which is a plain-text content blob the KnowledgeExtractor can send to the LLM.

Adding a new input format requires:
  1. Create a new class that inherits from DocumentAdapter.
  2. Register it in GenerationService.
  No other code changes needed (open/closed principle).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.generation.models.generation_job import InputSourceType


@dataclass
class ExtractedDocument:
    """
    Normalised representation of any input source.

    `content` is the primary text payload handed to the LLM.
    `content_hash` provides reproducibility — same input → same hash.
    `metadata` stores source-specific information (filename, page count, etc.).
    """
    source_type: InputSourceType
    content: str
    content_hash: str
    source_label: str = ""              # filename or short description
    page_count: Optional[int] = None    # PDF / video frames
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, label: str = "text_input") -> "ExtractedDocument":
        return cls(
            source_type=InputSourceType.TEXT,
            content=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            source_label=label,
        )


class DocumentAdapter(ABC):
    """
    Interface for all input source adapters.

    Each concrete adapter handles one InputSourceType.
    The `extract` method is the single entry point — it transforms raw
    input into an ExtractedDocument ready for the KnowledgeExtractor.
    """

    @property
    @abstractmethod
    def supported_type(self) -> InputSourceType:
        """The InputSourceType this adapter handles."""

    @abstractmethod
    async def extract(self, source: bytes | str, *, label: str = "") -> ExtractedDocument:
        """
        Extract text content from the raw source.

        Args:
            source: Raw bytes (PDF, image, video) or str (plain text).
            label:  Human-readable identifier for logging (filename, URL, etc.).

        Returns:
            ExtractedDocument with normalised text content.
        """
