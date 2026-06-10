"""
Machine repository — database access for Machine and MachineComponent.

No business logic. Every method is a query or a write.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.machine import Machine, MachineComponent
from app.repositories.base import BaseRepository


class MachineRepository(BaseRepository[Machine]):
    def __init__(self, session) -> None:
        super().__init__(Machine, session)

    async def get_with_components(self, machine_id: UUID) -> Machine | None:
        stmt = (
            select(Machine)
            .where(Machine.id == machine_id)
            .options(selectinload(Machine.components))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_internal_code(
        self, internal_code: str, site_id: UUID | None = None
    ) -> Machine | None:
        stmt = select(Machine).where(Machine.internal_code == internal_code)
        if site_id is not None:
            stmt = stmt.where(Machine.site_id == site_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(
        self, *, page: int = 1, page_size: int = 20, site_id: UUID | None = None
    ) -> tuple[list[Machine], int]:
        filters: dict = {"is_active": True}
        if site_id:
            filters["site_id"] = site_id
        return await self.list(page=page, page_size=page_size, filters=filters)

    async def add_component(self, component: MachineComponent) -> MachineComponent:
        self.session.add(component)
        await self.session.flush()
        await self.session.refresh(component)
        return component

    async def get_component(self, component_id: UUID) -> MachineComponent | None:
        return await self.session.get(MachineComponent, component_id)

    async def list_components(
        self, machine_id: UUID, *, active_only: bool = True
    ) -> list[MachineComponent]:
        stmt = select(MachineComponent).where(MachineComponent.machine_id == machine_id)
        if active_only:
            stmt = stmt.where(MachineComponent.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())
