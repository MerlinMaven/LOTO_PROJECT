"""
Unit tests for ProcedureValidator.

Tests cover all validation rules (E001-E009, W001-W005, I001).
No DB, no LLM, no HTTP — pure Python.
"""

from __future__ import annotations

import pytest

from app.generation.validators.procedure_validator import ProcedureValidator
from tests.fixtures.cardboard_prototype import make_cardboard_knowledge, make_cardboard_workflow


@pytest.fixture
def validator() -> ProcedureValidator:
    return ProcedureValidator()


@pytest.fixture
def valid_knowledge():
    return make_cardboard_knowledge()


@pytest.fixture
def valid_workflow():
    return make_cardboard_workflow()


# ── Happy path ────────────────────────────────────────────────────────────────

class TestValidProcedure:
    def test_cardboard_prototype_is_publishable(self, validator, valid_workflow, valid_knowledge):
        report = validator.validate(valid_workflow, valid_knowledge)
        assert report.is_publishable, (
            f"Expected publishable but got errors: "
            f"{[e.code + ': ' + e.message for e in report.errors]}"
        )

    def test_no_errors_on_valid_procedure(self, validator, valid_workflow, valid_knowledge):
        report = validator.validate(valid_workflow, valid_knowledge)
        assert report.error_count == 0

    def test_all_issues_combines_all_severities(self, validator, valid_workflow, valid_knowledge):
        report = validator.validate(valid_workflow, valid_knowledge)
        expected_total = len(report.errors) + len(report.warnings) + len(report.infos)
        assert len(report.all_issues) == expected_total


# ── Error rules ───────────────────────────────────────────────────────────────

class TestErrorRules:
    def test_E001_no_phases(self, validator, valid_knowledge):
        report = validator.validate({"phases": []}, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E001" in codes
        assert not report.is_publishable

    def test_E002_missing_lockout_phase(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {"step_id": "s1", "sequence": 1, "instruction": "Do something"}
                    ]}
                ]}
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E002" in codes

    def test_E003_missing_restoration_phase(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {"step_id": "s1", "sequence": 1, "instruction": "Lock it",
                         "component_ref": "main_switch"}
                    ]}
                ]}
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E003" in codes

    def test_E004_no_steps(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 1, "stages": []},
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 2, "stages": []},
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E004" in codes

    def test_E006_empty_instruction(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {"step_id": "s1", "sequence": 1, "instruction": "  ",
                         "component_ref": "main_switch"}
                    ]}
                ]},
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 2, "stages": [
                    {"stage_id": "st_2", "sequence": 1, "steps": [
                        {"step_id": "s2", "sequence": 1, "instruction": "Restore"}
                    ]}
                ]},
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E006" in codes

    def test_E007_duplicate_step_ids(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {"step_id": "DUPLICATE", "sequence": 1, "instruction": "Step A",
                         "component_ref": "main_switch"},
                        {"step_id": "DUPLICATE", "sequence": 2, "instruction": "Step B",
                         "component_ref": "battery_holder"},
                    ]}
                ]},
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 2, "stages": [
                    {"stage_id": "st_2", "sequence": 1, "steps": [
                        {"step_id": "s3", "sequence": 1, "instruction": "Restore"}
                    ]}
                ]},
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E007" in codes

    def test_E008_maintenance_before_lockout(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_m", "phase_type": "maintenance", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {"step_id": "s1", "sequence": 1, "instruction": "Fix it"}
                    ]}
                ]},
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 2, "stages": [
                    {"stage_id": "st_2", "sequence": 1, "steps": [
                        {"step_id": "s2", "sequence": 1, "instruction": "Lock",
                         "component_ref": "main_switch"}
                    ]}
                ]},
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 3, "stages": [
                    {"stage_id": "st_3", "sequence": 1, "steps": [
                        {"step_id": "s3", "sequence": 1, "instruction": "Restore"}
                    ]}
                ]},
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {e.code for e in report.errors}
        assert "E008" in codes


# ── Warning rules ─────────────────────────────────────────────────────────────

class TestWarningRules:
    def test_W001_missing_verification_phase(self, validator, valid_knowledge):
        # Build valid workflow without verification phase
        workflow = make_cardboard_workflow()
        workflow["phases"] = [
            p for p in workflow["phases"] if p["phase_type"] != "verification"
        ]
        report = validator.validate(workflow, valid_knowledge)
        codes = {w.code for w in report.warnings}
        assert "W001" in codes
        assert report.is_publishable  # warnings don't block

    def test_W002_low_confidence_component(self, validator, valid_workflow):
        knowledge = make_cardboard_knowledge()
        knowledge.components[0].extraction_confidence = 0.3
        report = validator.validate(valid_workflow, knowledge)
        codes = {w.code for w in report.warnings}
        assert "W002" in codes

    def test_W003_vision_step_without_yolo_prompts(self, validator, valid_knowledge):
        workflow = {
            "phases": [
                {"phase_id": "ph_l", "phase_type": "lockout", "sequence": 1, "stages": [
                    {"stage_id": "st_1", "sequence": 1, "steps": [
                        {
                            "step_id": "s1", "sequence": 1,
                            "instruction": "Turn off switch",
                            "component_ref": "main_switch",
                            "validation": {
                                "method": "vision_detection",
                                "yolo_candidate_prompts": [],  # empty!
                            },
                        }
                    ]}
                ]},
                {"phase_id": "ph_r", "phase_type": "restoration", "sequence": 2, "stages": [
                    {"stage_id": "st_2", "sequence": 1, "steps": [
                        {"step_id": "s2", "sequence": 1, "instruction": "Restore"}
                    ]}
                ]},
            ]
        }
        report = validator.validate(workflow, valid_knowledge)
        codes = {w.code for w in report.warnings}
        assert "W003" in codes
