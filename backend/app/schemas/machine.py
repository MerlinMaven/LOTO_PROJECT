"""
Machine and MachineComponent Pydantic v2 schemas.

Naming convention:
  *Create  — request body for POST
  *Update  — request body for PATCH (all fields optional)
  *Read    — response body for GET
  *Summary — lightweight read used inside nested responses
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.domain.enums import EnergyType, RiskLevel
from app.schemas.common import AppBaseModel


# ── MachineComponent ──────────────────────────────────────────────────────────

class ComponentCreate(AppBaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    energy_type: EnergyType
    physical_description: str | None = None
    location_hint: str | None = None
    default_vision_prompt: str | None = Field(
        None,
        description="Zero-shot YOLO-World detection prompt. Populated in Phase 3.",
        examples=["red safety padlock on circuit breaker hasp"],
    )
    ar_anchor_id: str | None = Field(
        None, description="Quest spatial anchor reference. Populated in Phase 4."
    )


class ComponentUpdate(AppBaseModel):
    label: str | None = None
    physical_description: str | None = None
    location_hint: str | None = None
    default_vision_prompt: str | None = None
    ar_anchor_id: str | None = None
    is_active: bool | None = None


class ComponentRead(AppBaseModel):
    id: UUID
    machine_id: UUID
    label: str
    energy_type: EnergyType
    physical_description: str | None
    location_hint: str | None
    default_vision_prompt: str | None
    ar_anchor_id: str | None
    is_active: bool


# ── Machine ───────────────────────────────────────────────────────────────────

class MachineCreate(AppBaseModel):
    internal_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    manufacturer: str | None = None
    model_reference: str | None = None
    serial_number: str | None = None
    energy_types: list[EnergyType] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    location_in_site: str | None = None
    site_id: UUID | None = None
    components: list[ComponentCreate] = Field(
        default_factory=list,
        description="Optional: create components inline during machine registration.",
    )


class MachineUpdate(AppBaseModel):
    name: str | None = None
    manufacturer: str | None = None
    model_reference: str | None = None
    serial_number: str | None = None
    energy_types: list[EnergyType] | None = None
    risk_level: RiskLevel | None = None
    location_in_site: str | None = None
    is_active: bool | None = None


class MachineSummary(AppBaseModel):
    """Lightweight read used inside nested responses (e.g., inside Procedure)."""
    id: UUID
    internal_code: str
    name: str
    risk_level: RiskLevel
    is_active: bool


class MachineRead(AppBaseModel):
    id: UUID
    internal_code: str
    name: str
    manufacturer: str | None
    model_reference: str | None
    serial_number: str | None
    energy_types: list[EnergyType]
    risk_level: RiskLevel
    location_in_site: str | None
    site_id: UUID | None
    is_active: bool
    components: list[ComponentRead] = Field(default_factory=list)

    # Inline summary of the active procedure (null if no published procedure exists)
    active_procedure_version_id: UUID | None = Field(
        None,
        description="ID of the currently published ProcedureVersion for this machine.",
    )
