"""
AuditEvent repository.

CRITICAL: This repository only contains INSERT and SELECT operations.
No UPDATE. No DELETE. Ever.
The DB-level enforcement (PostgreSQL RULE) is in the Alembic migration.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from app.models.audit import AuditEvent
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    def __init__(self, session) -> None:
        super().__init__(AuditEvent, session)

    async def insert_event(self, event: AuditEvent) -> AuditEvent:
        """The only write operation allowed on audit_events."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self,
        *,
        machine_id: UUID | None = None,
        intervention_id: UUID | None = None,
        procedure_version_id: UUID | None = None,
        event_type: str | None = None,
        actor_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditEvent], int]:
        stmt = select(AuditEvent)

        if machine_id is not None:
            stmt = stmt.where(AuditEvent.machine_id == machine_id)
        if intervention_id is not None:
            stmt = stmt.where(AuditEvent.intervention_id == intervention_id)
        if procedure_version_id is not None:
            stmt = stmt.where(AuditEvent.procedure_version_id == procedure_version_id)
        if event_type is not None:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if actor_id is not None:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if from_date is not None:
            stmt = stmt.where(AuditEvent.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(AuditEvent.occurred_at <= to_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(AuditEvent.occurred_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_intervention_trail(
        self, intervention_id: UUID
    ) -> list[AuditEvent]:
        """Full ordered audit trail for a single intervention."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.intervention_id == intervention_id)
            .order_by(AuditEvent.occurred_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
