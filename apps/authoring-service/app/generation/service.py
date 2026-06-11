"""
GenerationService — top-level orchestrator for the generation pipeline.

Pipeline:
  raw input (text/PDF/image/video)
    → DocumentAdapter.extract()       [normalise to text]
    → KnowledgeExtractor.extract()    [LLM call → MachineKnowledge]
    → YoloMetadataBuilder.build()     [enrich vision metadata]
    → ProcedureGenerator.generate()   [algorithmic LOTO generation]
    → ProcedureValidator.validate()   [safety + consistency checks]
    → GenerationResult

Optionally:
    → DraftPublisher.publish()        [store as draft_pending_review]

The service is stateless. All dependencies are injected.
Swapping a provider, adapter, or generator requires changing only the
instantiation site (api/deps.py or tests/conftest.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.generation.adapters.base import DocumentAdapter, ExtractedDocument
from app.generation.adapters.text_adapter import TextAdapter
from app.generation.adapters.image_adapter import ImageAdapter
from app.generation.extractors.knowledge_extractor import KnowledgeExtractor
from app.generation.generators.procedure_generator import ProcedureGenerator
from app.generation.models.generation_job import (
    GenerationJob,
    GenerationJobStatus,
    GenerationResult,
    InputSourceType,
)
from app.generation.providers.base import LLMProvider
from app.generation.prompts.renderer import PromptRenderer
from app.generation.prompts.repository import PromptTemplateRepository, get_prompt_repository
from app.generation.validators.procedure_validator import ProcedureValidator
from app.generation.yolo.metadata_builder import YoloMetadataBuilder

logger = get_logger(__name__)


class GenerationService:
    """
    Orchestrates the full procedure generation pipeline.

    Injection points (swap without touching this class):
    - provider: any LLMProvider implementation
    - adapters: dict mapping InputSourceType → DocumentAdapter
    - repository: PromptTemplateRepository (custom directory for tests)
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        adapters: Optional[dict[InputSourceType, DocumentAdapter]] = None,
        repository: Optional[PromptTemplateRepository] = None,
    ) -> None:
        self._provider = provider
        repo = repository or get_prompt_repository()
        renderer = PromptRenderer(repo)

        self._extractor = KnowledgeExtractor(provider, renderer)
        self._generator = ProcedureGenerator()
        self._validator = ProcedureValidator()
        self._yolo_builder = YoloMetadataBuilder()

        # Default adapters — extend by passing custom dict
        self._adapters: dict[InputSourceType, DocumentAdapter] = {
            InputSourceType.TEXT: TextAdapter(),
            InputSourceType.IMAGE: ImageAdapter(provider=self._provider),
            **(adapters or {}),
        }

    async def run(
        self,
        source: bytes | str,
        *,
        source_type: InputSourceType = InputSourceType.TEXT,
        source_label: str = "input",
        machine_id: Optional[str] = None,
        requested_by: str = "system",
    ) -> GenerationResult:
        """
        Execute the full generation pipeline.

        Args:
            source:       Raw input bytes or str.
            source_type:  InputSourceType for adapter selection.
            source_label: Human-readable label for logging.
            machine_id:   Optional DB machine reference.
            requested_by: User identifier for audit trail.

        Returns:
            GenerationResult ready for DraftPublisher or direct use in tests.
        """
        job = GenerationJob(
            input_source_type=source_type,
            input_summary=source_label,
            requested_by=requested_by,
            llm_provider=self._provider.provider_name,
        )

        logger.info(
            "generation_pipeline_started",
            job_id=job.job_id,
            source_type=source_type,
            provider=self._provider.provider_name,
        )

        # ── Step 1: Adapt input ───────────────────────────────────────────────
        job.status = GenerationJobStatus.EXTRACTING
        document = await self._adapt(source, source_type, label=source_label)

        # ── Step 2: Extract knowledge ─────────────────────────────────────────
        knowledge = await self._extractor.extract(document, machine_id=machine_id)
        job.llm_provider = self._provider.provider_name

        # ── Step 3: Enrich YOLO metadata ──────────────────────────────────────
        yolo_metadata = self._yolo_builder.build_for_knowledge(knowledge)

        # ── Step 4: Generate procedure ────────────────────────────────────────
        job.status = GenerationJobStatus.GENERATING
        workflow_definition, notes = self._generator.generate(knowledge)

        # ── Step 5: Validate ──────────────────────────────────────────────────
        job.status = GenerationJobStatus.VALIDATING
        validation_report = self._validator.validate(workflow_definition, knowledge)

        job.status = (
            GenerationJobStatus.COMPLETED
            if validation_report.is_publishable
            else GenerationJobStatus.FAILED
        )
        job.completed_at = datetime.now(timezone.utc)

        if not validation_report.is_publishable:
            job.error_message = (
                f"{validation_report.error_count} validation error(s): "
                + "; ".join(e.code for e in validation_report.errors)
            )

        logger.info(
            "generation_pipeline_completed",
            job_id=job.job_id,
            is_publishable=validation_report.is_publishable,
            error_count=validation_report.error_count,
            warning_count=validation_report.warning_count,
            phases=len(workflow_definition.get("phases", [])),
        )

        return GenerationResult(
            job=job,
            machine_knowledge=knowledge,
            workflow_definition=workflow_definition,
            yolo_metadata=yolo_metadata,
            validation_report=validation_report,
            generation_notes=notes,
        )

    async def _adapt(
        self,
        source: bytes | str,
        source_type: InputSourceType,
        label: str,
    ) -> ExtractedDocument:
        adapter = self._adapters.get(source_type)
        if adapter is None:
            raise NotImplementedError(
                f"No adapter registered for source type '{source_type}'. "
                f"Available: {list(self._adapters.keys())}"
            )
        return await adapter.extract(source, label=label)
