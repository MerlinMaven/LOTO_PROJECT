"""
Image adapter — Phase 4 extension point.

Full implementation will use a multimodal LLM (GPT-4V, Claude Vision)
to describe image contents before component extraction.
"""

from __future__ import annotations

from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.models.generation_job import InputSourceType


class ImageAdapter(DocumentAdapter):
    """
    Converts machine images into text descriptions via multimodal LLM.
    Phase 4 stub — not yet implemented.
    """

    @property
    def supported_type(self) -> InputSourceType:
        return InputSourceType.IMAGE

    async def extract(self, source: bytes | str, *, label: str = "image") -> ExtractedDocument:
        raise NotImplementedError(
            "Image extraction is planned for Phase 4. "
            "It will use a multimodal vision model to describe image contents "
            "before passing the description to the KnowledgeExtractor."
        )
