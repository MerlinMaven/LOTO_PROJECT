"""
SmartLOTO Authoring Service — API Piste d'Audit.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventRead, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AuditEventRead])
async def query_audit(
    page: int = 1,
    page_size: int = 20,
    machine_id: Optional[str] = None,
    event_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditEvent)
    if machine_id:
        stmt = stmt.where(AuditEvent.machine_id == machine_id)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    stmt = stmt.order_by(AuditEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    items = list(res.scalars().all())

    read_items = [
        AuditEventRead(
            id=item.id,
            event_type=item.event_type,
            actor_id=item.actor_id,
            machine_id=item.machine_id,
            procedure_id=item.procedure_id,
            payload=item.payload or {},
            created_at=item.created_at,
            occurred_at=item.created_at,
        )
        for item in items
    ]

    return PaginatedResponse(
        data=read_items,
        total=total,
        page=page,
        page_size=page_size,
    )
