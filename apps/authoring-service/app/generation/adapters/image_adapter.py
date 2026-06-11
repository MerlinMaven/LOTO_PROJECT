"""
Image adapter — Phase 4 extension point (Implemented!).

Converts machine images into text descriptions via multimodal LLM.
"""

from __future__ import annotations

import base64

from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.models.generation_job import InputSourceType
from app.generation.providers.base import LLMProvider, Message, MessageRole


class ImageAdapter(DocumentAdapter):
    """
    Converts machine images into text descriptions via multimodal LLM.
    """

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    @property
    def supported_type(self) -> InputSourceType:
        return InputSourceType.IMAGE

    async def extract(self, source: bytes | str, *, label: str = "image") -> ExtractedDocument:
        if isinstance(source, bytes):
            base64_img = base64.b64encode(source).decode("utf-8")
        else:
            base64_img = source
            
        # Ensure it doesn't have the data URL prefix if it was passed cleanly, but in run_generation we decode it to bytes so it will be bytes.
        
        messages = [
            Message(
                role=MessageRole.USER,
                content=[
                    {
                        "type": "text", 
                        "text": "Tu es un expert en sécurité industrielle (HSE). Analyse cette photo de machine et décris tous les composants visibles qui sont pertinents pour une procédure de consignation (LOTO) : sources d'énergie, organes de coupure, points de condamnation, et cibles de maintenance. Liste-les de manière détaillée."
                    },
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                    }
                ]
            )
        ]

        response = await self._provider.complete(
            messages=messages,
            # We use a free vision model available on OpenRouter
            model="qwen/qwen-2.5-vl-72b-instruct:free",
            temperature=0.1
        )

        return ExtractedDocument(
            raw_text=response.content,
            metadata={"label": label, "vlm_analysis": True}
        )
