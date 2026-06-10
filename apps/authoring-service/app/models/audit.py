"""
AuditEvent ORM model.

Architectural contract:
- APPEND-ONLY: No UPDATE or DELETE ever touches this table in application code.
  The Alembic migration creates PostgreSQL RULE objects to enforce this at DB level.
- event_hash: SHA-256 of (event_type, actor_id, payload, occurred_at) computed
  in Python before INSERT. Enables offline tamper detection: re-hash any row and
  compare with stored hash.
- occurred_at uses server_default=func.now() and must NEVER be set by callers.

Every critical action in the service layer must produce at least one AuditEvent.
The AuditService.record_event() method is the single entry point.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AuditEventType
from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.intervention import Intervention


class AuditEvent(Base):
    """
    Immutable audit event record.

    No TimestampMixin — audit events have only occurred_at (set by DB server),
    never updated_at.
    """
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # actor_id: email, UUID, or "system" — nullable for automated events
    actor_id: Mapped[str | None] = mapped_column(String(255))

    # Optional FK references for efficient querying by resource
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"), nullable=True
    )
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interventions.id", ondelete="SET NULL"), nullable=True
    )
    procedure_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("procedure_versions.id", ondelete="SET NULL"), nullable=True
    )

    # "ph_lockout.st_elec.stp_1_1_1" — set for step-level events
    step_ref: Mapped[str | None] = mapped_column(String(255))

    # Contextual data for the event
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Client IP address (string to support both IPv4 and IPv6 without pg INET dependency)
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # Server-assigned timestamp — never set by application code
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # SHA-256 hash for tamper detection
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    intervention: Mapped[Intervention | None] = relationship(
        "Intervention",
        back_populates="audit_events",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_audit_machine", "machine_id", "occurred_at"),
        Index("idx_audit_intervention", "intervention_id", "occurred_at"),
        Index("idx_audit_event_type", "event_type", "occurred_at"),
        Index("idx_audit_procedure_version", "procedure_version_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent type={self.event_type!r} at={self.occurred_at}>"
