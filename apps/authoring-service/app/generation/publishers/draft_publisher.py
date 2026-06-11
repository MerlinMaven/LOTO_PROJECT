"""
DraftPublisher — stores a GenerationResult as a draft_pending_review procedure.

Integrates with ProcedureService.create_draft() from Phase 2.
Generated procedures are ALWAYS stored with status=draft_pending_review.
Human approval is mandatory before activation.

The publisher also embeds YOLO metadata and generation provenance into the
workflow_definition so that the HSE reviewer has full context.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from app.core.logging import get_logger
from app.domain.enums import GenerationSource
from app.generation.models.generation_job import GenerationResult, GenerationJobStatus
from app.schemas.procedure import ProcedureCreate
from app.services.procedure_service import ProcedureService

logger = get_logger(__name__)


class DraftPublisher:
    """
    Converts GenerationResult into a ProcedureCreate and calls ProcedureService.

    Responsibilities:
    - Reject GenerationResults with blocking errors (is_publishable=False)
    - Embed YOLO metadata and generation notes into the workflow_definition
    - Call ProcedureService.create_draft() with the correct GenerationSource
    - Record the resulting procedure_version_id back onto the GenerationJob
    - Emit an audit log entry
    """

    def __init__(self, procedure_service: ProcedureService) -> None:
        self._svc = procedure_service

    async def publish(
        self,
        result: GenerationResult,
        *,
        machine_id: uuid.UUID,
        procedure_title: str,
        actor_id: str,
        ip_address: Optional[str] = None,
    ):
        """
        Publish the GenerationResult as a draft procedure.

        Raises ValueError if the validation report contains errors.
        Returns ProcedureRead from ProcedureService.create_draft().
        """
        if not result.validation_report.is_publishable:
            error_codes = [e.code for e in result.validation_report.errors]
            raise ValueError(
                f"Cannot publish procedure: validation errors present "
                f"({', '.join(error_codes)}). "
                "Fix the generation errors before storing."
            )

        enriched_workflow = self._embed_metadata(result)

        # Map LLM model used to GenerationSource enum
        llm_model = result.machine_knowledge.extraction_metadata.llm_model_used
        source = self._infer_generation_source(llm_model)

        payload = ProcedureCreate(
            machine_id=machine_id,
            title=procedure_title,
            created_by=actor_id,
            workflow_definition=enriched_workflow,
            generation_source=source,
            llm_model_used=llm_model,
        )

        logger.info(
            "draft_publisher_storing",
            job_id=result.job.job_id,
            machine_id=str(machine_id),
            actor=actor_id,
            source=source,
            warning_count=result.validation_report.warning_count,
        )

        procedure_read = await self._svc.create_draft(
            payload,
            actor_id=actor_id,
            ip_address=ip_address,
        )

        result.job.status = GenerationJobStatus.COMPLETED
        # versions[0] may be empty before commit; fall back gracefully
        if procedure_read.versions:
            result.job.procedure_version_id = str(procedure_read.versions[0].id)

        logger.info(
            "draft_publisher_stored",
            job_id=result.job.job_id,
            procedure_id=str(procedure_read.id),
            version_id=result.job.procedure_version_id,
        )

        return procedure_read

    @staticmethod
    def _embed_metadata(result: GenerationResult) -> dict:
        """
        Embed YOLO metadata and generation notes into workflow_definition.

        The extra keys are stored under `_generation_metadata` so they do
        not conflict with the canonical schema and can be stripped before
        AR headset delivery.
        """
        workflow = dict(result.workflow_definition)
        workflow["_generation_metadata"] = {
            "knowledge_id": result.machine_knowledge.knowledge_id,
            "llm_model": result.machine_knowledge.extraction_metadata.llm_model_used,
            "prompt_version": result.machine_knowledge.extraction_metadata.prompt_version,
            "generator_version": result.machine_knowledge.extraction_metadata.generator_version,
            "overall_confidence": result.machine_knowledge.mean_confidence,
            "yolo_metadata": result.yolo_metadata,
            "generation_notes": result.generation_notes,
            "validation_warnings": [
                {"code": w.code, "message": w.message}
                for w in result.validation_report.warnings
            ],
        }
        return workflow

    @staticmethod
    def _infer_generation_source(llm_model: str) -> GenerationSource:
        if llm_model.startswith("stub"):
            return GenerationSource.MANUAL
        if "gpt" in llm_model or "openai" in llm_model:
            return GenerationSource.LLM_TEXT
        if "claude" in llm_model or "anthropic" in llm_model:
            return GenerationSource.LLM_TEXT
        return GenerationSource.LLM_TEXT
