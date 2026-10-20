"""
SmartLOTO Authoring Service — Schémas Pydantic.
Contrats de données échangés avec le dashboard HSE (React/Vite).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    page_size: int


# ── Procédures & Versions ─────────────────────────────────────────────────────

class ApprovalRead(BaseModel):
    id: str
    version_id: str
    reviewer_id: str
    decision: str
    notes: Optional[str] = None
    created_at: datetime


class ApprovalCreatePayload(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: Optional[str] = None


class ProcedureVersionRead(BaseModel):
    id: str
    procedure_id: str
    version_number: int
    status: str
    workflow_definition: Dict[str, Any]
    created_by: str
    created_at: datetime
    approvals: List[ApprovalRead] = []


class DraftUpdatePayload(BaseModel):
    workflow_definition: Dict[str, Any]
    notes: Optional[str] = None


class ProcedureListItem(BaseModel):
    id: str
    machine_id: str
    machine_name: str
    status: str
    version_number: int = 1
    created_at: datetime
    updated_at: datetime


class ProcedureRead(BaseModel):
    id: str
    machine_id: str
    machine_name: str
    status: str
    active_version_id: Optional[str] = None
    versions: List[ProcedureVersionRead] = []
    created_at: datetime
    updated_at: datetime


class ProcedurePublishResponse(BaseModel):
    procedure_id: str
    published_version_id: str
    deprecated_version_id: Optional[str] = None
    published_at: datetime


# ── Génération LLM ────────────────────────────────────────────────────────────

class GenerationRunRequest(BaseModel):
    machine_id: str
    machine_name: str
    components: str
    requested_by: str = "hse_user@smartloto.io"
    source_type: Literal["text", "image"] = "text"
    image_base64: Optional[str] = None
    provider: Literal["openrouter", "mistral", "groq", "vllm", "stub"] = "stub"


class ValidationIssueSummary(BaseModel):
    code: str
    message: str
    severity: str
    field_path: Optional[str] = None


class GenerationRunResponse(BaseModel):
    job_id: str
    status: str
    is_publishable: bool
    workflow_definition: Dict[str, Any]
    yolo_metadata: Dict[str, Any] = {}
    validation_errors: List[ValidationIssueSummary] = []
    validation_warnings: List[ValidationIssueSummary] = []
    generation_notes: List[str] = []
    llm_provider: Optional[str] = None
    error_message: Optional[str] = None
    procedure_id: Optional[str] = None


# ── Interventions & Monitoring ────────────────────────────────────────────────

class InterventionSummary(BaseModel):
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

class AuditEventRead(BaseModel):
    id: str
    event_type: str
    actor_id: str
    machine_id: Optional[str] = None
    procedure_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    created_at: datetime
