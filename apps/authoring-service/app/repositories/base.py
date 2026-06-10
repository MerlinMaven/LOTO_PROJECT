"""
Generic async repository base class.

Provides standard CRUD operations. Domain-specific repositories extend this
with their own query methods but must not contain any business logic.

The type parameter T is the SQLAlchemy model class.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: UUID) -> ModelT | None:
        result = await self.session.get(self.model, id)
        return result

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        stmt = select(self.model)
        if filters:
            for column, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, column) == value)

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Paginated rows
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def create(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def exists(self, id: UUID) -> bool:
        stmt = select(self.model.id).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
