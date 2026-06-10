"""
Runtime Validation Engine — strategy pattern.

Maps each ValidationRuleMethod from the workflow_definition to a concrete
validation strategy. Phase 5 provides:

    ManualConfirmationStrategy   — operator explicitly confirms the step
    VisionDetectionStub          — YOLO-World placeholder (Phase 6)
    InverseVisionAbsenceStub     — absence-detection placeholder (Phase 6)
    SensorThresholdStub          — IoT sensor placeholder (Phase 6+)

The engine is deterministic: no LLM, no external calls in Phase 5.
Stubs return success=False so the caller knows vision/sensor validation is
not yet available and can guide the operator to use manual confirmation.

Extension protocol (Phase 6):
1. Implement YOLOWorldDetectionStrategy(ValidationStrategy) with real inference.
2. Swap the mapping in ValidationEngine._STRATEGIES.
3. Zero changes to InterventionService or API layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.enums import ValidationRuleMethod


@dataclass
class ValidationContext:
    """Input bag for a validation attempt."""
    step_ref: str
    step_data: dict                          # Step object from workflow_definition
    operator_id: str
    notes: str | None = None
    image_bytes: bytes | None = None         # Future: Quest camera frame
    sensor_value: float | None = None        # Future: IoT sensor reading
    extra: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Outcome of a single validation attempt."""
    success: bool
    method_used: str
    confidence: float | None = None
    notes: str | None = None
    requires_override: bool = False          # True when vision/sensor unavailable
    evidence: dict = field(default_factory=dict)


# ── Strategies ────────────────────────────────────────────────────────────────

class ValidationStrategy(ABC):
    """Abstract base for all validation strategies."""

    @abstractmethod
    async def validate(self, ctx: ValidationContext) -> ValidationResult:
        """
        Attempt to validate the step described by ctx.

        The method is async so that future strategies can make network calls
        (YOLO inference, IoT sensor reads) without refactoring callers.
        """
        ...


class ManualConfirmationStrategy(ValidationStrategy):
    """
    Operator explicitly confirms the step has been completed.

    Phase 5 primary validation path. No hardware, no AI required.
    """

    async def validate(self, ctx: ValidationContext) -> ValidationResult:
        return ValidationResult(
            success=True,
            method_used=ValidationRuleMethod.MANUAL_CONFIRMATION,
            notes=ctx.notes,
        )


class VisionDetectionStub(ValidationStrategy):
    """
    YOLO-World zero-shot detection — Phase 6 extension point.

    Returns success=False with requires_override=True so the caller can
    prompt the operator to use manual confirmation in Phase 5.
    """

    async def validate(self, ctx: ValidationContext) -> ValidationResult:
        return ValidationResult(
            success=False,
            method_used=ValidationRuleMethod.VISION_DETECTION,
            requires_override=True,
            notes=(
                "Vision detection is not yet available (Phase 6). "
                "Use manual confirmation or override to proceed."
            ),
        )


class InverseVisionAbsenceStub(ValidationStrategy):
    """
    Confirms that a hazard state is ABSENT (e.g. guard is back in place).

    Inverse detection — Phase 6 extension point.
    """

    async def validate(self, ctx: ValidationContext) -> ValidationResult:
        return ValidationResult(
            success=False,
            method_used=ValidationRuleMethod.INVERSE_VISION_ABSENCE,
            requires_override=True,
            notes=(
                "Inverse vision absence detection is not yet available (Phase 6). "
                "Use manual confirmation or override to proceed."
            ),
        )


class SensorThresholdStub(ValidationStrategy):
    """
    IoT sensor threshold check (de-energisation confirmation) — Phase 6+ stub.
    """

    async def validate(self, ctx: ValidationContext) -> ValidationResult:
        return ValidationResult(
            success=False,
            method_used=ValidationRuleMethod.SENSOR_THRESHOLD,
            requires_override=True,
            notes=(
                "Sensor threshold validation is not yet available (Phase 6+). "
                "Use manual confirmation or override to proceed."
            ),
        )


# ── Engine ────────────────────────────────────────────────────────────────────

class ValidationEngine:
    """
    Routes a validation request to the appropriate strategy.

    Usage::

        engine = ValidationEngine()
        ctx = ValidationContext(step_ref="ph_lockout.st_1.stp_1", ...)
        method = engine.get_method_for_step(step_data)
        result = await engine.validate(method, ctx)

    Adding a new strategy:
        1. Implement ValidationStrategy subclass.
        2. Add the mapping to _STRATEGIES below.
        3. Done — InterventionService picks it up automatically.
    """

    _STRATEGIES: dict[str, type[ValidationStrategy]] = {
        ValidationRuleMethod.MANUAL_CONFIRMATION: ManualConfirmationStrategy,
        ValidationRuleMethod.VISION_DETECTION: VisionDetectionStub,
        ValidationRuleMethod.INVERSE_VISION_ABSENCE: InverseVisionAbsenceStub,
        ValidationRuleMethod.SENSOR_THRESHOLD: SensorThresholdStub,
    }

    async def validate(
        self,
        method: str,
        ctx: ValidationContext,
    ) -> ValidationResult:
        """
        Execute the strategy for the given method string.

        Falls back to ManualConfirmationStrategy for unknown methods so that
        future workflow additions do not block operators.
        """
        strategy_cls = self._STRATEGIES.get(method, ManualConfirmationStrategy)
        return await strategy_cls().validate(ctx)

    @staticmethod
    def get_method_for_step(step_data: dict) -> str:
        """Extract the validation method string from a workflow step dict."""
        return (
            step_data.get("validation", {}).get("method")
            or ValidationRuleMethod.MANUAL_CONFIRMATION
        )
