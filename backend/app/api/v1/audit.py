"""
Audit endpoints.

GET /api/v1/audit   Query the audit trail with flexible filters.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuditSvcDep
from app.schemas.audit import AuditEventRead, AuditFilters
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AuditEventRead])
async def get_audit_events(
    audit_svc: AuditSvcDep,
    machine_id: UUID | None = Query(None),
    intervention_id: UUID | None = Query(None),
    procedure_version_id: UUID | None = Query(None),
    event_type: str | None = Query(None),
    actor_id: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditEventRead]:
    """
    Query the immutable audit trail.

    All parameters are optional filters. Results are ordered by `occurred_at DESC`.

    Supports OSHA-style traceability: filter by machine_id + date range to
    produce a compliance report for a specific period.
    """
    filters = AuditFilters(
        machine_id=machine_id,
        intervention_id=intervention_id,
        procedure_version_id=procedure_version_id,
        event_type=event_type,
        actor_id=actor_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    return await audit_svc.get_events(filters)
