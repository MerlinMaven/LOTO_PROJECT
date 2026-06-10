"""
Intervention repository — database access for Intervention and InterventionStep.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.enums import InterventionStatus
from app.models.intervention import Intervention, InterventionStep
from app.repositories.base import BaseRepository


class InterventionRepository(BaseRepository[Intervention]):
    def __init__(self, session) -> None:
        super().__init__(Intervention, session)

    async def get_active_for_machine(self, machine_id: UUID) -> Intervention | None:
        """Return the currently active (pending/in_progress/paused) intervention."""
        stmt = (
            select(Intervention)
            .where(
                Intervention.machine_id == machine_id,
                Intervention.status.in_([
                    InterventionStatus.PENDING,
                    InterventionStatus.IN_PROGRESS,
                    InterventionStatus.PAUSED,
                ]),
            )
            .options(selectinload(Intervention.steps))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_with_steps(self, intervention_id: UUID) -> Intervention | None:
        stmt = (
            select(Intervention)
            .where(Intervention.id == intervention_id)
            .options(
                selectinload(Intervention.steps),
                selectinload(Intervention.machine),
                selectinload(Intervention.procedure_version),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_machine(
        self, machine_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Intervention], int]:
        return await self.list(
            page=page,
            page_size=page_size,
            filters={"machine_id": machine_id},
        )

    async def list_for_operator(
        self, operator_name: str, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Intervention], int]:
        return await self.list(
            page=page,
            page_size=page_size,
            filters={"operator_name": operator_name},
        )

    async def add_step(self, step: InterventionStep) -> InterventionStep:
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def get_step(
        self, intervention_id: UUID, step_ref: str
    ) -> InterventionStep | None:
        stmt = select(InterventionStep).where(
            InterventionStep.intervention_id == intervention_id,
            InterventionStep.step_ref == step_ref,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_incomplete_steps(self, intervention_id: UUID) -> int:
        from sqlalchemy import func as sqlfunc
        from app.domain.enums import StepStatus
        stmt = select(sqlfunc.count(InterventionStep.id)).where(
            InterventionStep.intervention_id == intervention_id,
            InterventionStep.status.notin_([
                StepStatus.VALIDATED, StepStatus.OVERRIDDEN, StepStatus.SKIPPED
            ]),
        )
        return (await self.session.execute(stmt)).scalar_one()
