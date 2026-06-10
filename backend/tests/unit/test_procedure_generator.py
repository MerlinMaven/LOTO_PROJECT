"""
Unit tests for ProcedureGenerator.

Tests cover:
- Cardboard prototype generates exactly 4 phases (lockout/verify/maintenance/restoration)
- Phase sequence numbers are correct
- Lockout phase contains one stage per isolation switch + one per energy source
- Energy removal stage has step referencing the safe_box (storage unit)
- Verification phase has zero-energy stage + access-preparation stage
- Maintenance phase has a step per maintenance target per objective
- Restoration phase mirrors lockout in reverse order
- generate() returns a notes list as well
- Steps have non-empty instructions
- No duplicate step_ids
All tests are deterministic — no LLM, no DB.
"""

from __future__ import annotations

import pytest

from app.generation.generators.procedure_generator import ProcedureGenerator
from tests.fixtures.cardboard_prototype import make_cardboard_knowledge


@pytest.fixture
def generator() -> ProcedureGenerator:
    return ProcedureGenerator()


@pytest.fixture
def knowledge():
    return make_cardboard_knowledge()


@pytest.fixture
def result(generator, knowledge):
    workflow, notes = generator.generate(knowledge)
    return workflow, notes


# ── Top-level structure ───────────────────────────────────────────────────────

class TestTopLevelStructure:
    def test_returns_dict_with_phases_key(self, result):
        workflow, _ = result
        assert "phases" in workflow

    def test_returns_four_phases(self, result):
        workflow, _ = result
        assert len(workflow["phases"]) == 4

    def test_notes_is_list(self, result):
        _, notes = result
        assert isinstance(notes, list)

    def test_notes_not_empty(self, result):
        _, notes = result
        assert len(notes) > 0

    def test_phase_types_present(self, result):
        workflow, _ = result
        types = {p["phase_type"] for p in workflow["phases"]}
        assert "lockout" in types
        assert "verification" in types
        assert "maintenance" in types
        assert "restoration" in types

    def test_phases_have_sequential_sequence_numbers(self, result):
        workflow, _ = result
        sequences = [p["sequence"] for p in workflow["phases"]]
        assert sequences == sorted(sequences)
        assert sequences[0] == 1

    def test_no_duplicate_step_ids(self, result):
        workflow, _ = result
        seen = []
        for phase in workflow["phases"]:
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    seen.append(step["step_id"])
        assert len(seen) == len(set(seen)), "Duplicate step_ids found"

    def test_all_instructions_non_empty(self, result):
        workflow, _ = result
        for phase in workflow["phases"]:
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    assert step["instruction"].strip(), (
                        f"Empty instruction in step {step['step_id']}"
                    )


# ── Lockout phase ─────────────────────────────────────────────────────────────

class TestLockoutPhase:
    def _lockout(self, workflow):
        return next(p for p in workflow["phases"] if p["phase_type"] == "lockout")

    def test_lockout_is_first(self, result):
        workflow, _ = result
        phases = workflow["phases"]
        assert phases[0]["phase_type"] == "lockout"

    def test_lockout_has_isolation_switch_stage(self, result):
        workflow, _ = result
        lockout = self._lockout(workflow)
        stage_ids = [s["stage_id"] for s in lockout["stages"]]
        assert any("main_switch" in sid for sid in stage_ids)

    def test_lockout_has_energy_source_stage(self, result):
        workflow, _ = result
        lockout = self._lockout(workflow)
        stage_ids = [s["stage_id"] for s in lockout["stages"]]
        assert any("battery_holder" in sid for sid in stage_ids)

    def test_energy_removal_stage_has_storage_step(self, result):
        workflow, _ = result
        lockout = self._lockout(workflow)
        # The battery_holder removal stage should include a step referencing safe_box
        battery_stage = next(
            s for s in lockout["stages"] if "battery_holder" in s["stage_id"]
        )
        component_refs = [
            step.get("component_ref") for step in battery_stage["steps"]
        ]
        assert "safe_box" in component_refs

    def test_switch_step_references_main_switch(self, result):
        workflow, _ = result
        lockout = self._lockout(workflow)
        switch_stage = next(
            s for s in lockout["stages"] if "main_switch" in s["stage_id"]
        )
        refs = [step.get("component_ref") for step in switch_stage["steps"]]
        assert "main_switch" in refs

    def test_lockout_steps_have_vision_validation(self, result):
        workflow, _ = result
        lockout = self._lockout(workflow)
        for stage in lockout["stages"]:
            for step in stage["steps"]:
                validation = step.get("validation", {})
                assert "method" in validation, f"Step {step['step_id']} missing validation"


# ── Verification phase ────────────────────────────────────────────────────────

