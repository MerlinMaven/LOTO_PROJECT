"""
Procedure repository — database access for Procedure, ProcedureVersion, ProcedureApproval.

Key design notes:
- get_current_version returns the most recent non-archived, non-rejected version.
- get_active_version returns the PUBLISHED version pointed to by Procedure.active_version_id.
- No state transition logic here — that belongs to ProcedureService.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.enums import ProcedureStatus
from app.models.procedure import Procedure, ProcedureApproval, ProcedureVersion
from app.repositories.base import BaseRepository


class ProcedureRepository(BaseRepository[Procedure]):
    def __init__(self, session) -> None:
        super().__init__(Procedure, session)

    async def get_by_machine_id(self, machine_id: UUID) -> Procedure | None:
        stmt = (
            select(Procedure)
            .where(Procedure.machine_id == machine_id)
            .options(
                selectinload(Procedure.versions),
                selectinload(Procedure.active_version).selectinload(
                    ProcedureVersion.approvals
                ),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_with_versions(self, procedure_id: UUID) -> Procedure | None:
        stmt = (
            select(Procedure)
            .where(Procedure.id == procedure_id)
            .options(
                selectinload(Procedure.versions),
                selectinload(Procedure.active_version).selectinload(
                    ProcedureVersion.approvals
                ),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_current_draft_version(
        self, procedure_id: UUID
    ) -> ProcedureVersion | None:
        """Return the most recent DRAFT_PENDING_REVIEW version, if any."""
        stmt = (
            select(ProcedureVersion)
            .where(
                ProcedureVersion.procedure_id == procedure_id,
                ProcedureVersion.status == ProcedureStatus.DRAFT_PENDING_REVIEW,
            )
            .order_by(ProcedureVersion.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_approved_version(
        self, procedure_id: UUID
    ) -> ProcedureVersion | None:
        """Return the most recent APPROVED (not yet published) version, if any."""
        stmt = (
            select(ProcedureVersion)
            .where(
                ProcedureVersion.procedure_id == procedure_id,
                ProcedureVersion.status == ProcedureStatus.APPROVED,
            )
            .order_by(ProcedureVersion.created_at.desc())
            .limit(1)
            .options(selectinload(ProcedureVersion.approvals))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_published_version(
        self, procedure_id: UUID
    ) -> ProcedureVersion | None:
        """Return the currently PUBLISHED version."""
        stmt = (
            select(ProcedureVersion)
            .where(
                ProcedureVersion.procedure_id == procedure_id,
                ProcedureVersion.status == ProcedureStatus.PUBLISHED,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_version(self, version_id: UUID) -> ProcedureVersion | None:
        stmt = (
            select(ProcedureVersion)
            .where(ProcedureVersion.id == version_id)
            .options(selectinload(ProcedureVersion.approvals))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_version(self, version: ProcedureVersion) -> ProcedureVersion:
        self.session.add(version)
        await self.session.flush()
        await self.session.refresh(version)
        return version

    async def create_approval(self, approval: ProcedureApproval) -> ProcedureApproval:
        self.session.add(approval)
        await self.session.flush()
        await self.session.refresh(approval)
        return approval

    async def list_versions_for_procedure(
        self, procedure_id: UUID
    ) -> list[ProcedureVersion]:
        stmt = (
            select(ProcedureVersion)
            .where(ProcedureVersion.procedure_id == procedure_id)
            .order_by(ProcedureVersion.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all_with_versions(
        self, *, search: str | None = None
    ) -> list[Procedure]:
        """
        Return all procedures with their versions eagerly loaded.

        Status filtering and pagination are applied in the service layer because
        a procedure's display status is derived from its latest version (a
        correlated property), not a column on the procedures table.

        `search` does a case-insensitive title match at the DB level to keep the
        loaded set small.
        """
        stmt = (
            select(Procedure)
            .options(
                selectinload(Procedure.versions),
                selectinload(Procedure.active_version).selectinload(
                    ProcedureVersion.approvals
                ),
            )
            .order_by(Procedure.updated_at.desc())
        )
        if search:
            stmt = stmt.where(Procedure.title.ilike(f"%{search}%"))
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_version(self, version: ProcedureVersion) -> ProcedureVersion:
        """Flush in-place mutations to a tracked ProcedureVersion and refresh it."""
        await self.session.flush()
        await self.session.refresh(version)
        return version
