"""
Procedure State Machine.

Encodes the ONLY valid state transitions for a ProcedureVersion.
All transition logic is centralised here so:
  - Services call validate_transition() before any DB write.
  - Tests exercise pure Python — no DB, no HTTP.
  - Adding a new state requires changing exactly one place.

Valid graph:
    draft_pending_review ──► approved ──► published ──► archived

Explicitly forbidden (non-exhaustive):
    draft_pending_review ──► published   (skip approval)
    draft_pending_review ──► archived
    approved ──► archived                (must be published first)
    archived ──► *                       (terminal state)

Intervention state machine is simpler and implemented inline in InterventionService.
"""

from __future__ import annotations

from app.core.exceptions import InvalidStatusTransitionError
from app.domain.enums import ProcedureStatus

# Adjacency set: from_status → set of reachable to_statuses
_VALID_TRANSITIONS: dict[ProcedureStatus, frozenset[ProcedureStatus]] = {
    ProcedureStatus.DRAFT_PENDING_REVIEW: frozenset({ProcedureStatus.APPROVED}),
    ProcedureStatus.APPROVED: frozenset({ProcedureStatus.PUBLISHED}),
    ProcedureStatus.PUBLISHED: frozenset({ProcedureStatus.ARCHIVED}),
    ProcedureStatus.ARCHIVED: frozenset(),   # terminal — no outgoing transitions
}


def can_transition(from_status: ProcedureStatus, to_status: ProcedureStatus) -> bool:
    """Return True if the transition is allowed, False otherwise (no side effects)."""
    return to_status in _VALID_TRANSITIONS.get(from_status, frozenset())


def validate_transition(from_status: ProcedureStatus, to_status: ProcedureStatus) -> None:
    """
    Assert that a transition is allowed.
    Raises InvalidStatusTransitionError with a descriptive message if not.
    """
    if not can_transition(from_status, to_status):
        raise InvalidStatusTransitionError(
            from_status=str(from_status),
            to_status=str(to_status),
        )


def allowed_transitions(from_status: ProcedureStatus) -> frozenset[ProcedureStatus]:
    """Return the set of reachable states from a given state (useful for API docs)."""
    return _VALID_TRANSITIONS.get(from_status, frozenset())


def validate_workflow_definition(workflow: dict) -> list[str]:
    """
    Validate the canonical structure of a workflow_definition JSON.

    Returns a (possibly empty) list of human-readable error strings.
    An empty list means the workflow is structurally valid.

    This is a structural/semantic validator — it does NOT check whether
    vision_prompts are good or whether components exist in the DB.
    Those checks are the HSE reviewer's responsibility.
    """
    errors: list[str] = []

    if not isinstance(workflow, dict):
        return ["workflow_definition must be a JSON object."]

    # Required top-level keys
    if "phases" not in workflow:
        errors.append("Missing required field: 'phases'.")
        return errors  # Cannot continue without phases

    phases = workflow["phases"]
    if not isinstance(phases, list) or len(phases) == 0:
        errors.append("'phases' must be a non-empty list.")
        return errors

    valid_phase_types = {"lockout", "tagout", "verification", "maintenance", "restoration"}

    for i, phase in enumerate(phases):
        prefix = f"phases[{i}]"
        if not isinstance(phase, dict):
            errors.append(f"{prefix}: must be an object.")
            continue

        for field in ("phase_id", "phase_type", "sequence", "title", "stages"):
            if field not in phase:
                errors.append(f"{prefix}: missing required field '{field}'.")

        if "phase_type" in phase and phase["phase_type"] not in valid_phase_types:
            errors.append(
                f"{prefix}: invalid phase_type '{phase['phase_type']}'. "
                f"Must be one of {valid_phase_types}."
            )

        stages = phase.get("stages", [])
        if not isinstance(stages, list) or len(stages) == 0:
            errors.append(f"{prefix}: 'stages' must be a non-empty list.")
            continue

        for j, stage in enumerate(stages):
            s_prefix = f"{prefix}.stages[{j}]"
            if not isinstance(stage, dict):
                errors.append(f"{s_prefix}: must be an object.")
                continue

            for field in ("stage_id", "sequence", "title", "steps"):
                if field not in stage:
                    errors.append(f"{s_prefix}: missing required field '{field}'.")

            steps = stage.get("steps", [])
            if not isinstance(steps, list) or len(steps) == 0:
                errors.append(f"{s_prefix}: 'steps' must be a non-empty list.")
                continue

            for k, step in enumerate(steps):
                st_prefix = f"{s_prefix}.steps[{k}]"
                if not isinstance(step, dict):
                    errors.append(f"{st_prefix}: must be an object.")
                    continue

                for field in ("step_id", "sequence", "instruction", "validation"):
                    if field not in step:
                        errors.append(f"{st_prefix}: missing required field '{field}'.")

                validation = step.get("validation", {})
                if isinstance(validation, dict) and "method" not in validation:
                    errors.append(f"{st_prefix}.validation: missing required field 'method'.")

    return errors
