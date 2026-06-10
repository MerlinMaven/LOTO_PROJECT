"""
Procedure, ProcedureVersion, and ProcedureApproval Pydantic v2 schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain.enums import ApprovalDecision, GenerationSource, ProcedureStatus
from app.schemas.common import AppBaseModel


# ── ProcedureApproval ─────────────────────────────────────────────────────────

class ApprovalCreate(AppBaseModel):
    decision: ApprovalDecision
    notes: str | None = Field(None, max_length=2000)
    approved_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User identifier (email or UUID). Replaced by JWT subject in Phase 3.",
    )


class ApprovalRead(AppBaseModel):
    id: UUID
    version_id: UUID
    approved_by: str
    decision: ApprovalDecision
    notes: str | None
    decided_at: datetime
    is_superseded: bool


# ── ProcedureVersion ──────────────────────────────────────────────────────────

class ProcedureVersionCreate(AppBaseModel):
    """Payload to create a new draft version within an existing procedure."""
    version_number: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    generation_source: GenerationSource = GenerationSource.MANUAL
    llm_model_used: str | None = Field(
        None, description="LLM model identifier — populated by Phase 2 LLM service."
    )
    workflow_definition: dict = Field(
        ...,
        description="Canonical LOTO workflow JSON. Must conform to schema_version 1.0.",
    )
    created_by: str = Field(..., min_length=1, max_length=255)


class ProcedureVersionRead(AppBaseModel):
    id: UUID
    procedure_id: UUID
    version_number: str
    status: ProcedureStatus
    generation_source: GenerationSource
    llm_model_used: str | None
    schema_version: str
    workflow_definition: dict
    validation_errors: list[str] | None
    created_by: str
    submitted_for_review_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_approval: ApprovalRead | None = None


class ProcedureVersionSummary(AppBaseModel):
    """Lightweight version summary for embedding in ProcedureRead."""
    id: UUID
    version_number: str
    status: ProcedureStatus
    created_by: str
    created_at: datetime


# ── Procedure (envelope) ──────────────────────────────────────────────────────

class ProcedureCreate(AppBaseModel):
    """
    Creates both the Procedure envelope and its first draft ProcedureVersion
    in a single atomic operation.
    """
    machine_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    created_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User identifier — replaced by JWT subject in Phase 3.",
    )
    # First version content
    workflow_definition: dict = Field(
        ...,
        description="Canonical LOTO workflow JSON conforming to schema v1.0.",
    )
    generation_source: GenerationSource = GenerationSource.MANUAL
    llm_model_used: str | None = None

    @field_validator("workflow_definition")
    @classmethod
    def must_be_non_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("workflow_definition cannot be an empty object.")
        return v


class ProcedureRead(AppBaseModel):
    id: UUID
    machine_id: UUID
    title: str
    created_by: str
    active_version_id: UUID | None
    created_at: datetime
    updated_at: datetime
    versions: list[ProcedureVersionSummary] = Field(default_factory=list)
    active_version: ProcedureVersionRead | None = None


class ProcedurePublishResponse(AppBaseModel):
    procedure_id: UUID
    published_version_id: UUID
    deprecated_version_id: UUID | None
    published_at: datetime


# ── HSE Review Dashboard (Phase 4) ────────────────────────────────────────────

class DraftUpdate(AppBaseModel):
    """
    Payload to edit the workflow_definition of the current draft version.

    The dashboard sends the full edited workflow_definition (phases + the
    embedded `_generation_metadata` block). Components, workflow steps, and
    vision prompts all live inside this single document, so one endpoint
    covers every edit surface in the review screens.

    Only `draft_pending_review` versions can be edited. Approved / published /
    archived versions are immutable (ApprovedProcedureImmutableError).
    """
    workflow_definition: dict = Field(
        ...,
        description="Full edited canonical workflow JSON, including _generation_metadata.",
    )
    edited_by: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="HSE reviewer identifier — replaced by JWT subject later.",
    )
    edit_summary: str | None = Field(
        None,
        max_length=2000,
        description="Optional human note describing what was changed in this save.",
    )

    @field_validator("workflow_definition")
    @classmethod
    def must_be_non_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("workflow_definition cannot be an empty object.")
        return v


class ProcedureListItem(AppBaseModel):
    """
    Lightweight row for the dashboard home list.

    `current_status` is the status of the procedure's most recent version —
    the version that needs the reviewer's attention. `overall_confidence` is
    read from the embedded generation metadata when present (AI drafts).
    """
    id: UUID
    machine_id: UUID
    title: str
    created_by: str
    current_status: ProcedureStatus
    current_version_id: UUID
    current_version_number: str
    generation_source: GenerationSource
    overall_confidence: float | None = None
    open_validation_errors: int = 0
    has_published_version: bool = False
    created_at: datetime
    updated_at: datetime
