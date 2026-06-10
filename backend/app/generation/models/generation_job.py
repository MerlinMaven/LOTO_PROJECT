"""
GenerationJob and GenerationResult — pipeline tracking models.

GenerationJob records inputs and pipeline state.
GenerationResult is the successful output: validated MachineKnowledge +
generated workflow_definition + YOLO metadata + validation report.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from app.generation.models.machine_knowledge import MachineKnowledge


class GenerationJobStatus(StrEnum):
    PENDING     = "pending"
    EXTRACTING  = "extracting"    # LLM extraction in progress
    GENERATING  = "generating"    # Procedure generation in progress
    VALIDATING  = "validating"    # Validation checks running
    PUBLISHING  = "publishing"    # Writing to database
    COMPLETED   = "completed"
    FAILED      = "failed"


class InputSourceType(StrEnum):
    TEXT  = "text"
    PDF   = "pdf"
    IMAGE = "image"
    VIDEO = "video"


class GenerationJob(BaseModel):
    """Tracks a single pipeline execution from input to draft procedure."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: GenerationJobStatus = GenerationJobStatus.PENDING
    input_source_type: InputSourceType
    input_summary: str = Field(
        ...,
        description="Brief description of the input (filename, first 200 chars, etc.).",
    )
    requested_by: str = Field(
        ...,
        description="User identifier of whoever triggered the generation.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    llm_provider: Optional[str] = None
    prompt_version: Optional[str] = None
    procedure_version_id: Optional[str] = Field(
        None,
        description="Set after DraftPublisher stores the procedure in the database.",
    )


class ValidationIssue(BaseModel):
    """A single validation finding — error or warning."""
    code: str = Field(..., description="Machine-readable issue code.")
    message: str = Field(..., description="Human-readable description.")
    severity: str = Field(..., description="error | warning | info")
    field_path: Optional[str] = Field(
        None,
        description="Dot-notation path to the problematic field, if applicable.",
    )


class ValidationReport(BaseModel):
    """Summary of all validation findings for a generated procedure."""
    is_publishable: bool = Field(
        ...,
        description="True only when there are no errors (warnings are allowed).",
    )
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    infos: list[ValidationIssue] = Field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def all_issues(self) -> list[ValidationIssue]:
        return self.errors + self.warnings + self.infos


class GenerationResult(BaseModel):
    """
    The successful output of the generation pipeline.

    This is the input to DraftPublisher.
    It contains everything needed to create a ProcedureCreate
    and store it as draft_pending_review.
    """
    job: GenerationJob
    machine_knowledge: MachineKnowledge
    workflow_definition: dict = Field(
        ...,
        description="Canonical phases→stages→steps JSON ready for ProcedureVersion.",
    )
    yolo_metadata: dict = Field(
        default_factory=dict,
        description=(
            "component_id → ComponentVisionMetadata dict. "
            "Stored in step validation blocks for HSE review."
        ),
    )
    validation_report: ValidationReport
    generation_notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes about generation decisions.",
    )
