"""
Intervention and InterventionStep Pydantic v2 schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.domain.enums import InterventionStatus, StepStatus, ValidationMethod
from app.schemas.common import AppBaseModel


class InterventionStepRead(AppBaseModel):
    id: UUID
    intervention_id: UUID
    step_ref: str
    status: StepStatus
    validation_method_used: ValidationMethod | None
    ai_confidence_score: float | None
    override_reason: str | None
    evidence_url: str | None
    started_at: datetime | None
    completed_at: datetime | None
    attempts: int


class InterventionCreate(AppBaseModel):
    machine_id: UUID
    operator_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Operator identifier — will be replaced by JWT subject in Phase 3.",
    )


class InterventionRead(AppBaseModel):
    id: UUID
    machine_id: UUID
    procedure_version_id: UUID
    operator_name: str
    status: InterventionStatus
    current_step_ref: str | None
    started_at: datetime
    completed_at: datetime | None
    aborted_at: datetime | None
    abort_reason: str | None
    pdf_report_url: str | None
    operator_signature_url: str | None
    steps: list[InterventionStepRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InterventionAbortRequest(AppBaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class InterventionPauseRequest(AppBaseModel):
    reason: str | None = Field(None, max_length=500)


class InterventionProgress(AppBaseModel):
    """Summary of completion progress for an intervention."""
    intervention_id: UUID
    total_steps: int
    completed_steps: int
    overridden_steps: int
    failed_steps: int
    pending_steps: int
    completion_percentage: float


# ── Step action request bodies ────────────────────────────────────────────────

class StepValidationRequest(AppBaseModel):
    """Operator confirms a step has been performed (manual confirmation path)."""
    confirmed_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Identity of the person confirming this step.",
    )
    notes: str | None = Field(None, max_length=2000)


class StepRejectRequest(AppBaseModel):
    """Operator marks a step as failed and provides a rejection reason."""
    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Why this step could not be completed.",
    )


class StepOverrideRequest(AppBaseModel):
    """
    Manual override with documented evidence.

    Used when normal validation (vision/sensor) is not available OR when the
    operator deviates from the expected procedure. Every override is flagged
    for mandatory post-intervention HSE review by default.
    """
    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Justification for bypassing normal validation.",
    )
    evidence_url: str | None = Field(
        None,
        description="URL of the photo/document stored as evidence (e.g. Supabase Storage).",
    )
    photo_reference: str | None = Field(
        None,
        max_length=500,
        description="Operator-assigned reference for the captured photo (Phase 6: Quest).",
    )
    requires_hse_review: bool = Field(
        default=True,
        description="Flag this override for mandatory post-intervention HSE review.",
    )


# ── Step navigation / current step context ────────────────────────────────────

class CurrentStepContext(AppBaseModel):
    """
    Full context for the step currently being executed.

    Provides everything the runtime client (Quest / mobile) needs to render
    the current step without a second API call to parse the workflow JSON.
    """
    intervention_id: UUID
    intervention_status: InterventionStatus

    # Workflow position
    current_step_ref: str | None
    overall_step_number: int | None   # 1-based position in the entire workflow
    total_steps_overall: int

    # Step content (from workflow_definition)
    step_instruction: str | None
    step_validation_method: str | None
    safety_note: str | None
    warnings: list[str] = Field(default_factory=list)
    rollback_instruction: str | None

    # Location context (phase / stage)
    phase_id: str | None
    phase_type: str | None
    phase_title: str | None
    stage_id: str | None
    stage_title: str | None

    # Navigation
    previous_step_ref: str | None
    next_step_ref: str | None

    # DB record for this step (None if not yet entered)
    step_record: InterventionStepRead | None
