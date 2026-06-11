"""
Machine Knowledge — intermediate representation.

This model sits between raw LLM output and the final LOTO procedure.
It is completely independent of any LLM output format or database schema.

The KnowledgeExtractor converts raw LLM JSON into MachineKnowledge.
The ProcedureGenerator transforms MachineKnowledge into a workflow_definition.

Design rules:
- All component IDs are plain strings (LLM-assigned snake_case identifiers).
- UUIDs live at the procedure/version level (DB concern), not here.
- VisionMetadata stores YOLO-World candidate prompts — NOT detection results.
- Confidence scores reflect extraction certainty, not detection confidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from app.compat import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import EnergyType


# ── Component taxonomy ────────────────────────────────────────────────────────

class ComponentType(StrEnum):
    ENERGY_SOURCE     = "energy_source"       # Battery, mains supply, capacitor
    ISOLATION_SWITCH  = "isolation_switch"    # Circuit breaker, main switch
    LOCKOUT_POINT     = "lockout_point"       # Hasp, valve handle, disconnect
    SAFETY_GUARD      = "safety_guard"        # Physical protective cover/housing
    ACCESS_PANEL      = "access_panel"        # Door/panel opened for access
    MAINTENANCE_TARGET = "maintenance_target" # What the operator is working on
    SAFETY_DEVICE     = "safety_device"       # Padlock, safety tag, lockout hasp
    STORAGE_UNIT      = "storage_unit"        # Safe box, lockout station
    INDICATOR         = "indicator"           # Visual marker, gauge, LED, label
    SENSOR            = "sensor"              # Limit switch, position sensor


class HazardSeverity(StrEnum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ── YOLO-World vision metadata ────────────────────────────────────────────────

class ComponentVisionMetadata(BaseModel):
    """
    Candidate prompts for YOLO-World zero-shot detection.

    These are SUGGESTIONS for the HSE reviewer.
    The reviewer is responsible for final approval of all prompts.
    No inference is performed here.

    `state_prompts` maps state names to lists of prompts:
        {"active":  ["white switch pressed up"],
         "isolated": ["white switch pressed down"]}
    """
    state_prompts: dict[str, list[str]] = Field(
        default_factory=dict,
        description="State-name → list of YOLO-World text prompts for that state.",
    )
    candidate_detection_prompts: list[str] = Field(
        default_factory=list,
        description="General prompts not tied to a specific state.",
    )
    detection_difficulty: str = Field(
        "medium",
        description="Estimated detection difficulty: easy | medium | hard.",
    )
    notes_for_reviewer: str = Field(
        "",
        description="Free-text guidance for the HSE reviewer approving these prompts.",
    )


# ── Core component model ──────────────────────────────────────────────────────

class MachineComponent(BaseModel):
    """
    A single identifiable component on the machine.

    `component_id` is an LLM-assigned snake_case string used as a reference
    key throughout the generation pipeline. It becomes a `component_ref` in
    the workflow_definition steps.
    """
    component_id: str = Field(
        ...,
        min_length=1,
        description="Snake_case unique identifier assigned during extraction.",
    )
    component_type: ComponentType
    label: str = Field(..., min_length=1, description="Human-readable component name.")
    physical_description: str = Field(
        ...,
        min_length=1,
        description="Detailed visual description enabling identification in the field.",
    )
    location_hint: Optional[str] = Field(
        None,
        description="Where the component is located on the machine.",
    )
    energy_type: Optional[EnergyType] = Field(
        None,
        description="Relevant only for energy sources and isolation switches.",
    )
    vision_metadata: ComponentVisionMetadata = Field(
        default_factory=ComponentVisionMetadata,
    )
    extraction_confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.8,
        description="How confident the extractor is about this component.",
    )
    is_lockout_required: bool = Field(
        True,
        description=(
            "Whether this component must be locked out before maintenance. "
            "False for purely visual indicators or passive components."
        ),
    )

    @field_validator("component_id")
    @classmethod
    def must_be_snake_case(cls, v: str) -> str:
        if " " in v:
            raise ValueError(
                f"component_id must be snake_case with no spaces, got: '{v}'"
            )
        return v.lower()


# ── Hazard model ──────────────────────────────────────────────────────────────

class Hazard(BaseModel):
    """An identified safety hazard associated with the machine."""
    hazard_id: str = Field(default_factory=lambda: f"hz_{uuid.uuid4().hex[:8]}")
    hazard_type: str = Field(
        ...,
        description="e.g. electrical, mechanical, thermal, chemical, gravitational, pneumatic",
    )
    description: str = Field(..., min_length=1)
    severity: HazardSeverity
    associated_component_ids: list[str] = Field(
        default_factory=list,
        description="component_id references.",
    )
    mitigation: str = Field(
        ...,
        min_length=1,
        description="How to eliminate or reduce this hazard.",
    )


# ── Extraction provenance ─────────────────────────────────────────────────────

class ExtractionMetadata(BaseModel):
    """Records how and when MachineKnowledge was extracted — the audit trail."""
    source_document_type: str = Field(
        ...,
        description="text | pdf | image | video | manual",
    )
    source_content_hash: Optional[str] = Field(
        None,
        description="SHA-256 of the source document content for reproducibility.",
    )
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    llm_model_used: str = Field(
        ...,
        description="Identifier of the LLM that performed extraction.",
    )
    prompt_template_name: str = Field(
        ...,
        description="Name of the prompt template used.",
    )
    prompt_version: str = Field(
        ...,
        description="Version of the prompt template.",
    )
    generator_version: str = Field(
        "3.0.0",
        description="Version of the generation pipeline.",
    )
    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Mean confidence across all extracted components.",
    )
    raw_llm_response_hash: Optional[str] = Field(
        None,
        description="SHA-256 of the raw LLM response for audit purposes.",
    )


# ── Root MachineKnowledge model ───────────────────────────────────────────────

class MachineKnowledge(BaseModel):
    """
    Intermediate representation of everything known about the machine
    before procedure generation.

    This model is the contract between the KnowledgeExtractor and the
    ProcedureGenerator. Both sides are independent of LLM output formats.
    """
    knowledge_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this extraction run.",
    )
    machine_id: Optional[str] = Field(
        None,
        description="Optional reference to a Machine record in the database.",
    )
    machine_name: str = Field(..., min_length=1)
    description: str = Field(
        ...,
        min_length=1,
        description="Brief description of the machine and its industrial purpose.",
    )
    energy_types: list[EnergyType] = Field(
        ...,
        min_length=1,
        description="All energy types present. At least one required.",
    )
    components: list[MachineComponent] = Field(
        ...,
        min_length=1,
        description="All identified machine components.",
    )
    hazards: list[Hazard] = Field(
        default_factory=list,
        description="Identified safety hazards.",
    )
    maintenance_objectives: list[str] = Field(
        ...,
        min_length=1,
        description="What the operator needs to accomplish.",
    )
    special_considerations: list[str] = Field(
        default_factory=list,
        description="Non-standard precautions or constraints.",
    )
    extraction_metadata: ExtractionMetadata

    # ── Convenience accessors ─────────────────────────────────────────────────

    @property
    def energy_sources(self) -> list[MachineComponent]:
        return [c for c in self.components if c.component_type == ComponentType.ENERGY_SOURCE]

    @property
    def isolation_switches(self) -> list[MachineComponent]:
        return [c for c in self.components if c.component_type == ComponentType.ISOLATION_SWITCH]

    @property
    def lockout_points(self) -> list[MachineComponent]:
        return [
            c for c in self.components
            if c.component_type in (ComponentType.LOCKOUT_POINT, ComponentType.ENERGY_SOURCE,
                                    ComponentType.ISOLATION_SWITCH)
            and c.is_lockout_required
        ]

    @property
    def safety_guards(self) -> list[MachineComponent]:
        return [
            c for c in self.components
            if c.component_type in (ComponentType.SAFETY_GUARD, ComponentType.ACCESS_PANEL)
        ]

    @property
    def maintenance_targets(self) -> list[MachineComponent]:
        return [c for c in self.components if c.component_type == ComponentType.MAINTENANCE_TARGET]

    @property
    def storage_units(self) -> list[MachineComponent]:
        return [c for c in self.components if c.component_type == ComponentType.STORAGE_UNIT]

    def get_component(self, component_id: str) -> Optional[MachineComponent]:
        for c in self.components:
            if c.component_id == component_id:
                return c
        return None

    @property
    def mean_confidence(self) -> float:
        if not self.components:
            return 0.0
        return sum(c.extraction_confidence for c in self.components) / len(self.components)
