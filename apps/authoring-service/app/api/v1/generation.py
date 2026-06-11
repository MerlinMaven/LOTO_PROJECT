"""
Generation API — POST /api/v1/generation/run

Triggers the LLM-powered LOTO procedure generation pipeline.
Supported providers: openrouter (default), mistral, groq, vllm, stub.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DBDep, MachineSvcDep, ProcedureSvcDep
from app.core.logging import get_logger
from app.generation.models.generation_job import InputSourceType
from app.generation.providers.stub_provider import StubLLMProvider
from app.generation.publishers.draft_publisher import DraftPublisher
from app.generation.service import GenerationService
from app.schemas.generation import GenerationRunRequest, GenerationRunResponse, ValidationIssueSummary
from app.schemas.machine import MachineCreate

logger = get_logger(__name__)

router = APIRouter()


def _build_provider(provider_name: str):
    """Instantiate the requested LLM provider from env settings."""
    from app.core.config import get_settings
    settings = get_settings()

    if provider_name == "openrouter":
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="OPENROUTER_API_KEY is not set in .env.",
            )
        try:
            from app.generation.providers.openrouter_provider import OpenRouterProvider
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="openai package not installed. Run: pip install openai>=1.0.0",
            )
        return OpenRouterProvider(
            api_key=api_key,
            default_model=settings.OPENROUTER_MODEL,
        )

    if provider_name == "mistral":
        api_key = settings.MISTRAL_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MISTRAL_API_KEY is not set in .env.",
            )
        try:
            from app.generation.providers.mistral_provider import MistralProvider
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mistralai package not installed. Run: pip install mistralai>=1.0.0",
            )
        return MistralProvider(api_key=api_key, default_model=settings.MISTRAL_MODEL)

    if provider_name == "groq":
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="GROQ_API_KEY is not set in .env.",
            )
        try:
            from app.generation.providers.groq_provider import GroqProvider
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="openai package not installed. Run: pip install openai>=1.0.0",
            )
        return GroqProvider(api_key=api_key, default_model=settings.GROQ_MODEL)

    if provider_name == "vllm":
        base_url = settings.VLLM_BASE_URL
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="VLLM_BASE_URL is not set in .env. Point it to your vLLM server (e.g. http://localhost:8000/v1).",
            )
        try:
            from app.generation.providers.vllm_provider import VLLMProvider
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="openai package not installed. Run: pip install openai>=1.0.0",
            )
        return VLLMProvider(base_url=base_url, model=settings.VLLM_MODEL)

    # stub — no key required
    return StubLLMProvider()


def _build_vision_provider():
    """
    Return the best available vision-capable provider for image analysis.
    Priority: vllm (self-hosted) → openrouter (qwen-vl free tier).
    """
    from app.core.config import get_settings
    settings = get_settings()

    if settings.VLLM_BASE_URL:
        from app.generation.providers.vllm_provider import VLLMProvider
        return VLLMProvider(base_url=settings.VLLM_BASE_URL, model=settings.VLLM_MODEL)

    if settings.OPENROUTER_API_KEY:
        from app.generation.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            api_key=settings.OPENROUTER_API_KEY,
            default_model="qwen/qwen-2.5-vl-72b-instruct:free",
        )

    return StubLLMProvider()


@router.post(
    "/generation/run",
    response_model=GenerationRunResponse,
    summary="Run the LOTO procedure generation pipeline",
    description=(
        "Accepts machine metadata and a text description or image of energy sources. "
        "Runs the full generation pipeline: knowledge extraction → procedure generation → validation. "
        "Saves the result as a draft_pending_review procedure. "
        "Supported providers: openrouter (default), mistral, groq, vllm, stub."
    ),
    status_code=status.HTTP_200_OK,
)
async def run_generation(
    data: GenerationRunRequest,
    user: CurrentUserDep,
    machine_svc: MachineSvcDep,
    procedure_svc: ProcedureSvcDep,
    request: Request,
) -> GenerationRunResponse:
    text_provider = _build_provider(data.provider)

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

    # For image source, wire in the best available vision provider for the ImageAdapter
    adapters = None
    if source_type == InputSourceType.IMAGE:
        from app.generation.adapters.image_adapter import ImageAdapter
        vision_provider = _build_vision_provider()
        adapters = {InputSourceType.IMAGE: ImageAdapter(provider=vision_provider)}
        logger.info(
            "image_generation_vision_provider",
            vision_provider=vision_provider.provider_name,
        )

    gen_svc = GenerationService(provider=text_provider, adapters=adapters)

    result = await gen_svc.run(
        source=source,
        source_type=source_type,
        source_label=f"{data.machine_name} — {data.machine_id}",
        machine_id=data.machine_id,
        requested_by=data.requested_by,
    )

    # ── Persist to DB ─────────────────────────────────────────────────────────
    # Auto-upsert the machine by internal_code so the form works without
    # pre-registering machines. Creates on first use, reuses on repeat.
    # Pre-check for existing procedure to avoid raising domain exceptions that
    # would be intercepted by the global exception handler before our catch.
    from app.domain.enums import GenerationSource
    from app.models.procedure import ProcedureVersion
    from app.domain.enums import ProcedureStatus

    procedure_id: str | None = None
    try:
        ip = request.client.host if request.client else None

        machine = await machine_svc.repo.get_by_internal_code(data.machine_id)
        if machine is None:
            machine_data = MachineCreate(
                internal_code=data.machine_id,
                name=data.machine_name,
            )
            machine = await machine_svc.create_machine(
                machine_data, actor_id=user.identifier
            )

        procedure_title = f"{data.machine_id} - {data.machine_name}"
        enriched = DraftPublisher._embed_metadata(result)
        llm_model = result.machine_knowledge.extraction_metadata.llm_model_used

        # Pre-check: if machine already has a procedure, add a new version
        existing = await procedure_svc.repo.get_by_machine_id(machine.id)
        if existing is None:
            # First generation for this machine — create procedure + first version
            publisher = DraftPublisher(procedure_svc)
            saved = await publisher.publish(
                result,
                machine_id=machine.id,
                procedure_title=procedure_title,
                actor_id=user.identifier,
                ip_address=ip,
            )
            procedure_id = str(saved.id)
        else:
            # Machine already has a procedure — append a new draft version
            next_minor = len(existing.versions or []) + 1
            version = ProcedureVersion(
                procedure_id=existing.id,
                version_number=f"1.{next_minor}.0",
                status=ProcedureStatus.DRAFT_PENDING_REVIEW,
                generation_source=GenerationSource.LLM_TEXT,
                llm_model_used=llm_model,
                workflow_definition=enriched,
                created_by=user.identifier,
            )
            await procedure_svc.repo.create_version(version)
            procedure_id = str(existing.id)

        logger.info("generation_saved_as_draft", procedure_id=procedure_id)
    except Exception as exc:
        # Never let a save failure hide the generation result from the user
        logger.warning("generation_save_failed", error=str(exc), exc_info=True)

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
        procedure_id=procedure_id,
    )
