"""
Unit tests for InterventionService Phase 5 methods.

Repository and audit service calls are mocked with AsyncMock.
_get_read is patched to return a fixed InterventionRead so tests are not
coupled to ORM serialisation details — the important assertions are on
status mutations and audit calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import InterventionNotActiveError, NotFoundError, StepAlreadyCompletedError
from app.domain.enums import InterventionStatus, StepStatus, ValidationMethod
from app.schemas.intervention import (
    InterventionRead,
    StepOverrideRequest,
    StepRejectRequest,
    StepValidationRequest,
)
from app.services.intervention_service import InterventionService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sample_workflow() -> dict:
    return {
        "phases": [
            {
                "phase_id": "ph_lockout",
                "phase_type": "lockout",
                "title": "Lockout Phase",
                "stages": [
                    {
                        "stage_id": "st_elec",
                        "title": "Electrical",
                        "steps": [
                            {
                                "step_id": "stp_1",
                                "instruction": "Turn off main breaker",
                                "validation": {"method": "manual_confirmation"},
                            },
                            {
                                "step_id": "stp_2",
                                "instruction": "Apply padlock",
                                "validation": {"method": "manual_confirmation"},
                            },
                        ],
                    }
                ],
            }
        ]
    }


_REF_1 = "ph_lockout.st_elec.stp_1"
_REF_2 = "ph_lockout.st_elec.stp_2"


def _make_intervention(
    status: InterventionStatus = InterventionStatus.IN_PROGRESS,
    current_step_ref: str | None = _REF_1,
) -> MagicMock:
    iv = MagicMock()
    iv.id = uuid.uuid4()
    iv.machine_id = uuid.uuid4()
    iv.operator_name = "bob"
    iv.status = status
    iv.current_step_ref = current_step_ref
    iv.procedure_version_id = uuid.uuid4()
    iv.steps = []
    iv.procedure_version = MagicMock()
    iv.procedure_version.workflow_definition = _sample_workflow()
    return iv


def _sample_read(intervention_id: uuid.UUID | None = None) -> InterventionRead:
    return InterventionRead(
        id=intervention_id or uuid.uuid4(),
        machine_id=uuid.uuid4(),
        procedure_version_id=uuid.uuid4(),
        operator_name="bob",
        status=InterventionStatus.IN_PROGRESS,
        current_step_ref=_REF_1,
        started_at=_now(),
        completed_at=None,
        aborted_at=None,
        abort_reason=None,
        pdf_report_url=None,
        operator_signature_url=None,
        steps=[],
        created_at=_now(),
        updated_at=_now(),
    )


def _make_service() -> tuple[InterventionService, MagicMock, MagicMock]:
    mock_repo = MagicMock()
    mock_procedure_repo = MagicMock()
    mock_audit = MagicMock()
    mock_audit.record_event = AsyncMock()
    mock_vision = MagicMock()
    svc = InterventionService(
        intervention_repo=mock_repo,
        procedure_repo=mock_procedure_repo,
        audit_service=mock_audit,
        vision_service=mock_vision,
    )
    return svc, mock_repo, mock_audit


# ── pause_intervention ────────────────────────────────────────────────────────


class TestPauseIntervention:
    async def test_sets_status_to_paused(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(status=InterventionStatus.IN_PROGRESS)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.pause_intervention(iv.id, reason="shift change", actor_id="alice")

        assert iv.status == InterventionStatus.PAUSED

    async def test_records_audit_event(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(status=InterventionStatus.IN_PROGRESS)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.pause_intervention(iv.id, reason="lunch", actor_id="alice")

        mock_audit.record_event.assert_awaited_once()

    async def test_raises_when_already_terminal(self):
        svc, mock_repo, _ = _make_service()
        iv = _make_intervention(status=InterventionStatus.COMPLETED)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)

        with pytest.raises(InterventionNotActiveError):
            await svc.pause_intervention(iv.id)

    async def test_raises_not_found_when_missing(self):
        svc, mock_repo, _ = _make_service()
        mock_repo.get_with_steps = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.pause_intervention(uuid.uuid4())


# ── resume_intervention ───────────────────────────────────────────────────────


class TestResumeIntervention:
    async def test_sets_status_to_in_progress(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(status=InterventionStatus.PAUSED)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.resume_intervention(iv.id, actor_id="alice")

        assert iv.status == InterventionStatus.IN_PROGRESS

    async def test_records_audit_event(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(status=InterventionStatus.PAUSED)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.resume_intervention(iv.id, actor_id="alice")

        mock_audit.record_event.assert_awaited_once()


# ── enter_step ────────────────────────────────────────────────────────────────


class TestEnterStep:
    async def test_creates_step_record_on_first_entry(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=None)
        mock_repo.add_step = AsyncMock()
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.enter_step(iv.id, _REF_1, actor_id="bob")

        mock_repo.add_step.assert_awaited_once()

    async def test_sets_current_step_ref(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(current_step_ref=None)
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=None)
        mock_repo.add_step = AsyncMock()
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.enter_step(iv.id, _REF_1, actor_id="bob")

        assert iv.current_step_ref == _REF_1

    async def test_increments_attempts_on_retry(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.FAILED  # can re-enter from FAILED
        existing_step.started_at = _now()
        existing_step.attempts = 1
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.enter_step(iv.id, _REF_1, actor_id="bob")

        assert existing_step.attempts == 2

    async def test_raises_on_terminal_step(self):
        svc, mock_repo, _ = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.VALIDATED  # terminal
        existing_step.started_at = _now()
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)

        with pytest.raises(StepAlreadyCompletedError):
            await svc.enter_step(iv.id, _REF_1, actor_id="bob")

    async def test_records_audit_event(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=None)
        mock_repo.add_step = AsyncMock()
        sample = _sample_read(iv.id)

        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.enter_step(iv.id, _REF_1, actor_id="bob")

        mock_audit.record_event.assert_awaited_once()


# ── validate_step ─────────────────────────────────────────────────────────────


class TestValidateStep:
    async def test_marks_step_validated(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(current_step_ref=_REF_1)
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepValidationRequest(confirmed_by="alice")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.validate_step(iv.id, _REF_1, req, actor_id="bob")

        assert existing_step.status == StepStatus.VALIDATED

    async def test_advances_current_step_ref(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(current_step_ref=_REF_1)
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepValidationRequest(confirmed_by="alice")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.validate_step(iv.id, _REF_1, req, actor_id="bob")

        assert iv.current_step_ref == _REF_2

    async def test_current_step_ref_is_none_after_last_step(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention(current_step_ref=_REF_2)
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepValidationRequest(confirmed_by="alice")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.validate_step(iv.id, _REF_2, req, actor_id="bob")

        assert iv.current_step_ref is None

    async def test_sets_validation_method_manual_override(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepValidationRequest(confirmed_by="alice")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.validate_step(iv.id, _REF_1, req, actor_id="bob")

        assert existing_step.validation_method_used == ValidationMethod.MANUAL_OVERRIDE

    async def test_records_audit_event(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepValidationRequest(confirmed_by="alice")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.validate_step(iv.id, _REF_1, req, actor_id="bob")

        mock_audit.record_event.assert_awaited_once()


# ── reject_step ───────────────────────────────────────────────────────────────


class TestRejectStep:
    async def test_marks_step_failed(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepRejectRequest(reason="machine not in expected state")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.reject_step(iv.id, _REF_1, req, actor_id="bob")

        assert existing_step.status == StepStatus.FAILED

    async def test_stores_rejection_reason(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepRejectRequest(reason="voltage not zero")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.reject_step(iv.id, _REF_1, req, actor_id="bob")

        assert existing_step.override_reason == "voltage not zero"

    async def test_creates_step_record_when_absent(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=None)
        mock_repo.add_step = AsyncMock()
        sample = _sample_read(iv.id)

        req = StepRejectRequest(reason="unexpected state")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.reject_step(iv.id, _REF_1, req, actor_id="bob")

        mock_repo.add_step.assert_awaited_once()

    async def test_records_audit_event(self):
        svc, mock_repo, mock_audit = _make_service()
        iv = _make_intervention()
        existing_step = MagicMock()
        existing_step.status = StepStatus.IN_PROGRESS
        mock_repo.get_with_steps = AsyncMock(return_value=iv)
        mock_repo.get_step = AsyncMock(return_value=existing_step)
        sample = _sample_read(iv.id)

        req = StepRejectRequest(reason="bad state")
        with patch.object(svc, "_get_read", AsyncMock(return_value=sample)):
            await svc.reject_step(iv.id, _REF_1, req, actor_id="bob")

        mock_audit.record_event.assert_awaited_once()


# ── Workflow navigation helpers ───────────────────────────────────────────────


class TestWorkflowHelpers:
    def test_flatten_steps_returns_all_steps(self):
        flat = InterventionService._flatten_steps(_sample_workflow())
        refs = [r for r, _, _, _ in flat]
        assert refs == [_REF_1, _REF_2]

    def test_flatten_steps_empty_workflow(self):
        assert InterventionService._flatten_steps({}) == []

    def test_extract_first_step_ref(self):
        ref = InterventionService._extract_first_step_ref(_sample_workflow())
        assert ref == _REF_1

    def test_extract_first_step_ref_empty(self):
        assert InterventionService._extract_first_step_ref({}) is None

    def test_extract_next_step_ref_from_first(self):
        ref = InterventionService._extract_next_step_ref(_sample_workflow(), _REF_1)
        assert ref == _REF_2

    def test_extract_next_step_ref_from_last_returns_none(self):
        ref = InterventionService._extract_next_step_ref(_sample_workflow(), _REF_2)
        assert ref is None

    def test_extract_prev_step_ref_from_second(self):
        ref = InterventionService._extract_prev_step_ref(_sample_workflow(), _REF_2)
        assert ref == _REF_1

    def test_extract_prev_step_ref_from_first_returns_none(self):
        ref = InterventionService._extract_prev_step_ref(_sample_workflow(), _REF_1)
        assert ref is None

    def test_find_workflow_step_found(self):
        step = InterventionService._find_workflow_step(_sample_workflow(), _REF_1)
        assert step is not None
        assert step["instruction"] == "Turn off main breaker"

    def test_find_workflow_step_not_found(self):
        step = InterventionService._find_workflow_step(_sample_workflow(), "ph_x.st_y.stp_z")
        assert step is None

    def test_find_workflow_step_malformed_ref(self):
        step = InterventionService._find_workflow_step(_sample_workflow(), "bad_ref")
        assert step is None
