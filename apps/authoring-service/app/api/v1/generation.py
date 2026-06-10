"""
Generation API — POST /api/v1/generation/run

Triggers the LLM-powered LOTO procedure generation pipeline.
The result is returned immediately (synchronous) for the MVP.
Phase 3 will move this to a background task queue (Celery/ARQ).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUserDep, get_current_user
from app.core.logging import get_logger
from app.generation.models.generation_job import InputSourceType
from app.generation.providers.stub_provider import StubLLMProvider
from app.generation.service import GenerationService
from app.schemas.generation import GenerationRunRequest, GenerationRunResponse, ValidationIssueSummary

logger = get_logger(__name__)

router = APIRouter()


def _get_generation_service(provider_name: str) -> GenerationService:
    """Resolve the correct LLM provider from the request parameter."""
    if provider_name == "claude":
        try:
            from app.core.config import get_settings
            settings = get_settings()
            api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="ANTHROPIC_API_KEY is not configured. Use provider='stub' or set the key in .env.",
                )
            from app.generation.providers.claude_provider import ClaudeProvider
            provider = ClaudeProvider(api_key=api_key)
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="anthropic package not installed. Run: pip install anthropic>=0.30.0",
            )
    else:
        provider = StubLLMProvider()

    return GenerationService(provider=provider)


@router.post(
    "/generation/run",
    response_model=GenerationRunResponse,
    summary="Run the LOTO procedure generation pipeline",
    description=(
        "Accepts machine metadata and a text description of energy sources. "
        "Runs the full generation pipeline: knowledge extraction → procedure generation → validation. "
        "Returns the generated workflow_definition and validation report. "
        "Use provider='stub' (default) without an API key; use provider='claude' with ANTHROPIC_API_KEY set."
    ),
    status_code=status.HTTP_200_OK,
)
async def run_generation(
    data: GenerationRunRequest,
    user: CurrentUserDep,
) -> GenerationRunResponse:
    svc = _get_generation_service(data.provider)

    source_type = InputSourceType.TEXT
    source: bytes | str = data.components

    if data.source_type == "image":
        if not data.image_base64:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="image_base64 is required when source_type='image'.",
            )
        import base64
        try:
            raw = data.image_base64
            if "," in raw:
                raw = raw.split(",")[1]
            source = base64.b64decode(raw)
            source_type = InputSourceType.IMAGE
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid image_base64: {exc}",
            ) from exc

    logger.info(
        "generation_api_request",
        machine_id=data.machine_id,
        provider=data.provider,
        source_type=source_type,
        requested_by=data.requested_by,
    )

    result = await svc.run(
        source=source,
        source_type=source_type,
        source_label=f"{data.machine_name} — {data.machine_id}",
        machine_id=data.machine_id,
        requested_by=data.requested_by,
    )

    return GenerationRunResponse(
        job_id=result.job.job_id,
        status=result.job.status,
        is_publishable=result.validation_report.is_publishable,
        workflow_definition=result.workflow_definition,
        yolo_metadata=result.yolo_metadata,
        validation_errors=[
            ValidationIssueSummary(**e.model_dump())
            for e in result.validation_report.errors
        ],
        validation_warnings=[
            ValidationIssueSummary(**w.model_dump())
            for w in result.validation_report.warnings
        ],
        generation_notes=result.generation_notes,
        llm_provider=result.job.llm_provider,
        error_message=result.job.error_message,
    )
