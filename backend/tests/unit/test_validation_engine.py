"""
Unit tests for the Runtime Validation Engine (strategy pattern).

All strategies are async — pytest-asyncio auto-mode handles the event loop.
No mocks needed: the engine and strategies are pure Python.
"""

import pytest

from app.domain.enums import ValidationRuleMethod
from app.runtime.validation_engine import (
    InverseVisionAbsenceStub,
    ManualConfirmationStrategy,
    SensorThresholdStub,
    ValidationContext,
    ValidationEngine,
    VisionDetectionStub,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _ctx(
    method: str = ValidationRuleMethod.MANUAL_CONFIRMATION,
    notes: str | None = None,
) -> ValidationContext:
    return ValidationContext(
        step_ref="ph_lockout.st_elec.stp_1",
        step_data={"validation": {"method": method}},
        operator_id="operator_1",
        notes=notes,
    )


_engine = ValidationEngine()


# ── ManualConfirmationStrategy ────────────────────────────────────────────────


class TestManualConfirmationStrategy:
    async def test_returns_success(self):
        result = await ManualConfirmationStrategy().validate(_ctx())
        assert result.success is True

    async def test_method_used_is_manual(self):
        result = await ManualConfirmationStrategy().validate(_ctx())
        assert result.method_used == ValidationRuleMethod.MANUAL_CONFIRMATION

    async def test_no_override_required(self):
        result = await ManualConfirmationStrategy().validate(_ctx())
        assert result.requires_override is False

    async def test_notes_passed_through(self):
        result = await ManualConfirmationStrategy().validate(_ctx(notes="checked ok"))
        assert result.notes == "checked ok"


# ── VisionDetectionStub ───────────────────────────────────────────────────────


class TestVisionDetectionStub:
    async def test_returns_failure(self):
        result = await VisionDetectionStub().validate(_ctx())
        assert result.success is False

    async def test_method_used_is_vision_detection(self):
        result = await VisionDetectionStub().validate(_ctx())
        assert result.method_used == ValidationRuleMethod.VISION_DETECTION

    async def test_requires_override_true(self):
        result = await VisionDetectionStub().validate(_ctx())
        assert result.requires_override is True

    async def test_notes_mention_phase6(self):
        result = await VisionDetectionStub().validate(_ctx())
        assert "Phase 6" in (result.notes or "")


# ── InverseVisionAbsenceStub ──────────────────────────────────────────────────


class TestInverseVisionAbsenceStub:
    async def test_returns_failure(self):
        result = await InverseVisionAbsenceStub().validate(_ctx())
        assert result.success is False

    async def test_requires_override_true(self):
        result = await InverseVisionAbsenceStub().validate(_ctx())
        assert result.requires_override is True

    async def test_method_used(self):
        result = await InverseVisionAbsenceStub().validate(_ctx())
        assert result.method_used == ValidationRuleMethod.INVERSE_VISION_ABSENCE


# ── SensorThresholdStub ───────────────────────────────────────────────────────


class TestSensorThresholdStub:
    async def test_returns_failure(self):
        result = await SensorThresholdStub().validate(_ctx())
        assert result.success is False

    async def test_requires_override_true(self):
        result = await SensorThresholdStub().validate(_ctx())
        assert result.requires_override is True

    async def test_method_used(self):
        result = await SensorThresholdStub().validate(_ctx())
        assert result.method_used == ValidationRuleMethod.SENSOR_THRESHOLD


# ── ValidationEngine routing ──────────────────────────────────────────────────


class TestValidationEngineRouting:
    async def test_routes_manual_to_success(self):
        ctx = _ctx(ValidationRuleMethod.MANUAL_CONFIRMATION)
        result = await _engine.validate(ValidationRuleMethod.MANUAL_CONFIRMATION, ctx)
        assert result.success is True

    async def test_routes_vision_to_stub(self):
        ctx = _ctx(ValidationRuleMethod.VISION_DETECTION)
        result = await _engine.validate(ValidationRuleMethod.VISION_DETECTION, ctx)
        assert result.success is False
        assert result.requires_override is True

    async def test_routes_inverse_to_stub(self):
        ctx = _ctx(ValidationRuleMethod.INVERSE_VISION_ABSENCE)
        result = await _engine.validate(ValidationRuleMethod.INVERSE_VISION_ABSENCE, ctx)
        assert result.success is False
        assert result.requires_override is True

    async def test_routes_sensor_to_stub(self):
        ctx = _ctx(ValidationRuleMethod.SENSOR_THRESHOLD)
        result = await _engine.validate(ValidationRuleMethod.SENSOR_THRESHOLD, ctx)
        assert result.success is False
        assert result.requires_override is True

    async def test_unknown_method_falls_back_to_manual(self):
        ctx = _ctx()
        result = await _engine.validate("unknown_future_method", ctx)
        assert result.success is True
        assert result.requires_override is False


# ── get_method_for_step ───────────────────────────────────────────────────────


class TestGetMethodForStep:
    def test_extracts_method_from_validation_block(self):
        step = {"validation": {"method": "vision_detection"}}
        assert _engine.get_method_for_step(step) == "vision_detection"

    def test_defaults_to_manual_when_no_validation_key(self):
        assert (
            _engine.get_method_for_step({})
            == ValidationRuleMethod.MANUAL_CONFIRMATION
        )

    def test_defaults_to_manual_when_method_is_null(self):
        step = {"validation": {"method": None}}
        assert (
            _engine.get_method_for_step(step)
            == ValidationRuleMethod.MANUAL_CONFIRMATION
        )

    def test_defaults_to_manual_when_method_is_empty_string(self):
        step = {"validation": {"method": ""}}
        assert (
            _engine.get_method_for_step(step)
            == ValidationRuleMethod.MANUAL_CONFIRMATION
        )
