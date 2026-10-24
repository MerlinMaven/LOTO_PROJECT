"""Versioned canonical JSON contract for procedure drafts."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class OpenModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class SourceReference(OpenModel):
    source_id: str
    page: int | None = None
    quote: str = ""
    figure_or_region: str | None = None


class InvariantFeature(OpenModel):
    feature_type: str = "marking"  # symbol, pictogram, marking, local_geometry, fixed_text, color_pattern
    description: str
    details: str = ""
    source_ref: str = ""


class VerifiableState(OpenModel):
    state_name: str
    physical_rule: str
    supported_by_unity: bool = False
    candidate_prompt: str = ""
    requires_human_confirmation: bool = True


class ProcedureComponent(OpenModel):
    component_id: str
    component_name: str = ""
    internal_id: str | None = None
    source_tag: str | None = None
    canonical_name: str | None = None
    label: str = ""
    description: str = ""
    component_type: str = ""
    unity_class_id: str = ""
    invariant_features: list[InvariantFeature] = Field(default_factory=list)
    verifiable_states: list[VerifiableState] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_note: str = ""


class TechnicalFact(OpenModel):
    fact_id: str
    internal_id: str | None = None
    qualification: Literal["documented", "inferred", "unknown", "contradictory"]
    category: str
    label: str
    value: str
    source_pages: list[int] = Field(default_factory=list)
    source_quote: str = ""
    source_refs: list[SourceReference] = Field(default_factory=list)
    evidence_type: Literal["text", "visual", "unknown"]
    source_id: str = ""
    structured_value: dict[str, Any] | None = None
    unit: str = ""
    justification: str = ""


class TechnicalInference(OpenModel):
    inference_id: str
    claim: str
    rationale: str
    fact_refs: list[str] = Field(default_factory=list)
    related_component_ids: list[str] = Field(default_factory=list)
    uncertainty: str = ""


class Verification(OpenModel):
    method: Literal[
        "visual_observation", "measurement", "human_confirmation", "sensor_signal",
        "combined_evidence", "not_defined",
    ]
    criteria: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    instrument_refs: list[str] = Field(default_factory=list)
    indeterminate_when: list[str] = Field(default_factory=list)
    candidate_prompts: list[str] = Field(default_factory=list)


class ProcedureStep(OpenModel):
    step_id: str
    sequence: int = Field(ge=1)
    instruction: str
    component_refs: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    expected_result: str = ""
    rationale: str = ""
    basis: Literal["documented_procedure", "reasoning_to_review"]
    fact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[SourceReference] = Field(default_factory=list)
    unresolved_conditions: list[str] = Field(default_factory=list)
    verification: Verification


class ProcedureStage(OpenModel):
    stage_id: str
    sequence: int = Field(ge=1)
    title: str
    steps: list[ProcedureStep] = Field(default_factory=list)


class ProcedurePhase(OpenModel):
    phase_id: str
    phase_type: str
    sequence: int = Field(ge=1)
    title: str
    description: str = ""
    stages: list[ProcedureStage] = Field(default_factory=list)


class Clarification(OpenModel):
    id: str
    impact: str = "à évaluer"
    question: str
    why_needed: str = ""
    source_pages: list[int] = Field(default_factory=list)
    affected_step_ids: list[str] = Field(default_factory=list)
    related_component_ids: list[str] = Field(default_factory=list)
    status: Literal["unresolved", "resolved"] = "unresolved"
    resolution: dict[str, Any] | None = None
    affected_steps_reviewed: bool = False


class ProcedureDraftV2(OpenModel):
    schema_version: Literal["2.0"]
    revision_id: str
    machine_id: str
    machine_name: str
    maintenance_objective: str = ""
    expected_final_state: str = ""
    source_documents: list[dict[str, Any]]
    components: list[ProcedureComponent] = Field(default_factory=list)
    technical_facts: list[TechnicalFact] = Field(default_factory=list)
    inferences: list[TechnicalInference] = Field(default_factory=list)
    visual_observations: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    phases: list[ProcedurePhase] = Field(default_factory=list)
    clarifications_required: list[Clarification] = Field(default_factory=list)
    review: dict[str, Any]
    validation_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
