"""
SmartLOTO Authoring Service — Schémas Pydantic.
Contrats de données échangés avec le dashboard HSE (React/Vite).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from pydantic import BaseModel, Field
from pydantic import ConfigDict

T = TypeVar("T")

class _UTCModel(BaseModel):
    """Base model that serializes all datetime fields with explicit 'Z' UTC suffix."""
    model_config = ConfigDict(json_encoders={
        datetime: lambda dt: (
            dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            if dt.tzinfo is None
            else dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )
    })


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    page_size: int


# ── Procédures & Versions ─────────────────────────────────────────────────────

class ApprovalRead(_UTCModel):
    id: str
    version_id: str
    reviewer_id: str
    decision: str
    notes: Optional[str] = None
    created_at: datetime
    approved_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    is_superseded: bool = False


class ApprovalCreatePayload(BaseModel):
    version_id: Optional[str] = None
    decision: Literal["approved", "rejected"]
    notes: Optional[str] = None
    approved_by: Optional[str] = None


class ProcedureVersionRead(_UTCModel):
    id: str
    procedure_id: str
    version_number: int
    status: str
    workflow_definition: Dict[str, Any]
    created_by: str
    created_at: datetime
    approvals: List[ApprovalRead] = []
    generation_source: str = "manual"
    llm_model_used: Optional[str] = None
    schema_version: str = "1.0"
    validation_errors: Optional[List[str]] = None
    submitted_for_review_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    latest_approval: Optional[ApprovalRead] = None


class DraftUpdatePayload(BaseModel):
    workflow_definition: Dict[str, Any]
    notes: Optional[str] = None


class ResolveClarificationPayload(_UTCModel):
    clarification_id: str
    answer: str
    rationale: Optional[str] = "Décision HSE validée"
    step_id: Optional[str] = None


class ProcedureListItem(_UTCModel):
    id: str
    machine_id: str
    machine_name: str  # kept for backward compat
    title: str
    created_by: Optional[str] = None
    status: str  # kept for backward compat
    current_status: str
    current_version_id: Optional[str] = None
    current_version_number: int = 1
    version_number: int = 1  # kept for backward compat
    generation_source: str = "manual"
    overall_confidence: Optional[float] = None
    open_validation_errors: int = 0
    has_published_version: bool = False
    workflow_definition: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ProcedureRead(_UTCModel):
    id: str
    machine_id: str
    machine_name: str
    status: str
    active_version_id: Optional[str] = None
    versions: List[ProcedureVersionRead] = []
    created_at: datetime
    updated_at: datetime
    title: Optional[str] = None
    created_by: Optional[str] = None
    active_version: Optional[ProcedureVersionRead] = None
    review_version: Optional[ProcedureVersionRead] = None


class ProcedurePublishResponse(_UTCModel):
    procedure_id: str
    published_version_id: str
    deprecated_version_id: Optional[str] = None
    published_at: datetime
    published_by: Optional[str] = None


# ── Génération LLM ────────────────────────────────────────────────────────────

# ── Interventions & Monitoring ────────────────────────────────────────────────

class InterventionSummary(_UTCModel):
    id: str
    machine_id: str
    procedure_version_id: Optional[str] = None
    operator_name: str
    status: str
    current_step_ref: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    aborted_at: Optional[datetime] = None
    abort_reason: Optional[str] = None
    pdf_report_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedInterventions(BaseModel):
    data: List[InterventionSummary]
    total: int
    page: int
    page_size: int


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEventRead(_UTCModel):
    id: str
    event_type: str
    actor_id: str
    machine_id: Optional[str] = None
    procedure_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    created_at: datetime
    occurred_at: Optional[datetime] = None
