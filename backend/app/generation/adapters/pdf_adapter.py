"""
PDF adapter — Phase 3 extension point.

Full implementation requires `pypdf` or `PyMuPDF`.
Install with: pip install pypdf
"""

from __future__ import annotations

from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.models.generation_job import InputSourceType


class PDFAdapter(DocumentAdapter):
    """
    Extracts text from PDF documents.

    Phase 3 stub: raises NotImplementedError until pypdf is added to deps.
    To activate: install pypdf, then replace the body of `extract`.
    """

    @property
    def supported_type(self) -> InputSourceType:
        return InputSourceType.PDF

    async def extract(self, source: bytes | str, *, label: str = "document.pdf") -> ExtractedDocument:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            raise NotImplementedError(
                "PDF extraction requires 'pypdf'. "
                "Add it to requirements/base.txt and run pip install."
            )

        import io
        import hashlib

        if isinstance(source, str):
            source = source.encode()

        reader = pypdf.PdfReader(io.BytesIO(source))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

        content = "\n\n".join(pages)
        if not content.strip():
            raise ValueError(f"PDF '{label}' yielded no extractable text.")

        return ExtractedDocument(
            source_type=InputSourceType.PDF,
            content=content,
            content_hash=hashlib.sha256(source).hexdigest(),
            source_label=label,
            page_count=len(reader.pages),
        )
