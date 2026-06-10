"""
Integration tests for /api/v1/procedures endpoints.

Covers the full procedure lifecycle:
  draft creation → approval (4-eyes) → publish → archive-on-republish

Each test exercises HTTP → schema validation → router → mocked service →
error handler → response body.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    MachineAlreadyHasProcedureError,
    NotFoundError,
    ProcedureNotApprovableError,
    ProcedureNotPublishableError,
    SelfApprovalForbiddenError,
)
from app.domain.enums import ApprovalDecision, GenerationSource, ProcedureStatus
from app.schemas.procedure import (
    ApprovalRead,
    ProcedurePublishResponse,
    ProcedureRead,
    ProcedureVersionRead,
    ProcedureVersionSummary,
)

_VALID_WORKFLOW = {
    "phases": [
        {
            "phase_id": "ph_lockout",
            "phase_type": "lockout",
            "sequence": 1,
            "title": "Lockout",
            "stages": [
                {
                    "stage_id": "st_1",
                    "sequence": 1,
                    "title": "Electrical Isolation",
                    "steps": [
                        {
                            "step_id": "stp_1",
                            "sequence": 1,
                            "instruction": "Open the main circuit breaker.",
                            "validation": {"method": "manual_confirmation"},
                        }
                    ],
                }
            ],
        }
    ]
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _version_summary(version_id=None, status=ProcedureStatus.DRAFT_PENDING_REVIEW):
    return ProcedureVersionSummary(
        id=version_id or uuid.uuid4(),
        version_number="1.0.0",
        status=status,
        created_by="alice",
        created_at=_now(),
    )


# ── POST /api/v1/procedures ───────────────────────────────────────────────────

class TestCreateDraftProcedure:
    async def test_201_on_valid_payload(
        self, client, mock_procedure_service, sample_procedure_read
    ):
        mock_procedure_service.create_draft.return_value = sample_procedure_read

        response = await client.post(
            "/api/v1/procedures",
            json={
                "machine_id": str(sample_procedure_read.machine_id),
                "title": "Hydraulic Press LOTO Procedure",
                "created_by": "alice",
                "workflow_definition": _VALID_WORKFLOW,
            },
            headers={"X-User-Id": "alice"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Hydraulic Press LOTO Procedure"
        assert data["created_by"] == "alice"
        mock_procedure_service.create_draft.assert_awaited_once()

    async def test_422_on_missing_required_fields(self, client):
        response = await client.post("/api/v1/procedures", json={})
        assert response.status_code == 422

    async def test_422_on_empty_workflow_definition(self, client):
        response = await client.post(
            "/api/v1/procedures",
            json={
                "machine_id": str(uuid.uuid4()),
                "title": "Test",
                "created_by": "alice",
                "workflow_definition": {},  # empty — fails field_validator
            },
        )
        assert response.status_code == 422

    async def test_409_when_machine_already_has_procedure(
        self, client, mock_procedure_service, sample_machine_id
    ):
        mock_procedure_service.create_draft.side_effect = MachineAlreadyHasProcedureError(
            sample_machine_id
        )

        response = await client.post(
            "/api/v1/procedures",
            json={
                "machine_id": str(sample_machine_id),
                "title": "Duplicate",
                "created_by": "alice",
                "workflow_definition": _VALID_WORKFLOW,
            },
        )

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "MACHINE_ALREADY_HAS_PROCEDURE"


# ── GET /api/v1/procedures/{id} ───────────────────────────────────────────────

class TestGetProcedure:
    async def test_200_returns_procedure(
        self, client, mock_procedure_service, sample_procedure_read, sample_procedure_id
    ):
        mock_procedure_service.get_procedure.return_value = sample_procedure_read

        response = await client.get(f"/api/v1/procedures/{sample_procedure_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_procedure_id)

    async def test_404_when_not_found(self, client, mock_procedure_service):
        unknown = uuid.uuid4()
        mock_procedure_service.get_procedure.side_effect = NotFoundError("Procedure", unknown)

        response = await client.get(f"/api/v1/procedures/{unknown}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


# ── POST /api/v1/procedures/{id}/approve ─────────────────────────────────────

class TestApproveProcedure:
    def _make_approval_read(self, version_id=None):
        return ApprovalRead(
            id=uuid.uuid4(),
            version_id=version_id or uuid.uuid4(),
            approved_by="bob",
            decision=ApprovalDecision.APPROVED,
            notes=None,
            decided_at=_now(),
            is_superseded=False,
        )

    async def test_200_on_valid_approval(
        self, client, mock_procedure_service, sample_procedure_id, sample_version_id
    ):
        mock_procedure_service.approve_procedure.return_value = self._make_approval_read(
            sample_version_id
        )

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/approve",
            json={"decision": "approved", "approved_by": "bob"},
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "approved"
        assert data["approved_by"] == "bob"

    async def test_403_on_self_approval(
        self, client, mock_procedure_service, sample_procedure_id
    ):
        mock_procedure_service.approve_procedure.side_effect = SelfApprovalForbiddenError("alice")

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/approve",
            json={"decision": "approved", "approved_by": "alice"},
            headers={"X-User-Id": "alice"},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"

    async def test_422_on_no_draft_version(
        self, client, mock_procedure_service, sample_procedure_id
    ):
        mock_procedure_service.approve_procedure.side_effect = ProcedureNotApprovableError(
            "no_draft_version"
        )

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/approve",
            json={"decision": "approved", "approved_by": "bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "PROCEDURE_NOT_APPROVABLE"

    async def test_422_on_missing_decision_field(self, client, sample_procedure_id):
        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/approve",
            json={"approved_by": "bob"},  # missing decision
        )
        assert response.status_code == 422

    async def test_rejection_returns_200(
        self, client, mock_procedure_service, sample_procedure_id
    ):
        rejection = ApprovalRead(
            id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            approved_by="bob",
            decision=ApprovalDecision.REJECTED,
            notes="Needs more detail on step 2.",
            decided_at=_now(),
            is_superseded=False,
        )
        mock_procedure_service.approve_procedure.return_value = rejection

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/approve",
            json={
                "decision": "rejected",
                "approved_by": "bob",
                "notes": "Needs more detail on step 2.",
            },
        )

        assert response.status_code == 200
        assert response.json()["decision"] == "rejected"


# ── POST /api/v1/procedures/{id}/publish ─────────────────────────────────────

class TestPublishProcedure:
    async def test_200_on_successful_publish(
        self, client, mock_procedure_service, sample_procedure_id, sample_version_id
    ):
        mock_procedure_service.publish_procedure.return_value = ProcedurePublishResponse(
            procedure_id=sample_procedure_id,
            published_version_id=sample_version_id,
            deprecated_version_id=None,
            published_at=_now(),
        )

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/publish",
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["published_version_id"] == str(sample_version_id)
        assert data["deprecated_version_id"] is None

    async def test_200_with_deprecated_version_when_republishing(
        self, client, mock_procedure_service, sample_procedure_id, sample_version_id
    ):
        old_version_id = uuid.uuid4()
        mock_procedure_service.publish_procedure.return_value = ProcedurePublishResponse(
            procedure_id=sample_procedure_id,
            published_version_id=sample_version_id,
            deprecated_version_id=old_version_id,
            published_at=_now(),
        )

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/publish",
            headers={"X-User-Id": "bob"},
        )

        assert response.status_code == 200
        assert response.json()["deprecated_version_id"] == str(old_version_id)

    async def test_422_when_no_approved_version(
        self, client, mock_procedure_service, sample_procedure_id
    ):
        mock_procedure_service.publish_procedure.side_effect = ProcedureNotPublishableError(
            "no_approved_version"
        )

        response = await client.post(
            f"/api/v1/procedures/{sample_procedure_id}/publish",
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "PROCEDURE_NOT_PUBLISHABLE"

    async def test_404_when_procedure_not_found(self, client, mock_procedure_service):
        unknown = uuid.uuid4()
        mock_procedure_service.publish_procedure.side_effect = NotFoundError("Procedure", unknown)

        response = await client.post(f"/api/v1/procedures/{unknown}/publish")

        assert response.status_code == 404


# ── GET /api/v1/procedures/{procedure_id}/active ─────────────────────────────

class TestGetActiveVersion:
    async def test_200_returns_active_version(
        self, client, mock_procedure_service, sample_procedure_id,
        sample_machine_id, sample_version_id
    ):
        version_read = ProcedureVersionRead(
            id=sample_version_id,
            procedure_id=sample_procedure_id,
            version_number="1.0.0",
            status=ProcedureStatus.PUBLISHED,
            generation_source=GenerationSource.MANUAL,
            llm_model_used=None,
            schema_version="1.0",
            workflow_definition=_VALID_WORKFLOW,
            validation_errors=None,
            created_by="alice",
            submitted_for_review_at=_now(),
            created_at=_now(),
            updated_at=_now(),
            latest_approval=None,
        )
        procedure_with_active = ProcedureRead(
            id=sample_procedure_id,
            machine_id=sample_machine_id,
            title="Hydraulic Press LOTO",
            created_by="alice",
            active_version_id=sample_version_id,
            created_at=_now(),
            updated_at=_now(),
            versions=[_version_summary(sample_version_id, ProcedureStatus.PUBLISHED)],
            active_version=version_read,
        )
        mock_procedure_service.get_procedure.return_value = procedure_with_active

        response = await client.get(f"/api/v1/procedures/{sample_procedure_id}/active")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["version_number"] == "1.0.0"

    async def test_422_when_no_active_version(
        self, client, mock_procedure_service, sample_procedure_id, sample_machine_id
    ):
        from app.core.exceptions import NoActiveVersionError
        procedure_no_active = ProcedureRead(
            id=sample_procedure_id,
            machine_id=sample_machine_id,
            title="Unpublished Procedure",
            created_by="alice",
            active_version_id=None,  # no published version yet
            created_at=_now(),
            updated_at=_now(),
            versions=[_version_summary()],
            active_version=None,
        )
        mock_procedure_service.get_procedure.return_value = procedure_no_active

        response = await client.get(f"/api/v1/procedures/{sample_procedure_id}/active")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_ACTIVE_VERSION"
