"""
Unit tests for the procedure state machine.

These tests exercise pure Python — no database, no HTTP, no mocks needed.
They are the fastest tests in the suite and must pass in < 1ms each.
"""

import pytest

from app.core.exceptions import InvalidStatusTransitionError
from app.domain.enums import ProcedureStatus
from app.domain.state_machine import (
    allowed_transitions,
    can_transition,
    validate_transition,
    validate_workflow_definition,
)


# ── Transition matrix tests ───────────────────────────────────────────────────

class TestValidTransitions:
    def test_draft_to_approved(self):
        assert can_transition(
            ProcedureStatus.DRAFT_PENDING_REVIEW, ProcedureStatus.APPROVED
        )

    def test_approved_to_published(self):
        assert can_transition(ProcedureStatus.APPROVED, ProcedureStatus.PUBLISHED)

    def test_published_to_archived(self):
        assert can_transition(ProcedureStatus.PUBLISHED, ProcedureStatus.ARCHIVED)


class TestInvalidTransitions:
    def test_draft_to_published_forbidden(self):
        """Core business rule: approval cannot be skipped."""
        assert not can_transition(
            ProcedureStatus.DRAFT_PENDING_REVIEW, ProcedureStatus.PUBLISHED
        )

    def test_draft_to_archived_forbidden(self):
        assert not can_transition(
            ProcedureStatus.DRAFT_PENDING_REVIEW, ProcedureStatus.ARCHIVED
        )

    def test_approved_to_archived_forbidden(self):
        """Must go through published before archiving."""
        assert not can_transition(ProcedureStatus.APPROVED, ProcedureStatus.ARCHIVED)

    def test_approved_to_draft_forbidden(self):
        assert not can_transition(
            ProcedureStatus.APPROVED, ProcedureStatus.DRAFT_PENDING_REVIEW
        )

    def test_archived_is_terminal(self):
        """No transitions out of archived."""
        for status in ProcedureStatus:
            assert not can_transition(ProcedureStatus.ARCHIVED, status)

    def test_published_to_draft_forbidden(self):
        assert not can_transition(
            ProcedureStatus.PUBLISHED, ProcedureStatus.DRAFT_PENDING_REVIEW
        )

    def test_published_to_approved_forbidden(self):
        assert not can_transition(ProcedureStatus.PUBLISHED, ProcedureStatus.APPROVED)

    def test_self_transition_forbidden(self):
        """No status can transition to itself."""
        for status in ProcedureStatus:
            assert not can_transition(status, status)


class TestValidateTransition:
    def test_raises_on_invalid_transition(self):
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            validate_transition(
                ProcedureStatus.DRAFT_PENDING_REVIEW, ProcedureStatus.PUBLISHED
            )
        assert "draft_pending_review" in str(exc_info.value)
        assert "published" in str(exc_info.value)

    def test_does_not_raise_on_valid_transition(self):
        validate_transition(ProcedureStatus.DRAFT_PENDING_REVIEW, ProcedureStatus.APPROVED)

    def test_error_contains_from_and_to(self):
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            validate_transition(ProcedureStatus.APPROVED, ProcedureStatus.ARCHIVED)
        exc = exc_info.value
        assert exc.details["from_status"] == "approved"
        assert exc.details["to_status"] == "archived"


class TestAllowedTransitions:
    def test_draft_has_one_transition(self):
        transitions = allowed_transitions(ProcedureStatus.DRAFT_PENDING_REVIEW)
        assert transitions == frozenset({ProcedureStatus.APPROVED})

    def test_archived_has_no_transitions(self):
        assert allowed_transitions(ProcedureStatus.ARCHIVED) == frozenset()


# ── Workflow definition validation tests ─────────────────────────────────────

VALID_WORKFLOW = {
    "phases": [
        {
            "phase_id": "ph_lockout",
            "phase_type": "lockout",
            "sequence": 1,
            "title": "Lockout",
            "stages": [
                {
                    "stage_id": "st_elec",
                    "sequence": 1,
                    "title": "Electrical Isolation",
                    "steps": [
                        {
                            "step_id": "stp_1_1_1",
                            "sequence": 1,
                            "instruction": "Open the main circuit breaker.",
                            "validation": {"method": "vision_detection"},
                        }
                    ],
                }
            ],
        }
    ]
}


class TestWorkflowValidation:
    def test_valid_workflow_returns_no_errors(self):
        errors = validate_workflow_definition(VALID_WORKFLOW)
        assert errors == []

    def test_missing_phases_key(self):
        errors = validate_workflow_definition({})
        assert any("phases" in e for e in errors)

    def test_empty_phases_list(self):
        errors = validate_workflow_definition({"phases": []})
        assert any("phases" in e for e in errors)

    def test_invalid_phase_type(self):
        workflow = {
            "phases": [
                {
                    "phase_id": "ph_x",
                    "phase_type": "invalid_type",
                    "sequence": 1,
                    "title": "X",
                    "stages": [
                        {
                            "stage_id": "st_x",
                            "sequence": 1,
                            "title": "X Stage",
                            "steps": [
                                {
                                    "step_id": "stp_x",
                                    "sequence": 1,
                                    "instruction": "Do something.",
                                    "validation": {"method": "manual_confirmation"},
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        errors = validate_workflow_definition(workflow)
        assert any("invalid_type" in e for e in errors)

    def test_missing_step_instruction(self):
        workflow = {
            "phases": [
                {
                    "phase_id": "ph_lockout",
                    "phase_type": "lockout",
                    "sequence": 1,
                    "title": "Lockout",
                    "stages": [
                        {
                            "stage_id": "st_elec",
                            "sequence": 1,
                            "title": "Electrical",
                            "steps": [
                                {"step_id": "stp_1", "sequence": 1}  # missing instruction + validation
                            ],
                        }
                    ],
                }
            ]
        }
        errors = validate_workflow_definition(workflow)
        assert any("instruction" in e for e in errors)
        assert any("validation" in e for e in errors)

    def test_non_dict_raises_immediately(self):
        errors = validate_workflow_definition("not a dict")
        assert len(errors) == 1
        assert "JSON object" in errors[0]

    def test_missing_validation_method(self):
        workflow = {
            "phases": [
                {
                    "phase_id": "ph_lockout",
                    "phase_type": "lockout",
                    "sequence": 1,
                    "title": "Lockout",
                    "stages": [
                        {
                            "stage_id": "st_elec",
                            "sequence": 1,
                            "title": "Electrical",
                            "steps": [
                                {
                                    "step_id": "stp_1",
                                    "sequence": 1,
                                    "instruction": "Open breaker.",
                                    "validation": {},  # missing method
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        errors = validate_workflow_definition(workflow)
        assert any("method" in e for e in errors)