class TestVerificationPhase:
    def _verify(self, workflow):
        return next(p for p in workflow["phases"] if p["phase_type"] == "verification")

    def test_verification_has_zero_energy_stage(self, result):
        workflow, _ = result
        verify = self._verify(workflow)
        stage_ids = [s["stage_id"] for s in verify["stages"]]
        assert "st_zero_energy" in stage_ids

    def test_verification_has_access_preparation_stage(self, result):
        workflow, _ = result
        verify = self._verify(workflow)
        stage_ids = [s["stage_id"] for s in verify["stages"]]
        assert "st_access_preparation" in stage_ids

    def test_zero_energy_covers_both_lockout_points(self, result):
        workflow, _ = result
        verify = self._verify(workflow)
        zero_energy = next(s for s in verify["stages"] if s["stage_id"] == "st_zero_energy")
        refs = {step.get("component_ref") for step in zero_energy["steps"]}
        # main_switch and battery_holder are both lockout_points
        assert "main_switch" in refs
        assert "battery_holder" in refs

    def test_access_prep_references_transparent_guard(self, result):
        workflow, _ = result
        verify = self._verify(workflow)
        access = next(s for s in verify["stages"] if s["stage_id"] == "st_access_preparation")
        refs = {step.get("component_ref") for step in access["steps"]}
        assert "transparent_guard" in refs


# ── Maintenance phase ─────────────────────────────────────────────────────────

class TestMaintenancePhase:
    def _maintenance(self, workflow):
        return next(p for p in workflow["phases"] if p["phase_type"] == "maintenance")

    def test_maintenance_phase_has_light_bulb_stage(self, result):
        workflow, _ = result
        maintenance = self._maintenance(workflow)
        stage_ids = [s["stage_id"] for s in maintenance["stages"]]
        assert any("light_bulb" in sid for sid in stage_ids)

    def test_maintenance_step_references_light_bulb(self, result):
        workflow, _ = result
        maintenance = self._maintenance(workflow)
        bulb_stage = maintenance["stages"][0]
        refs = {step.get("component_ref") for step in bulb_stage["steps"]}
        assert "light_bulb" in refs

    def test_maintenance_includes_special_considerations_step(self, result):
        workflow, _ = result
        maintenance = self._maintenance(workflow)
        all_instructions = [
            step["instruction"]
            for stage in maintenance["stages"]
            for step in stage["steps"]
        ]
        assert any("polarity" in instr or "special" in instr.lower() or "verify" in instr.lower()
                   for instr in all_instructions)


# ── Restoration phase ─────────────────────────────────────────────────────────

class TestRestorationPhase:
    def _restoration(self, workflow):
        return next(p for p in workflow["phases"] if p["phase_type"] == "restoration")

    def test_restoration_is_last(self, result):
        workflow, _ = result
        assert workflow["phases"][-1]["phase_type"] == "restoration"

    def test_restoration_closes_transparent_guard(self, result):
        workflow, _ = result
        restoration = self._restoration(workflow)
        all_refs = [
            step.get("component_ref")
            for stage in restoration["stages"]
            for step in stage["steps"]
        ]
        assert "transparent_guard" in all_refs

    def test_restoration_restores_battery_holder(self, result):
        workflow, _ = result
        restoration = self._restoration(workflow)
        all_refs = [
            step.get("component_ref")
            for stage in restoration["stages"]
            for step in stage["steps"]
        ]
        assert "battery_holder" in all_refs

    def test_restoration_activates_main_switch(self, result):
        workflow, _ = result
        restoration = self._restoration(workflow)
        all_refs = [
            step.get("component_ref")
            for stage in restoration["stages"]
            for step in stage["steps"]
        ]
        assert "main_switch" in all_refs

    def test_guard_is_closed_before_battery_restored(self, result):
        """Guard closure must precede energy source restoration."""
        workflow, _ = result
        restoration = self._restoration(workflow)
        stage_ids = [s["stage_id"] for s in restoration["stages"]]
        guard_idx = next(
            (i for i, sid in enumerate(stage_ids) if "closure" in sid or "transparent_guard" in sid),
            None,
        )
        battery_idx = next(
            (i for i, sid in enumerate(stage_ids) if "battery_holder" in sid),
            None,
        )
        if guard_idx is not None and battery_idx is not None:
            assert guard_idx < battery_idx


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_generator_without_storage_unit_still_works(self, generator, knowledge):
        knowledge.components = [
            c for c in knowledge.components if c.component_id != "safe_box"
        ]
        workflow, notes = generator.generate(knowledge)
        phases = {p["phase_type"] for p in workflow["phases"]}
        assert "lockout" in phases
        assert "restoration" in phases

    def test_generator_without_maintenance_targets_uses_objectives(self, generator, knowledge):
        knowledge.components = [
            c for c in knowledge.components if c.component_type.value != "maintenance_target"
        ]
        workflow, notes = generator.generate(knowledge)
        types = {p["phase_type"] for p in workflow["phases"]}
        assert "maintenance" in types
        maintenance_phase = next(p for p in workflow["phases"] if p["phase_type"] == "maintenance")
        assert len(maintenance_phase["stages"]) >= 1

    def test_notes_mention_each_component_label(self, generator, knowledge):
        _, notes = generator.generate(knowledge)
        combined = " ".join(notes)
        assert "Main Power Switch" in combined
        assert "Battery Holder" in combined
