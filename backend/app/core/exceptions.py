"""
Domain exception hierarchy.

All domain-specific errors inherit from SmartLOTOError so callers can
catch broadly or narrowly as needed.

HTTP mapping lives in api/error_handlers.py — exceptions carry no HTTP
knowledge so the domain stays framework-agnostic.
"""

from __future__ import annotations

from uuid import UUID


class SmartLOTOError(Exception):
    """Root exception for all SmartLOTO domain errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ── Resource Not Found ────────────────────────────────────────────────────────

class NotFoundError(SmartLOTOError):
    """Raised when a requested entity does not exist."""

    def __init__(self, resource: str, identifier: str | UUID) -> None:
        super().__init__(
            f"{resource} '{identifier}' not found.",
            {"resource": resource, "identifier": str(identifier)},
        )


# ── Conflict / Uniqueness ─────────────────────────────────────────────────────

class ConflictError(SmartLOTOError):
    """Raised when an operation would violate a uniqueness constraint."""


class MachineAlreadyHasProcedureError(ConflictError):
    def __init__(self, machine_id: UUID) -> None:
        super().__init__(
            f"Machine '{machine_id}' already has a procedure. "
            "Create a new version instead of a new procedure.",
            {"machine_id": str(machine_id)},
        )


class MachineAlreadyInInterventionError(ConflictError):
    def __init__(self, machine_id: UUID) -> None:
        super().__init__(
            f"Machine '{machine_id}' already has an active intervention in progress.",
            {"machine_id": str(machine_id)},
        )


# ── State Machine Violations ──────────────────────────────────────────────────

class InvalidStatusTransitionError(SmartLOTOError):
    """Raised when a requested state transition is not allowed by the state machine."""

    def __init__(self, from_status: str, to_status: str, resource: str = "procedure") -> None:
        super().__init__(
            f"Cannot transition {resource} from '{from_status}' to '{to_status}'.",
            {"from_status": from_status, "to_status": to_status},
        )


class ProcedureNotApprovableError(SmartLOTOError):
    """Raised when trying to approve a procedure version that is not in review."""

    def __init__(self, current_status: str) -> None:
        super().__init__(
            f"Procedure version cannot be approved from status '{current_status}'. "
            "Only 'draft_pending_review' versions can be approved.",
            {"current_status": current_status},
        )


class ProcedureNotPublishableError(SmartLOTOError):
    """Raised when trying to publish a procedure version that is not approved."""

    def __init__(self, current_status: str) -> None:
        super().__init__(
            f"Procedure version cannot be published from status '{current_status}'. "
            "Only 'approved' versions can be published.",
            {"current_status": current_status},
        )


class ApprovedProcedureImmutableError(SmartLOTOError):
    """Raised when attempting to modify an approved, published, or archived procedure version."""

    def __init__(self, version_id: UUID, status: str) -> None:
        super().__init__(
            f"Procedure version '{version_id}' is '{status}' and cannot be modified. "
            "Create a new draft version.",
            {"version_id": str(version_id), "status": status},
        )


# ── Business Rule Violations ──────────────────────────────────────────────────

class SelfApprovalForbiddenError(SmartLOTOError):
    """4-eyes principle: the author of a procedure cannot approve it themselves."""

    def __init__(self, user_identifier: str) -> None:
        super().__init__(
            "Self-approval is forbidden. The procedure author cannot approve their own work.",
            {"user_identifier": user_identifier},
        )


class NoActiveVersionError(SmartLOTOError):
    """Raised when a machine has no published (active) procedure."""

    def __init__(self, machine_id: UUID) -> None:
        super().__init__(
            f"Machine '{machine_id}' has no published procedure. "
            "An approved and published procedure is required to start an intervention.",
            {"machine_id": str(machine_id)},
        )


class InterventionStepsIncompleteError(SmartLOTOError):
    """Raised when attempting to close an intervention with pending steps."""

    def __init__(self, intervention_id: UUID, pending_count: int) -> None:
        super().__init__(
            f"Intervention '{intervention_id}' cannot be closed: "
            f"{pending_count} step(s) are still pending.",
            {"intervention_id": str(intervention_id), "pending_count": pending_count},
        )


class InterventionNotActiveError(SmartLOTOError):
    """Raised when an action requires an active intervention but it is not active."""

    def __init__(self, intervention_id: UUID, current_status: str) -> None:
        super().__init__(
            f"Intervention '{intervention_id}' is not active (current status: {current_status}). "
            "Only pending, in_progress, or paused interventions can be acted upon.",
            {"intervention_id": str(intervention_id), "current_status": current_status},
        )


class StepAlreadyCompletedError(SmartLOTOError):
    """Raised when trying to transition a step that is already in a terminal state."""

    def __init__(self, step_ref: str, current_status: str) -> None:
        super().__init__(
            f"Step '{step_ref}' is already '{current_status}' and cannot be modified.",
            {"step_ref": step_ref, "current_status": current_status},
        )


# ── Validation ────────────────────────────────────────────────────────────────

class WorkflowValidationError(SmartLOTOError):
    """Raised when a workflow_definition JSON fails schema validation."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(
            "Workflow definition failed validation.",
            {"errors": errors},
        )


class PaginationError(SmartLOTOError):
    """Raised for invalid pagination parameters."""
