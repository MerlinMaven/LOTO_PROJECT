"""
AuditEvent Pydantic v2 schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import AppBaseModel


class AuditEventRead(AppBaseModel):
    id: UUID
    event_type: str
    actor_id: str | None
    machine_id: UUID | None
    intervention_id: UUID | None
    procedure_version_id: UUID | None
    step_ref: str | None
    payload: dict
    ip_address: str | None
    occurred_at: datetime
    event_hash: str


class AuditFilters(AppBaseModel):
    """Query parameters for the audit log endpoint."""
    machine_id: UUID | None = None
    intervention_id: UUID | None = None
    procedure_version_id: UUID | None = None
    event_type: str | None = None
    actor_id: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
