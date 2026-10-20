"""
SmartLOTO Authoring Service — API Interventions (supervision côté console HSE).
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Intervention
from app.schemas import InterventionSummary, PaginatedInterventions

router = APIRouter()


@router.get("", response_model=PaginatedInterventions)
async def list_interventions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Intervention)
    if status:
        stmt = stmt.where(Intervention.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    stmt = stmt.order_by(Intervention.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    items = list(res.scalars().all())

    summaries = [
        InterventionSummary(
            id=item.id,
            machine_id=item.machine_id,
            operator_name=item.operator_name,
            status=item.status,
            current_step_ref=f"Étape {item.current_stage_id}",
            started_at=item.started_at,
            completed_at=item.completed_at,
            pdf_report_url=item.pdf_report_url,
            created_at=item.started_at,
            updated_at=item.completed_at or item.started_at,
        )
        for item in items
    ]

    return PaginatedInterventions(
        data=summaries,
        total=total,
        page=page,
        page_size=page_size,
    )
