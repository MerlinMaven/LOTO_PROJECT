"""
Integration tests for /api/v1/interventions endpoints.

Covers the full HTTP → schema validation → router → mocked service →
error handler → response body path for all Phase 5 endpoints.

The client fixture (from conftest.py) mocks all service dependencies so no
database is needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import (
    InterventionNotActiveError,
    InvalidStatusTransitionError,
    MachineAlreadyInInterventionError,
    NoActiveVersionError,
    NotFoundError,
    StepAlreadyCompletedError,
)
from app.domain.enums import InterventionStatus, StepStatus
from app.schemas.intervention import (
    CurrentStepContext,
    InterventionProgress,
    InterventionRead,
)
from app.schemas.audit import AuditEventRead


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


_INTERVENTION_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_MACHINE_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_VERSION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_REF_1 = "ph_lockout.st_elec.stp_1"


def _sample_read(
    status: InterventionStatus = InterventionStatus.IN_PROGRESS,
    current_step_ref: str | None = _REF_1,
) -> InterventionRead:
    return InterventionRead(
        id=_INTERVENTION_ID,
        machine_id=_MACHINE_ID,
        procedure_version_id=_VERSION_ID,
        operator_name="bob",
        status=status,
        current_step_ref=current_step_ref,
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


def _sample_progress() -> InterventionProgress:
    return InterventionProgress(
        intervention_id=_INTERVENTION_ID,
        total_steps=5,
        completed_steps=2,
        overridden_steps=0,
        failed_steps=1,
        pending_steps=2,
        completion_percentage=40.0,
    )


def _sample_step_context() -> CurrentStepContext:
    return CurrentStepContext(
        intervention_id=_INTERVENTION_ID,
        intervention_status=InterventionStatus.IN_PROGRESS,
        current_step_ref=_REF_1,
        overall_step_number=1,
        total_steps_overall=5,
        step_instruction="Turn off main breaker",
        step_validation_method="manual_confirmation",
        safety_note="DANGER: verify voltage at panel before touching",
        warnings=["High voltage present"],
        rollback_instruction=None,
        phase_id="ph_lockout",
        phase_type="lockout",
        phase_title="Lockout Phase",
        stage_id="st_elec",
        stage_title="Electrical",
        previous_step_ref=None,
        next_step_ref="ph_lockout.st_elec.stp_2",
        step_record=None,
    )


def _sample_audit_event() -> AuditEventRead:
    return AuditEventRead(
        id=uuid.uuid4(),
        event_type="intervention.started",
        actor_id="bob",
        machine_id=_MACHINE_ID,
        intervention_id=_INTERVENTION_ID,
        procedure_version_id=_VERSION_ID,
        step_ref=None,
        payload={},
        ip_address="127.0.0.1",
        occurred_at=_now(),
        event_hash="abc123",
    )


# ── POST /api/v1/interventions ────────────────────────────────────────────────


class TestStartIntervention:
    async def test_201_on_valid_payload(self, client, mock_intervention_service):
        mock_intervention_service.start_intervention.return_value = _sample_read()

        response = await client.post(
            "/api/v1/interventions",
            json={"machine_id": str(_MACHINE_ID), "operator_name": "bob"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["operator_name"] == "bob"
        assert body["status"] == "in_progress"
        mock_intervention_service.start_intervention.assert_awaited_once()

    async def test_422_on_missing_machine_id(self, client):
        response = await client.post(
            "/api/v1/interventions",
            json={"operator_name": "bob"},
        )
        assert response.status_code == 422

    async def test_422_when_no_published_procedure(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.start_intervention.side_effect = NoActiveVersionError(
            _MACHINE_ID
        )

        response = await client.post(
            "/api/v1/interventions",
            json={"machine_id": str(_MACHINE_ID), "operator_name": "bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_ACTIVE_VERSION"

    async def test_409_when_machine_already_active(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.start_intervention.side_effect = (
            MachineAlreadyInInterventionError(_MACHINE_ID)
        )

        response = await client.post(
            "/api/v1/interventions",
            json={"machine_id": str(_MACHINE_ID), "operator_name": "bob"},
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MACHINE_ALREADY_IN_INTERVENTION"


# ── GET /api/v1/interventions/{id} ────────────────────────────────────────────


class TestGetIntervention:
    async def test_200_returns_intervention(self, client, mock_intervention_service):
        mock_intervention_service.get_intervention.return_value = _sample_read()

        response = await client.get(f"/api/v1/interventions/{_INTERVENTION_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == str(_INTERVENTION_ID)

    async def test_404_when_not_found(self, client, mock_intervention_service):
        mock_intervention_service.get_intervention.side_effect = NotFoundError(
            "Intervention", _INTERVENTION_ID
        )

        response = await client.get(f"/api/v1/interventions/{_INTERVENTION_ID}")

        assert response.status_code == 404


# ── POST /api/v1/interventions/{id}/pause ─────────────────────────────────────


class TestPauseIntervention:
    async def test_200_pauses_intervention(self, client, mock_intervention_service):
        mock_intervention_service.pause_intervention.return_value = _sample_read(
            status=InterventionStatus.PAUSED
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/pause",
            json={"reason": "shift change"},
            headers={"X-User-Id": "supervisor"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "paused"
        mock_intervention_service.pause_intervention.assert_awaited_once()

    async def test_200_with_no_reason(self, client, mock_intervention_service):
        mock_intervention_service.pause_intervention.return_value = _sample_read(
            status=InterventionStatus.PAUSED
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/pause",
            json={},
            headers={"X-User-Id": "supervisor"},
        )

        assert response.status_code == 200

    async def test_422_when_already_terminal(self, client, mock_intervention_service):
        mock_intervention_service.pause_intervention.side_effect = (
            InterventionNotActiveError(_INTERVENTION_ID, "completed")
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/pause",
            json={},
            headers={"X-User-Id": "supervisor"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INTERVENTION_NOT_ACTIVE"


# ── POST /api/v1/interventions/{id}/resume ────────────────────────────────────


class TestResumeIntervention:
    async def test_200_resumes_intervention(self, client, mock_intervention_service):
        mock_intervention_service.resume_intervention.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/resume",
            headers={"X-User-Id": "supervisor"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    async def test_422_on_invalid_transition(self, client, mock_intervention_service):
        mock_intervention_service.resume_intervention.side_effect = (
            InvalidStatusTransitionError(
                from_status="completed",
                to_status="in_progress",
                resource="intervention",
            )
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/resume",
            headers={"X-User-Id": "supervisor"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ── POST /api/v1/interventions/{id}/complete ──────────────────────────────────


class TestCompleteIntervention:
    async def test_200_completes_intervention(self, client, mock_intervention_service):
        mock_intervention_service.complete_intervention.return_value = _sample_read(
            status=InterventionStatus.COMPLETED
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/complete",
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"


# ── POST /api/v1/interventions/{id}/abort ─────────────────────────────────────


class TestAbortIntervention:
    async def test_200_aborts_intervention(self, client, mock_intervention_service):
        mock_intervention_service.abort_intervention.return_value = _sample_read(
            status=InterventionStatus.ABORTED
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/abort",
            json={"reason": "emergency"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "aborted"

    async def test_422_missing_reason(self, client, mock_intervention_service):
        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/abort",
            json={},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422


# ── GET /api/v1/interventions/{id}/current-step ───────────────────────────────


class TestGetCurrentStep:
    async def test_200_returns_step_context(self, client, mock_intervention_service):
        mock_intervention_service.get_current_step.return_value = (
            _sample_step_context()
        )

        response = await client.get(
            f"/api/v1/interventions/{_INTERVENTION_ID}/current-step"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["current_step_ref"] == _REF_1
        assert body["step_instruction"] == "Turn off main breaker"
        assert body["phase_id"] == "ph_lockout"
        assert body["next_step_ref"] == "ph_lockout.st_elec.stp_2"
        assert body["previous_step_ref"] is None

    async def test_404_when_not_found(self, client, mock_intervention_service):
        mock_intervention_service.get_current_step.side_effect = NotFoundError(
            "Intervention", _INTERVENTION_ID
        )

        response = await client.get(
            f"/api/v1/interventions/{_INTERVENTION_ID}/current-step"
        )

        assert response.status_code == 404


# ── GET /api/v1/interventions/{id}/progress ───────────────────────────────────


class TestGetProgress:
    async def test_200_returns_progress(self, client, mock_intervention_service):
        mock_intervention_service.get_progress.return_value = _sample_progress()

        response = await client.get(
            f"/api/v1/interventions/{_INTERVENTION_ID}/progress"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total_steps"] == 5
        assert body["completed_steps"] == 2
        assert body["completion_percentage"] == 40.0


# ── GET /api/v1/interventions/{id}/audit ─────────────────────────────────────


class TestGetAuditTrail:
    async def test_200_returns_audit_events(
        self, client, mock_audit_service
    ):
        mock_audit_service.get_intervention_trail = __import__(
            "unittest.mock", fromlist=["AsyncMock"]
        ).AsyncMock(return_value=[_sample_audit_event()])

        response = await client.get(
            f"/api/v1/interventions/{_INTERVENTION_ID}/audit"
        )

        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "intervention.started"


# ── POST /steps/{ref}/enter ───────────────────────────────────────────────────


class TestEnterStep:
    async def test_200_enters_step(self, client, mock_intervention_service):
        mock_intervention_service.enter_step.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/enter",
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        mock_intervention_service.enter_step.assert_awaited_once()

    async def test_422_when_step_already_completed(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.enter_step.side_effect = StepAlreadyCompletedError(
            _REF_1, "validated"
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/enter",
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_ALREADY_COMPLETED"


# ── POST /steps/{ref}/validate ────────────────────────────────────────────────


class TestValidateStep:
    async def test_200_validates_step(self, client, mock_intervention_service):
        mock_intervention_service.validate_step.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/validate",
            json={"confirmed_by": "alice", "notes": "all clear"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        mock_intervention_service.validate_step.assert_awaited_once()

    async def test_422_missing_confirmed_by(self, client, mock_intervention_service):
        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/validate",
            json={},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422

    async def test_422_when_intervention_not_active(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.validate_step.side_effect = (
            InterventionNotActiveError(_INTERVENTION_ID, "completed")
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/validate",
            json={"confirmed_by": "alice"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INTERVENTION_NOT_ACTIVE"


# ── POST /steps/{ref}/reject ──────────────────────────────────────────────────


class TestRejectStep:
    async def test_200_rejects_step(self, client, mock_intervention_service):
        mock_intervention_service.reject_step.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/reject",
            json={"reason": "voltage still present"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        mock_intervention_service.reject_step.assert_awaited_once()

    async def test_422_missing_reason(self, client, mock_intervention_service):
        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/reject",
            json={},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422


# ── POST /steps/{ref}/override ────────────────────────────────────────────────


class TestOverrideStep:
    async def test_200_overrides_step_with_evidence(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.override_step.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/override",
            json={
                "reason": "vision unavailable in Phase 5",
                "evidence_url": "https://storage.example.com/photo123.jpg",
                "photo_reference": "IMG_0042",
                "requires_hse_review": True,
            },
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        mock_intervention_service.override_step.assert_awaited_once()

    async def test_200_override_without_optional_fields(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.override_step.return_value = _sample_read()

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/override",
            json={"reason": "manual bypass"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200

    async def test_422_missing_reason(self, client, mock_intervention_service):
        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/override",
            json={},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422

    async def test_422_step_already_completed(
        self, client, mock_intervention_service
    ):
        mock_intervention_service.override_step.side_effect = (
            StepAlreadyCompletedError(_REF_1, "validated")
        )

        response = await client.post(
            f"/api/v1/interventions/{_INTERVENTION_ID}/steps/{_REF_1}/override",
            json={"reason": "bypass"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_ALREADY_COMPLETED"
