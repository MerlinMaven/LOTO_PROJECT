"""
All domain enums used across models, schemas, and services.

Using str-based enums ensures JSON serialization works without extra config
and that values stored in PostgreSQL are readable strings, not opaque integers.
"""

from __future__ import annotations

from enum import StrEnum


class EnergyType(StrEnum):
    ELECTRICAL = "electrical"
    PNEUMATIC = "pneumatic"
    HYDRAULIC = "hydraulic"
    MECHANICAL = "mechanical"
    THERMAL = "thermal"
    CHEMICAL = "chemical"
    GRAVITATIONAL = "gravitational"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Procedure lifecycle ───────────────────────────────────────────────────────

class ProcedureStatus(StrEnum):
    """
    States for ProcedureVersion.

    Transitions are enforced by the state machine in domain/state_machine.py.
    Only PUBLISHED procedures can be used to start an Intervention.
    Only DRAFT_PENDING_REVIEW procedures can be edited.
    """
    DRAFT_PENDING_REVIEW = "draft_pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    @property
    def is_immutable(self) -> bool:
        """Returns True if the procedure version must no longer be edited."""
        return self in (
            ProcedureStatus.APPROVED,
            ProcedureStatus.PUBLISHED,
            ProcedureStatus.ARCHIVED,
        )


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class GenerationSource(StrEnum):
    MANUAL = "manual"
    LLM_TEXT = "llm_text"
    LLM_VISION = "llm_vision"
    PDF_EXTRACTED = "pdf_extracted"
    VIDEO_EXTRACTED = "video_extracted"


# ── Intervention lifecycle ────────────────────────────────────────────────────

class InterventionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"

    @property
    def is_active(self) -> bool:
        """A machine with an active intervention cannot start another."""
        return self in (InterventionStatus.PENDING, InterventionStatus.IN_PROGRESS,
                        InterventionStatus.PAUSED)

    @property
    def is_terminal(self) -> bool:
        return self in (InterventionStatus.COMPLETED, InterventionStatus.ABORTED)


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    OVERRIDDEN = "overridden"
    FAILED = "failed"
    SKIPPED = "skipped"


class ValidationMethod(StrEnum):
    VISION_AI = "vision_ai"          # YOLO-World (Phase 3)
    MANUAL_OVERRIDE = "manual_override"
    SENSOR = "sensor"                # IoT integration (Phase 4+)


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEventType(StrEnum):
    # Procedure lifecycle
    PROCEDURE_DRAFT_CREATED = "procedure.draft.created"
    PROCEDURE_DRAFT_UPDATED = "procedure.draft.updated"
    PROCEDURE_APPROVED = "procedure.approved"
    PROCEDURE_REJECTED = "procedure.rejected"
    PROCEDURE_PUBLISHED = "procedure.published"
    PROCEDURE_ARCHIVED = "procedure.archived"

    # Intervention lifecycle
    INTERVENTION_STARTED = "intervention.started"
    INTERVENTION_PAUSED = "intervention.paused"
    INTERVENTION_RESUMED = "intervention.resumed"
    INTERVENTION_COMPLETED = "intervention.completed"
    INTERVENTION_ABORTED = "intervention.aborted"

    # Step events
    STEP_ENTERED = "intervention.step.entered"
    STEP_VALIDATED_MANUAL = "intervention.step.validated_manually"
    STEP_VALIDATED_AI = "intervention.step.validated_by_ai"
    STEP_REJECTED = "intervention.step.rejected"
    STEP_OVERRIDE_REQUESTED = "intervention.step.override_requested"
    STEP_OVERRIDE_GRANTED = "intervention.step.override_granted"
    STEP_FAILED = "intervention.step.failed"

    # Machine management
    MACHINE_REGISTERED = "machine.registered"
    MACHINE_COMPONENT_ADDED = "machine.component.added"

    # System / integrity
    SCHEMA_VALIDATION_FAILED = "system.schema_validation_failed"


# ── Phase types (used in workflow_definition JSON) ────────────────────────────

class PhaseType(StrEnum):
    LOCKOUT = "lockout"
    TAGOUT = "tagout"
    VERIFICATION = "verification"
    MAINTENANCE = "maintenance"   # work performed between isolation and restoration
    RESTORATION = "restoration"


class ValidationRuleMethod(StrEnum):
    VISION_DETECTION = "vision_detection"
    INVERSE_VISION_ABSENCE = "inverse_vision_absence"
    MANUAL_CONFIRMATION = "manual_confirmation"
    SENSOR_THRESHOLD = "sensor_threshold"   # Phase 4 extension point
