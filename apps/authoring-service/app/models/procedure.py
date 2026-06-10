"""
Procedure, ProcedureVersion, and ProcedureApproval ORM models.

Procedure        — the stable envelope for a machine's LOTO procedure.
                   One Procedure per Machine (UNIQUE constraint).
ProcedureVersion — immutable versioned content (workflow_definition JSONB).
                   Each Procedure can have many Versions.
ProcedureApproval — formal sign-off record per Version.

Key architectural invariants:
1. ProcedureVersion.workflow_definition is immutable once status != DRAFT.
   Enforced at the service layer (ApprovedProcedureImmutableError) AND via
   a PostgreSQL trigger created in the Alembic migration.
2. Procedure.active_version_id points to the currently PUBLISHED version.
   It is null until the first version is published.
3. The circular FK (procedures → procedure_versions.active_version_id) is
   declared with use_alter=True so Alembic emits an ALTER TABLE after both
   tables are created.
4. The 4-eyes rule (approver ≠ author) is enforced at the service layer, not
   DB-level, to give a meaningful error message.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ApprovalDecision, GenerationSource, ProcedureStatus
from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.intervention import Intervention


class Procedure(Base, TimestampMixin):
    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    machine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Points to the currently PUBLISHED version; null until first publish
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "procedure_versions.id",
            use_alter=True,
            name="fk_procedure_active_version",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    machine: Mapped[Machine] = relationship("Machine", back_populates="procedure")

    versions: Mapped[list[ProcedureVersion]] = relationship(
        "ProcedureVersion",
        back_populates="procedure",
        foreign_keys="ProcedureVersion.procedure_id",
        cascade="all, delete-orphan",
        order_by="ProcedureVersion.created_at.desc()",
        lazy="selectin",
    )

    active_version: Mapped[ProcedureVersion | None] = relationship(
        "ProcedureVersion",
        foreign_keys=[active_version_id],
        primaryjoin="Procedure.active_version_id == ProcedureVersion.id",
        lazy="selectin",
        post_update=True,
    )

    __table_args__ = (
        Index("idx_procedures_machine_id", "machine_id"),
    )

    def __repr__(self) -> str:
        return f"<Procedure id={self.id} machine_id={self.machine_id}>"


class ProcedureVersion(Base, TimestampMixin):
    __tablename__ = "procedure_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    procedure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False
    )

    version_number: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    status: Mapped[ProcedureStatus] = mapped_column(
        String(30),
        nullable=False,
        default=ProcedureStatus.DRAFT_PENDING_REVIEW,
    )

    # How this version was created (tracks LLM vs manual vs PDF source)
    generation_source: Mapped[GenerationSource] = mapped_column(
        String(30), nullable=False, default=GenerationSource.MANUAL
    )
    # Phase 2 extension point: which LLM model generated this (if any)
    llm_model_used: Mapped[str | None] = mapped_column(String(255))

    # Version of the canonical JSON schema used for workflow_definition
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False, default="1.0")

    # Canonical procedure workflow — see Phase 1 schema document
    workflow_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Populated by the service layer when schema validation finds issues
    validation_errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    submitted_for_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    procedure: Mapped[Procedure] = relationship(
        "Procedure",
        back_populates="versions",
        foreign_keys=[procedure_id],
    )

    approvals: Mapped[list[ProcedureApproval]] = relationship(
        "ProcedureApproval",
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    interventions: Mapped[list[Intervention]] = relationship(
        "Intervention",
        back_populates="procedure_version",
        lazy="noload",   # never eager-loaded; fetched explicitly when needed
    )

    __table_args__ = (
        UniqueConstraint("procedure_id", "version_number", name="uq_version_per_procedure"),
        Index("idx_procedure_versions_procedure_id", "procedure_id"),
        Index("idx_procedure_versions_status", "status"),
        Index("idx_procedure_versions_procedure_status", "procedure_id", "status"),
    )

    @property
    def latest_approval(self) -> ProcedureApproval | None:
        if not self.approvals:
            return None
        return max(self.approvals, key=lambda a: a.decided_at)

    def __repr__(self) -> str:
        return f"<ProcedureVersion id={self.id} v={self.version_number} status={self.status}>"


class ProcedureApproval(Base):
    __tablename__ = "procedure_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedure_versions.id", ondelete="CASCADE"), nullable=False
    )

    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # True if a later approval superseded this one (e.g., after a rejection and re-review)
    is_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    version: Mapped[ProcedureVersion] = relationship(
        "ProcedureVersion", back_populates="approvals"
    )

    __table_args__ = (
        Index("idx_approvals_version_id", "version_id"),
    )

    def __repr__(self) -> str:
        return f"<ProcedureApproval id={self.id} decision={self.decision}>"
