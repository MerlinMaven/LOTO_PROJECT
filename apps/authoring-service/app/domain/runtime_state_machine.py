"""
Runtime State Machine.

Two finite state machines that govern the Phase 5 Runtime Engine:

1. InterventionStateMachine  — lifecycle of a single execution session
2. StepStateMachine          — lifecycle of each individual step record

Both are pure Python adjacency tables with no side effects.
Services call validate_*_transition() before any DB write.

Valid graphs:

  Intervention:
    pending ──► in_progress ──► completed
                    │               (terminal)
                    ▼
                  paused ──► in_progress
                    │
               (abort from any active state)
                    ▼
                 aborted (terminal)

  Step:
    pending ──► in_progress ──► validated  (terminal)
                    │         ──► overridden (terminal)
                    │         ──► failed ──► in_progress  (retry)
                    ▼
               (skipped — terminal, set externally, no transition guard)
"""

from __future__ import annotations

from app.core.exceptions import InvalidStatusTransitionError
from app.domain.enums import InterventionStatus, StepStatus

# ── Intervention transitions ──────────────────────────────────────────────────

_INTERVENTION_TRANSITIONS: dict[InterventionStatus, frozenset[InterventionStatus]] = {
    InterventionStatus.PENDING: frozenset({
        InterventionStatus.IN_PROGRESS,
        InterventionStatus.ABORTED,
    }),
    InterventionStatus.IN_PROGRESS: frozenset({
        InterventionStatus.PAUSED,
        InterventionStatus.COMPLETED,
        InterventionStatus.ABORTED,
    }),
    InterventionStatus.PAUSED: frozenset({
        InterventionStatus.IN_PROGRESS,   # resume
        InterventionStatus.ABORTED,       # emergency abort while paused
    }),
    InterventionStatus.COMPLETED: frozenset(),   # terminal
    InterventionStatus.ABORTED: frozenset(),     # terminal
}


def can_transition_intervention(
    from_status: InterventionStatus,
    to_status: InterventionStatus,
) -> bool:
    return to_status in _INTERVENTION_TRANSITIONS.get(from_status, frozenset())


def validate_intervention_transition(
    from_status: InterventionStatus,
    to_status: InterventionStatus,
) -> None:
    if not can_transition_intervention(from_status, to_status):
        raise InvalidStatusTransitionError(
            from_status=str(from_status),
            to_status=str(to_status),
            resource="intervention",
        )


def allowed_intervention_transitions(
    from_status: InterventionStatus,
) -> frozenset[InterventionStatus]:
    return _INTERVENTION_TRANSITIONS.get(from_status, frozenset())


# ── Step transitions ──────────────────────────────────────────────────────────

_STEP_TRANSITIONS: dict[StepStatus, frozenset[StepStatus]] = {
    StepStatus.PENDING: frozenset({StepStatus.IN_PROGRESS}),
    StepStatus.IN_PROGRESS: frozenset({
        StepStatus.VALIDATED,
        StepStatus.OVERRIDDEN,
        StepStatus.FAILED,
    }),
    StepStatus.FAILED: frozenset({StepStatus.IN_PROGRESS}),   # operator can retry
    StepStatus.VALIDATED: frozenset(),    # terminal
    StepStatus.OVERRIDDEN: frozenset(),   # terminal
    StepStatus.SKIPPED: frozenset(),      # terminal
}


def can_transition_step(from_status: StepStatus, to_status: StepStatus) -> bool:
    return to_status in _STEP_TRANSITIONS.get(from_status, frozenset())


def validate_step_transition(from_status: StepStatus, to_status: StepStatus) -> None:
    from app.core.exceptions import StepAlreadyCompletedError
    if not can_transition_step(from_status, to_status):
        # Terminal states get a domain-specific error for clearer messaging.
        if from_status in (StepStatus.VALIDATED, StepStatus.OVERRIDDEN, StepStatus.SKIPPED):
            raise StepAlreadyCompletedError(
                step_ref="<unknown>",
                current_status=str(from_status),
            )
        raise InvalidStatusTransitionError(
            from_status=str(from_status),
            to_status=str(to_status),
            resource="step",
        )


def allowed_step_transitions(from_status: StepStatus) -> frozenset[StepStatus]:
    return _STEP_TRANSITIONS.get(from_status, frozenset())
