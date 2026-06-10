"""
Machine and MachineComponent ORM models.

Machine  — a physical industrial asset.
MachineComponent — an energy isolation point belonging to a machine
                   (circuit breaker, valve, etc.).

Design notes:
- energy_types stored as JSONB list of EnergyType strings so the column
  is queryable (`energy_types @> '["electrical"]'`) without a join table.
- ar_spatial_reference is nullable JSONB reserved for Phase 4 Quest integration.
- default_vision_prompt is nullable; populated by the HSE engineer and used
  by the Phase 3 YOLO service as the zero-shot detection prompt.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EnergyType, RiskLevel
from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.procedure import Procedure


class Machine(Base, TimestampMixin):
    __tablename__ = "machines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)

    # Phase 1 had a Site entity; site_id is nullable in Phase 2 (Sites API deferred)
    site_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    internal_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model_reference: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(100))

    # List of EnergyType strings e.g. ["electrical", "pneumatic"]
    energy_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    risk_level: Mapped[RiskLevel] = mapped_column(
        String(20), nullable=False, default=RiskLevel.MEDIUM
    )
    location_in_site: Mapped[str | None] = mapped_column(Text)

    # Nullable JSONB: future Quest spatial reference (Phase 4)
    ar_spatial_reference: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    components: Mapped[list[MachineComponent]] = relationship(
        "MachineComponent",
        back_populates="machine",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    procedure: Mapped[Procedure | None] = relationship(
        "Procedure",
        back_populates="machine",
        uselist=False,
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("site_id", "internal_code", name="uq_machine_code_per_site"),
        Index("idx_machines_site_id", "site_id"),
        Index("idx_machines_internal_code", "internal_code"),
        Index("idx_machines_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Machine id={self.id} code={self.internal_code!r}>"


class MachineComponent(Base, TimestampMixin):
    __tablename__ = "machine_components"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    machine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), nullable=False
    )

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    energy_type: Mapped[EnergyType] = mapped_column(String(30), nullable=False)
    physical_description: Mapped[str | None] = mapped_column(Text)
    location_hint: Mapped[str | None] = mapped_column(Text)

    # Phase 3 extension point: zero-shot YOLO-World detection prompt
    default_vision_prompt: Mapped[str | None] = mapped_column(Text)

    # Phase 4 extension point: Quest spatial anchor reference
    ar_anchor_id: Mapped[str | None] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    machine: Mapped[Machine] = relationship("Machine", back_populates="components")

    __table_args__ = (
        Index("idx_components_machine_active", "machine_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<MachineComponent id={self.id} label={self.label!r}>"
