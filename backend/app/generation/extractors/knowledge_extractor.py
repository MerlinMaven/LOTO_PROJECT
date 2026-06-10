"""
KnowledgeExtractor — transforms ExtractedDocument into MachineKnowledge.

Pipeline:
  ExtractedDocument
    → PromptRenderer (fills template variables)
    → LLMProvider.complete() (calls LLM API)
    → JSON parse + Pydantic validation (LLMComponentRaw)
    → Enrichment (UUIDs, vision metadata generation, confidence aggregation)
    → MachineKnowledge

The LLM output schema (LLMComponentRaw) is intentionally simpler than
MachineKnowledge. This decouples the LLM contract from the domain model.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from app.core.logging import get_logger
from app.domain.enums import EnergyType
from app.generation.adapters.base import ExtractedDocument
from app.generation.models.machine_knowledge import (
    ComponentType,
    ComponentVisionMetadata,
    ExtractionMetadata,
    Hazard,
    HazardSeverity,
    MachineComponent,
    MachineKnowledge,
)
from app.generation.providers.base import LLMProvider, LLMProviderError
from app.generation.prompts.renderer import PromptRenderer

logger = get_logger(__name__)


# ── LLM output schema (what the model returns) ───────────────────────────────

class _LLMComponentRaw(BaseModel):
    """Mirrors the JSON schema in component_extraction_v1.yaml."""
    component_id: str
    component_type: ComponentType
    label: str
    physical_description: str
    location_hint: Optional[str] = None
    energy_type: Optional[EnergyType] = None
    state_active: Optional[str] = None
    state_locked: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class _LLMHazardRaw(BaseModel):
    hazard_type: str
    description: str
    severity: HazardSeverity
    associated_component_ids: list[str] = Field(default_factory=list)
    mitigation: str


class _LLMMachineKnowledgeRaw(BaseModel):
    machine_name: str
    description: str
    energy_types: list[EnergyType]
    components: list[_LLMComponentRaw]
    hazards: list[_LLMHazardRaw] = Field(default_factory=list)
    maintenance_objectives: list[str]
    special_considerations: list[str] = Field(default_factory=list)


# ── Extraction error ──────────────────────────────────────────────────────────

class KnowledgeExtractionError(Exception):
    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


# ── Extractor ─────────────────────────────────────────────────────────────────

class KnowledgeExtractor:
    """
    Calls the LLM, parses JSON, and produces MachineKnowledge.

    Responsibilities:
    - Render the prompt with document content
    - Call the LLM provider
    - Parse and validate the JSON response
    - Convert LLM-assigned component IDs to domain model
    - Build initial VisionMetadata from state_active / state_locked hints
    - Record extraction provenance in ExtractionMetadata
    """

    TEMPLATE_NAME = "component_extraction"
    TEMPLATE_VERSION = "1"

    def __init__(
        self,
        provider: LLMProvider,
        renderer: PromptRenderer,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> None:
        self._provider = provider
        self._renderer = renderer
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def extract(
        self,
        document: ExtractedDocument,
        *,
        machine_id: Optional[str] = None,
    ) -> MachineKnowledge:
        """
        Extract MachineKnowledge from an ExtractedDocument.

        Raises:
            KnowledgeExtractionError: LLM failed, JSON invalid, or Pydantic validation failed.
        """
        messages = self._renderer.render(
            self.TEMPLATE_NAME,
            self.TEMPLATE_VERSION,
            document_content=document.content,
        )

        logger.info(
            "knowledge_extraction_started",
            provider=self._provider.provider_name,
            model=self._provider.default_model,
            content_hash=document.content_hash,
        )

        try:
            response = await self._provider.complete(
                messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format="json_object",
            )
        except LLMProviderError as exc:
            raise KnowledgeExtractionError(str(exc)) from exc

        raw_hash = hashlib.sha256(response.content.encode()).hexdigest()

        raw = self._parse_llm_response(response.content)
        knowledge = self._convert_to_domain(
            raw=raw,
            machine_id=machine_id,
            source_type=document.source_type.value,
            source_hash=document.content_hash,
            llm_response_hash=raw_hash,
            model_id=response.model_id,
        )

        logger.info(
            "knowledge_extraction_completed",
            machine_name=knowledge.machine_name,
            component_count=len(knowledge.components),
            hazard_count=len(knowledge.hazards),
            mean_confidence=round(knowledge.mean_confidence, 3),
        )

        return knowledge

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_llm_response(self, content: str) -> _LLMMachineKnowledgeRaw:
        """Parse raw LLM text into the validated intermediate model."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise KnowledgeExtractionError(
                f"LLM returned invalid JSON: {exc}",
                raw_response=content,
            ) from exc

        try:
            return _LLMMachineKnowledgeRaw.model_validate(data)
        except ValidationError as exc:
            raise KnowledgeExtractionError(
                f"LLM JSON does not match expected schema: {exc}",
                raw_response=content,
            ) from exc

    def _convert_to_domain(
        self,
        raw: _LLMMachineKnowledgeRaw,
        *,
        machine_id: Optional[str],
        source_type: str,
        source_hash: str,
        llm_response_hash: str,
        model_id: str,
    ) -> MachineKnowledge:
        components = [self._build_component(c) for c in raw.components]
        hazards = [self._build_hazard(h) for h in raw.hazards]

        mean_conf = (
            sum(c.extraction_confidence for c in components) / len(components)
            if components else 0.0
        )

        metadata = ExtractionMetadata(
            source_document_type=source_type,
            source_content_hash=source_hash,
            extraction_timestamp=datetime.now(timezone.utc),
            llm_model_used=model_id,
            prompt_template_name=self.TEMPLATE_NAME,
            prompt_version=self.TEMPLATE_VERSION,
            overall_confidence=mean_conf,
            raw_llm_response_hash=llm_response_hash,
        )

        return MachineKnowledge(
            machine_id=machine_id,
            machine_name=raw.machine_name,
            description=raw.description,
            energy_types=raw.energy_types,
            components=components,
            hazards=hazards,
            maintenance_objectives=raw.maintenance_objectives,
            special_considerations=raw.special_considerations,
            extraction_metadata=metadata,
        )

    @staticmethod
    def _build_component(raw: _LLMComponentRaw) -> MachineComponent:
        state_prompts: dict[str, list[str]] = {}
        if raw.state_active:
            state_prompts["active"] = [raw.state_active]
        if raw.state_locked:
            state_prompts["isolated"] = [raw.state_locked]

        vision = ComponentVisionMetadata(
            state_prompts=state_prompts,
            candidate_detection_prompts=[raw.physical_description],
            detection_difficulty="medium",
            notes_for_reviewer=(
                "Prompts auto-generated from physical description. "
                "Review and refine before YOLO activation."
            ),
        )

        # Storage units and indicators are typically not locked out
        no_lockout_types = {ComponentType.STORAGE_UNIT, ComponentType.INDICATOR}
        requires_lockout = raw.component_type not in no_lockout_types

        return MachineComponent(
            component_id=raw.component_id,
            component_type=raw.component_type,
            label=raw.label,
            physical_description=raw.physical_description,
            location_hint=raw.location_hint,
            energy_type=raw.energy_type,
            vision_metadata=vision,
            extraction_confidence=raw.confidence,
            is_lockout_required=requires_lockout,
        )

    @staticmethod
    def _build_hazard(raw: _LLMHazardRaw) -> Hazard:
        return Hazard(
            hazard_type=raw.hazard_type,
            description=raw.description,
            severity=raw.severity,
            associated_component_ids=raw.associated_component_ids,
            mitigation=raw.mitigation,
        )
