"""Text adapter — wraps a plain string as an ExtractedDocument."""

from __future__ import annotations

from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.models.generation_job import InputSourceType


class TextAdapter(DocumentAdapter):
    """
    Accepts raw text (machine description, manual notes, etc.).
    No parsing needed — the text is the content.
    """

    @property
    def supported_type(self) -> InputSourceType:
        return InputSourceType.TEXT

    async def extract(self, source: bytes | str, *, label: str = "text_input") -> ExtractedDocument:
        if isinstance(source, bytes):
            text = source.decode("utf-8", errors="replace")
        else:
            text = source
        if not text.strip():
            raise ValueError("TextAdapter received empty content.")
        return ExtractedDocument.from_text(text, label=label)
