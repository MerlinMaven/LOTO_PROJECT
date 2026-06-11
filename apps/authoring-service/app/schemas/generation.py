"""
Request / response schemas for the generation API.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerationRunRequest(BaseModel):
    """Trigger the generation pipeline from a text description."""

    machine_id: str = Field(
        ...,
        description="Target machine identifier (must exist in the machines table).",
        examples=["COMPRESSEUR_A1"],
    )
    machine_name: str = Field(
        ...,
        examples=["Compresseur Ligne A1"],
    )
    components: str = Field(
        ...,
        description="Free-text list of physical energy sources to isolate (one per line).",
        examples=["Main electrical breaker (black)\nRed padlock on electrical moraillon\nPressure discharge valve (red)"],
    )
    requested_by: str = Field(
        ...,
        description="HSE engineer username initiating the generation.",
        examples=["w.serraji"],
    )
    source_type: Literal["text", "image"] = Field(
        "text",
        description="'text' for text-only generation, 'image' for multimodal (requires image_base64).",
    )
    image_base64: str | None = Field(
        None,
        description="Base64-encoded machine photo. Required when source_type='image'.",
    )
    provider: Literal["openrouter", "mistral", "groq", "vllm", "stub"] = Field(
        "openrouter",
        description=(
            "LLM provider to use. "
            "'openrouter' uses OPENROUTER_API_KEY, "
            "'mistral' uses MISTRAL_API_KEY, "
            "'groq' uses GROQ_API_KEY, "
            "'vllm' uses VLLM_BASE_URL (self-hosted), "
            "'stub' requires no key."
        ),
    )


class ValidationIssueSummary(BaseModel):
    code: str
    message: str
    severity: str
    field_path: str | None = None


class GenerationRunResponse(BaseModel):
    """Result of a generation pipeline run."""

    job_id: str
    status: str
    is_publishable: bool
    workflow_definition: dict
    yolo_metadata: dict
    validation_errors: list[ValidationIssueSummary]
    validation_warnings: list[ValidationIssueSummary]
    generation_notes: list[str]
    llm_provider: str | None
    error_message: str | None = None
    procedure_id: str | None = None
