"""
Unit tests for the runtime state machine.

Pure Python — no database, no mocks required.
"""

import pytest

from app.core.exceptions import InvalidStatusTransitionError, StepAlreadyCompletedError
from app.domain.enums import InterventionStatus, StepStatus
from app.domain.runtime_state_machine import (
    allowed_intervention_transitions,
    allowed_step_transitions,
    can_transition_intervention,
    can_transition_step,
    validate_intervention_transition,
    validate_step_transition,
)


# ── Intervention: valid transitions ──────────────────────────────────────────


class TestValidInterventionTransitions:
    def test_pending_to_in_progress(self):
        assert can_transition_intervention(
            InterventionStatus.PENDING, InterventionStatus.IN_PROGRESS
        )

    def test_pending_to_aborted(self):
        assert can_transition_intervention(
            InterventionStatus.PENDING, InterventionStatus.ABORTED
        )

    def test_in_progress_to_paused(self):
        assert can_transition_intervention(
            InterventionStatus.IN_PROGRESS, InterventionStatus.PAUSED
        )

    def test_in_progress_to_completed(self):
        assert can_transition_intervention(
            InterventionStatus.IN_PROGRESS, InterventionStatus.COMPLETED
        )

    def test_in_progress_to_aborted(self):
        assert can_transition_intervention(
            InterventionStatus.IN_PROGRESS, InterventionStatus.ABORTED
        )

    def test_paused_to_in_progress(self):
        assert can_transition_intervention(
            InterventionStatus.PAUSED, InterventionStatus.IN_PROGRESS
        )

    def test_paused_to_aborted_emergency(self):
        assert can_transition_intervention(
            InterventionStatus.PAUSED, InterventionStatus.ABORTED
        )


class TestInvalidInterventionTransitions:
    def test_pending_to_completed_forbidden(self):
        assert not can_transition_intervention(
            InterventionStatus.PENDING, InterventionStatus.COMPLETED
        )

    def test_pending_to_paused_forbidden(self):
        assert not can_transition_intervention(
            InterventionStatus.PENDING, InterventionStatus.PAUSED
        )

    def test_in_progress_to_pending_forbidden(self):
        assert not can_transition_intervention(
            InterventionStatus.IN_PROGRESS, InterventionStatus.PENDING
        )

    def test_paused_to_completed_forbidden(self):
        assert not can_transition_intervention(
            InterventionStatus.PAUSED, InterventionStatus.COMPLETED
        )

    def test_completed_is_terminal(self):
        for s in InterventionStatus:
            assert not can_transition_intervention(InterventionStatus.COMPLETED, s)

    def test_aborted_is_terminal(self):
        for s in InterventionStatus:
            assert not can_transition_intervention(InterventionStatus.ABORTED, s)


class TestInterventionTransitionGuard:
    def test_validate_raises_on_invalid(self):
        with pytest.raises(InvalidStatusTransitionError):
            validate_intervention_transition(
                InterventionStatus.COMPLETED, InterventionStatus.IN_PROGRESS
            )

    def test_validate_passes_on_valid(self):
        validate_intervention_transition(
            InterventionStatus.IN_PROGRESS, InterventionStatus.PAUSED
        )

    def test_allowed_transitions_in_progress(self):
        allowed = allowed_intervention_transitions(InterventionStatus.IN_PROGRESS)
        assert InterventionStatus.PAUSED in allowed
        assert InterventionStatus.COMPLETED in allowed
        assert InterventionStatus.ABORTED in allowed
        assert InterventionStatus.PENDING not in allowed

    def test_allowed_transitions_terminal_empty(self):
        assert allowed_intervention_transitions(InterventionStatus.COMPLETED) == frozenset()
        assert allowed_intervention_transitions(InterventionStatus.ABORTED) == frozenset()


# ── Step: valid transitions ───────────────────────────────────────────────────


class TestValidStepTransitions:
    def test_pending_to_in_progress(self):
        assert can_transition_step(StepStatus.PENDING, StepStatus.IN_PROGRESS)

    def test_in_progress_to_validated(self):
        assert can_transition_step(StepStatus.IN_PROGRESS, StepStatus.VALIDATED)

    def test_in_progress_to_overridden(self):
        assert can_transition_step(StepStatus.IN_PROGRESS, StepStatus.OVERRIDDEN)

    def test_in_progress_to_failed(self):
        assert can_transition_step(StepStatus.IN_PROGRESS, StepStatus.FAILED)

    def test_failed_to_in_progress_retry(self):
        assert can_transition_step(StepStatus.FAILED, StepStatus.IN_PROGRESS)


class TestInvalidStepTransitions:
    def test_pending_to_validated_forbidden(self):
        assert not can_transition_step(StepStatus.PENDING, StepStatus.VALIDATED)

    def test_pending_to_failed_forbidden(self):
        assert not can_transition_step(StepStatus.PENDING, StepStatus.FAILED)

    def test_failed_to_validated_directly_forbidden(self):
        assert not can_transition_step(StepStatus.FAILED, StepStatus.VALIDATED)

    def test_validated_is_terminal(self):
        for s in StepStatus:
            assert not can_transition_step(StepStatus.VALIDATED, s)

    def test_overridden_is_terminal(self):
        for s in StepStatus:
            assert not can_transition_step(StepStatus.OVERRIDDEN, s)

    def test_skipped_is_terminal(self):
        for s in StepStatus:
            assert not can_transition_step(StepStatus.SKIPPED, s)


class TestStepTransitionGuard:
    def test_validate_terminal_raises_step_already_completed(self):
        with pytest.raises(StepAlreadyCompletedError):
            validate_step_transition(StepStatus.VALIDATED, StepStatus.IN_PROGRESS)

    def test_overridden_terminal_raises_step_already_completed(self):
        with pytest.raises(StepAlreadyCompletedError):
            validate_step_transition(StepStatus.OVERRIDDEN, StepStatus.IN_PROGRESS)

    def test_skipped_terminal_raises_step_already_completed(self):
        with pytest.raises(StepAlreadyCompletedError):
            validate_step_transition(StepStatus.SKIPPED, StepStatus.IN_PROGRESS)

    def test_invalid_non_terminal_raises_invalid_transition(self):
        with pytest.raises(InvalidStatusTransitionError):
            validate_step_transition(StepStatus.PENDING, StepStatus.VALIDATED)

    def test_valid_transition_passes(self):
        validate_step_transition(StepStatus.PENDING, StepStatus.IN_PROGRESS)

    def test_allowed_transitions_in_progress(self):
        allowed = allowed_step_transitions(StepStatus.IN_PROGRESS)
        assert StepStatus.VALIDATED in allowed
        assert StepStatus.OVERRIDDEN in allowed
        assert StepStatus.FAILED in allowed

    def test_allowed_transitions_terminal_empty(self):
        assert allowed_step_transitions(StepStatus.VALIDATED) == frozenset()
        assert allowed_step_transitions(StepStatus.OVERRIDDEN) == frozenset()
        assert allowed_step_transitions(StepStatus.SKIPPED) == frozenset()
