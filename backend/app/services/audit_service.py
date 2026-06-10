"""
AuditService — the single entry point for creating audit events.

All service methods that modify critical state MUST call record_event().
The audit trail is immutable once written.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from app.domain.enums import AuditEventType
from app.models.audit import AuditEvent
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventRead, AuditFilters
from app.schemas.common import PaginatedResponse


def _compute_event_hash(
    event_type: str,
    actor_id: str | None,
    payload: dict,
    occurred_at: datetime,
) -> str:
    """
    Deterministic SHA-256 hash over the event's immutable fields.
    Used for offline tamper detection: re-hash stored fields and compare.
    """
    data = {
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload,
        "occurred_at": occurred_at.isoformat(),
    }
    serialised = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()


class AuditService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self.repo = audit_repo

    async def record_event(
        self,
        event_type: AuditEventType | str,
        *,
        actor_id: str | None = None,
        machine_id: UUID | None = None,
        intervention_id: UUID | None = None,
        procedure_version_id: UUID | None = None,
        step_ref: str | None = None,
        payload: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Create and persist an immutable audit event."""
        resolved_payload = payload or {}
        now = datetime.now(timezone.utc)
        event_hash = _compute_event_hash(str(event_type), actor_id, resolved_payload, now)

        event = AuditEvent(
            event_type=str(event_type),
            actor_id=actor_id,
            machine_id=machine_id,
            intervention_id=intervention_id,
            procedure_version_id=procedure_version_id,
            step_ref=step_ref,
            payload=resolved_payload,
            ip_address=ip_address,
            event_hash=event_hash,
        )
        return await self.repo.insert_event(event)

    async def get_events(
        self, filters: AuditFilters
    ) -> PaginatedResponse[AuditEventRead]:
        events, total = await self.repo.list_events(
            machine_id=filters.machine_id,
            intervention_id=filters.intervention_id,
            procedure_version_id=filters.procedure_version_id,
            event_type=filters.event_type,
            actor_id=filters.actor_id,
            from_date=filters.from_date,
            to_date=filters.to_date,
            page=filters.page,
            page_size=filters.page_size,
        )
        return PaginatedResponse(
            data=[AuditEventRead.model_validate(e) for e in events],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def get_intervention_trail(
        self, intervention_id: UUID
    ) -> list[AuditEventRead]:
        events = await self.repo.get_intervention_trail(intervention_id)
        return [AuditEventRead.model_validate(e) for e in events]
