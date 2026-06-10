"""
Integration test: full generation pipeline with StubLLMProvider.

Tests the complete text → MachineKnowledge → workflow_definition → validation
flow using StubLLMProvider (no API key required).

The stub returns the cardboard prototype fixture, so we validate the pipeline
produces a publishable 4-phase procedure matching the maquette_test.json.

Does NOT test:
- Database persistence (DraftPublisher)
- Quest AR integration
- YOLO inference
- Phase 4 features
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.generation.models.generation_job import GenerationJobStatus, InputSourceType
from app.generation.providers.stub_provider import StubLLMProvider
from app.generation.service import GenerationService


CARDBOARD_DESCRIPTION = """\
The SmartLOTO cardboard prototype simulates an industrial lockout-tagout machine.
It has:
- A white rocker switch (main power switch) on the front panel.
- A red battery holder (energy source) in the center.
- A cardboard safe box marked with a padlock symbol for storing the battery.
- A sliding transparent cover (protective guard) with alignment markers.
- A light bulb (maintenance target) behind the cover.
Maintenance objective: inspect or replace the light bulb.
Special considerations:
  - Verify battery polarity when reinserting.
  - Ensure transparent guard is fully closed before restoring power.
"""


@pytest.fixture
def stub_provider() -> StubLLMProvider:
    return StubLLMProvider(latency_ms=0.0)


@pytest.fixture
def service(stub_provider) -> GenerationService:
    return GenerationService(stub_provider)


# ── End-to-end pipeline ────────────────────────────────────────────────────────

class TestCardboardPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_pipeline_completes_without_error(self, service):
        result = await service.run(
            CARDBOARD_DESCRIPTION,
            source_type=InputSourceType.TEXT,
            source_label="cardboard_test",
            requested_by="test_user",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_job_status_is_completed(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert result.job.status == GenerationJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_procedure_is_publishable(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert result.validation_report.is_publishable, (
            f"Errors: {[e.code + ': ' + e.message for e in result.validation_report.errors]}"
        )

    @pytest.mark.asyncio
    async def test_no_validation_errors(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert result.validation_report.error_count == 0

    @pytest.mark.asyncio
    async def test_workflow_has_four_phases(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert len(result.workflow_definition["phases"]) == 4

    @pytest.mark.asyncio
    async def test_all_four_phase_types_present(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        types = {p["phase_type"] for p in result.workflow_definition["phases"]}
        assert types == {"lockout", "verification", "maintenance", "restoration"}


# ── MachineKnowledge extraction ───────────────────────────────────────────────

class TestMachineKnowledgeExtraction:
    @pytest.mark.asyncio
    async def test_machine_name_is_cardboard_prototype(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert "Cardboard" in result.machine_knowledge.machine_name

    @pytest.mark.asyncio
    async def test_energy_type_is_electrical(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        energy_values = [e.value for e in result.machine_knowledge.energy_types]
        assert "electrical" in energy_values

    @pytest.mark.asyncio
    async def test_five_components_extracted(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert len(result.machine_knowledge.components) == 5

    @pytest.mark.asyncio
    async def test_main_switch_is_isolation_switch(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        switch = result.machine_knowledge.get_component("main_switch")
        assert switch is not None
        assert switch.component_type.value == "isolation_switch"

    @pytest.mark.asyncio
    async def test_battery_holder_is_energy_source(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        battery = result.machine_knowledge.get_component("battery_holder")
        assert battery is not None
        assert battery.component_type.value == "energy_source"

    @pytest.mark.asyncio
    async def test_light_bulb_is_maintenance_target(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        bulb = result.machine_knowledge.get_component("light_bulb")
        assert bulb is not None
        assert bulb.component_type.value == "maintenance_target"

    @pytest.mark.asyncio
    async def test_one_hazard_extracted(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert len(result.machine_knowledge.hazards) >= 1

    @pytest.mark.asyncio
    async def test_maintenance_objective_extracted(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        objectives = result.machine_knowledge.maintenance_objectives
        assert any("bulb" in obj.lower() or "light" in obj.lower() for obj in objectives)


# ── YOLO metadata ─────────────────────────────────────────────────────────────

class TestYoloMetadata:
    @pytest.mark.asyncio
    async def test_yolo_metadata_covers_all_components(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        for comp in result.machine_knowledge.components:
            assert comp.component_id in result.yolo_metadata

    @pytest.mark.asyncio
    async def test_yolo_metadata_has_state_prompts(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        main_switch_meta = result.yolo_metadata.get("main_switch", {})
        assert "state_prompts" in main_switch_meta
        assert "active" in main_switch_meta["state_prompts"]
        assert "isolated" in main_switch_meta["state_prompts"]

    @pytest.mark.asyncio
    async def test_no_yolo_inference_occurred(self, service):
        """Sanity check: confidence_threshold_suggestion is a suggestion, not a detection result."""
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        for cid, meta in result.yolo_metadata.items():
            assert "confidence_threshold_suggestion" in meta
            # suggestions are between 0 and 1
            suggestion = meta["confidence_threshold_suggestion"]
            assert 0.0 <= suggestion <= 1.0, f"Invalid suggestion for {cid}"


# ── LLM provider interaction ──────────────────────────────────────────────────

class TestLLMProviderInteraction:
    @pytest.mark.asyncio
    async def test_stub_provider_called_exactly_once(self, stub_provider, service):
        await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert stub_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_job_records_provider_name(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert result.job.llm_provider == "stub"

    @pytest.mark.asyncio
    async def test_requested_by_preserved_in_job(self, service):
        result = await service.run(
            CARDBOARD_DESCRIPTION,
            source_label="test",
            requested_by="operator_alice",
        )
        assert result.job.requested_by == "operator_alice"


# ── Generation notes ──────────────────────────────────────────────────────────

class TestGenerationNotes:
    @pytest.mark.asyncio
    async def test_generation_notes_not_empty(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        assert len(result.generation_notes) > 0

    @pytest.mark.asyncio
    async def test_no_warning_notes_for_valid_procedure(self, service):
        result = await service.run(CARDBOARD_DESCRIPTION, source_label="test")
        warnings = [n for n in result.generation_notes if n.startswith("WARNING")]
        assert len(warnings) == 0, f"Unexpected generator warnings: {warnings}"
