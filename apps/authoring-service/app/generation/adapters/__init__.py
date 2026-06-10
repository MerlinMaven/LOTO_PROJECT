from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.adapters.text_adapter import TextAdapter
from app.generation.adapters.pdf_adapter import PDFAdapter
from app.generation.adapters.image_adapter import ImageAdapter
from app.generation.adapters.video_adapter import VideoAdapter

__all__ = [
    "DocumentAdapter", "ExtractedDocument",
    "TextAdapter", "PDFAdapter", "ImageAdapter", "VideoAdapter",
]
