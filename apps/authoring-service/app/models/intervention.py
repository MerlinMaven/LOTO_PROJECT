"""
Intervention and InterventionStep ORM models.

Intervention   — a real-world execution of a procedure by an operator.
InterventionStep — tracks each step's validation state within an intervention.

Key architectural invariants:
1. Intervention.procedure_version_id is IMMUTABLE after creation. The operator
   always works with the version that was active when they started — even if a
   newer version is published during the intervention (safety critical).
2. Only ONE intervention per machine can be in an active state at a time.
   Enforced by the partial unique index uq_one_active_intervention_per_machine.
3. step_ref is a string pointer into the workflow_definition JSON tree:
   "phase_id.stage_id.step_id" e.g. "ph_lockout.st_elec.stp_1_1_1"
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import InterventionStatus, StepStatus, ValidationMethod
from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.procedure import ProcedureVersion
    from app.models.audit import AuditEvent


class Intervention(Base, TimestampMixin):
    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)

    # Pinned at start — never changed during the intervention lifetime
    procedure_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procedure_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Phase 2: plain string until auth is implemented in Phase 3
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[InterventionStatus] = mapped_column(
        String(20), nullable=False, default=InterventionStatus.IN_PROGRESS
    )

    # String pointer to current step in the workflow tree
    current_step_ref: Mapped[str | None] = mapped_column(String(255))

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aborted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abort_reason: Mapped[str | None] = mapped_column(Text)

    # Phase 3+ extension points
    pdf_report_url: Mapped[str | None] = mapped_column(Text)
    operator_signature_url: Mapped[str | None] = mapped_column(Text)

    # ── Relationships ─────────────────────────────────────────────────────────
    machine: Mapped[Machine] = relationship("Machine", lazy="selectin")
    procedure_version: Mapped[ProcedureVersion] = relationship(
        "ProcedureVersion", back_populates="interventions", lazy="selectin"
    )
    steps: Mapped[list[InterventionStep]] = relationship(
        "InterventionStep",
        back_populates="intervention",
        cascade="all, delete-orphan",
        order_by="InterventionStep.started_at",
        lazy="selectin",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="intervention",
        order_by="AuditEvent.occurred_at",
        lazy="noload",
    )

    __table_args__ = (
        # Only one active intervention per machine at a time
        Index(
            "uq_one_active_intervention_per_machine",
            "machine_id",
            unique=True,
            postgresql_where=(
                "status IN ('pending', 'in_progress', 'paused')"
            ),
        ),
        Index("idx_interventions_machine_id", "machine_id"),
        Index("idx_interventions_operator", "operator_name"),
        Index("idx_interventions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Intervention id={self.id} machine={self.machine_id} status={self.status}>"


class InterventionStep(Base):
    __tablename__ = "intervention_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False
    )

    # "ph_lockout.st_elec.stp_1_1_1"
    step_ref: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[StepStatus] = mapped_column(
        String(20), nullable=False, default=StepStatus.PENDING
    )
    validation_method_used: Mapped[ValidationMethod | None] = mapped_column(String(20))

    # Populated when validated by AI (Phase 3)
    ai_confidence_score: Mapped[float | None] = mapped_column(Float)

    # Populated on manual override
    override_reason: Mapped[str | None] = mapped_column(Text)

    # URL to the evidence photo in Supabase Storage
    evidence_url: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Relationships ─────────────────────────────────────────────────────────
    intervention: Mapped[Intervention] = relationship(
        "Intervention", back_populates="steps"
    )

    __table_args__ = (
        # Each step_ref is unique within an intervention
        Index(
            "uq_step_per_intervention",
            "intervention_id",
            "step_ref",
            unique=True,
        ),
        Index("idx_steps_intervention_id", "intervention_id"),
        Index("idx_steps_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<InterventionStep ref={self.step_ref!r} status={self.status}>"
