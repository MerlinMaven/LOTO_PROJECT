"""
Video adapter — Phase 4 extension point.

Full implementation will extract keyframes then apply the ImageAdapter pipeline.
"""

from __future__ import annotations

from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.models.generation_job import InputSourceType


class VideoAdapter(DocumentAdapter):
    """
    Extracts machine knowledge from maintenance procedure videos.
    Phase 4 stub — not yet implemented.
    """

    @property
    def supported_type(self) -> InputSourceType:
        return InputSourceType.VIDEO

    async def extract(self, source: bytes | str, *, label: str = "video") -> ExtractedDocument:
        raise NotImplementedError(
            "Video extraction is planned for Phase 4. "
            "It will sample keyframes and apply ImageAdapter to each frame, "
            "then aggregate descriptions for the KnowledgeExtractor."
        )
