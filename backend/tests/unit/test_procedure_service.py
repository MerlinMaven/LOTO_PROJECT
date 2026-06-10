"""
Unit tests for ProcedureService.

All repository and audit calls are mocked with AsyncMock.
No database or network is needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    MachineAlreadyHasProcedureError,
    NotFoundError,
    ProcedureNotApprovableError,
    ProcedureNotPublishableError,
    SelfApprovalForbiddenError,
)
from app.domain.enums import ApprovalDecision, GenerationSource, ProcedureStatus
from app.schemas.procedure import ApprovalCreate, ProcedureCreate
from app.services.procedure_service import ProcedureService


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_service() -> tuple[ProcedureService, MagicMock, MagicMock]:
    """Return (service, mock_repo, mock_audit) for injection."""
    mock_repo = MagicMock()
    mock_audit = MagicMock()
    mock_audit.record_event = AsyncMock()
    svc = ProcedureService(procedure_repo=mock_repo, audit_service=mock_audit)
    return svc, mock_repo, mock_audit


def _machine_id() -> uuid.UUID:
    return uuid.uuid4()


def _version_id() -> uuid.UUID:
    return uuid.uuid4()


def _procedure_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_procedure(proc_id=None, machine_id=None, version_id=None):
    """Create a minimal MagicMock that looks like a Procedure ORM object."""
    p = MagicMock()
    p.id = proc_id or _procedure_id()
    p.machine_id = machine_id or _machine_id()
    p.active_version_id = version_id
    return p


def _make_version(
    version_id=None,
    procedure_id=None,
    status=ProcedureStatus.DRAFT_PENDING_REVIEW,
    created_by="alice",
    version_number="1.0.0",
):
    v = MagicMock()
    v.id = version_id or _version_id()
    v.procedure_id = procedure_id or _procedure_id()
    v.status = status
    v.created_by = created_by
    v.version_number = version_number
    v.submitted_for_review_at = None
    return v


VALID_WORKFLOW = {
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
                    "title": "Electrical",
                    "steps": [
                        {
                            "step_id": "stp_1",
                            "sequence": 1,
                            "instruction": "Open the breaker.",
                            "validation": {"method": "manual_confirmation"},
                        }
                    ],
                }
            ],
        }
    ]
}


# ── create_draft ──────────────────────────────────────────────────────────────

class TestCreateDraft:
    async def test_raises_if_machine_already_has_procedure(self):
        svc, repo, _ = make_service()
        machine_id = _machine_id()

        # Machine already has a procedure
        repo.get_by_machine_id = AsyncMock(return_value=_make_procedure(machine_id=machine_id))

        data = ProcedureCreate(
            machine_id=machine_id,
            title="Test Procedure",
            created_by="alice",
            workflow_definition=VALID_WORKFLOW,
        )

        with pytest.raises(MachineAlreadyHasProcedureError) as exc_info:
            await svc.create_draft(data, actor_id="alice")

        assert str(machine_id) in str(exc_info.value)

    async def test_creates_procedure_and_version_when_no_existing(self):
        svc, repo, audit = make_service()
        machine_id = _machine_id()
        proc = _make_procedure(machine_id=machine_id)
        version = _make_version(procedure_id=proc.id)

        repo.get_by_machine_id = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=proc)
        repo.create_version = AsyncMock(return_value=version)
        repo.get_with_versions = AsyncMock(return_value=proc)

        # ProcedureRead.model_validate needs real attributes; patch it
        with patch("app.services.procedure_service.ProcedureRead") as MockRead:
            MockRead.model_validate.return_value = MagicMock()
            data = ProcedureCreate(
                machine_id=machine_id,
                title="My Procedure",
                created_by="alice",
                workflow_definition=VALID_WORKFLOW,
                generation_source=GenerationSource.MANUAL,
            )
            result = await svc.create_draft(data, actor_id="alice")

        repo.create.assert_awaited_once()
        repo.create_version.assert_awaited_once()
        audit.record_event.assert_awaited_once()

    async def test_audit_event_recorded_on_success(self):
        svc, repo, audit = make_service()
        machine_id = _machine_id()
        proc = _make_procedure(machine_id=machine_id)
        version = _make_version(procedure_id=proc.id)

        repo.get_by_machine_id = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=proc)
        repo.create_version = AsyncMock(return_value=version)
        repo.get_with_versions = AsyncMock(return_value=proc)

        with patch("app.services.procedure_service.ProcedureRead") as MockRead:
            MockRead.model_validate.return_value = MagicMock()
            data = ProcedureCreate(
                machine_id=machine_id,
                title="My Procedure",
                created_by="alice",
                workflow_definition=VALID_WORKFLOW,
            )
            await svc.create_draft(data, actor_id="alice")

        call_args = audit.record_event.call_args
        event_type = call_args.args[0]
        assert "draft" in str(event_type)


# ── approve_procedure ─────────────────────────────────────────────────────────

class TestApproveProcedure:
    async def test_raises_not_found_when_procedure_missing(self):
        svc, repo, _ = make_service()
        repo.get_with_versions = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError) as exc_info:
            await svc.approve_procedure(
                _procedure_id(),
                ApprovalCreate(
                    decision=ApprovalDecision.APPROVED,
                    approved_by="bob",
                ),
            )
        assert "Procedure" in str(exc_info.value)

    async def test_raises_not_approvable_when_no_draft_version(self):
        svc, repo, _ = make_service()
        proc = _make_procedure()
        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_current_draft_version = AsyncMock(return_value=None)

        with pytest.raises(ProcedureNotApprovableError):
            await svc.approve_procedure(
                proc.id,
                ApprovalCreate(decision=ApprovalDecision.APPROVED, approved_by="bob"),
            )

    async def test_raises_self_approval_forbidden(self):
        """4-eyes rule: the author cannot approve their own procedure."""
        svc, repo, _ = make_service()
        proc = _make_procedure()
        version = _make_version(procedure_id=proc.id, created_by="alice")

        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_current_draft_version = AsyncMock(return_value=version)

        with pytest.raises(SelfApprovalForbiddenError) as exc_info:
            await svc.approve_procedure(
                proc.id,
                ApprovalCreate(decision=ApprovalDecision.APPROVED, approved_by="alice"),
            )

        assert exc_info.value.details.get("user_identifier") == "alice"

    async def test_4_eyes_rule_different_user_passes(self):
        """A different user CAN approve."""
        svc, repo, audit = make_service()
        proc = _make_procedure()
        version = _make_version(procedure_id=proc.id, created_by="alice")

        approval_obj = MagicMock()
        approval_obj.id = uuid.uuid4()
        approval_obj.version_id = version.id
        approval_obj.approved_by = "bob"
        approval_obj.decision = ApprovalDecision.APPROVED
        approval_obj.notes = None
        approval_obj.decided_at = datetime.now(timezone.utc)
        approval_obj.is_superseded = False

        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_current_draft_version = AsyncMock(return_value=version)
        repo.create_approval = AsyncMock(return_value=approval_obj)

        with patch("app.services.procedure_service.ApprovalRead") as MockApprovalRead:
            MockApprovalRead.model_validate.return_value = MagicMock()
            await svc.approve_procedure(
                proc.id,
                ApprovalCreate(decision=ApprovalDecision.APPROVED, approved_by="bob"),
            )

        # Version status was mutated to APPROVED
        assert version.status == ProcedureStatus.APPROVED
        audit.record_event.assert_awaited_once()

    async def test_rejection_does_not_advance_status(self):
        """Rejected procedure stays in draft_pending_review."""
        svc, repo, audit = make_service()
        proc = _make_procedure()
        version = _make_version(procedure_id=proc.id, created_by="alice")

        approval_obj = MagicMock()
        approval_obj.id = uuid.uuid4()
        approval_obj.version_id = version.id
        approval_obj.approved_by = "bob"
        approval_obj.decision = ApprovalDecision.REJECTED
        approval_obj.notes = "Needs revision."
        approval_obj.decided_at = datetime.now(timezone.utc)
        approval_obj.is_superseded = False

        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_current_draft_version = AsyncMock(return_value=version)
        repo.create_approval = AsyncMock(return_value=approval_obj)

        with patch("app.services.procedure_service.ApprovalRead") as MockApprovalRead:
            MockApprovalRead.model_validate.return_value = MagicMock()
            await svc.approve_procedure(
                proc.id,
                ApprovalCreate(
                    decision=ApprovalDecision.REJECTED,
                    approved_by="bob",
                    notes="Needs revision.",
                ),
            )

        assert version.status == ProcedureStatus.DRAFT_PENDING_REVIEW


# ── publish_procedure ─────────────────────────────────────────────────────────

class TestPublishProcedure:
    async def test_raises_not_found_when_procedure_missing(self):
        svc, repo, _ = make_service()
        repo.get_with_versions = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.publish_procedure(_procedure_id(), actor_id="bob")

    async def test_raises_not_publishable_when_no_approved_version(self):
        svc, repo, _ = make_service()
        proc = _make_procedure()
        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_approved_version = AsyncMock(return_value=None)

        with pytest.raises(ProcedureNotPublishableError):
            await svc.publish_procedure(proc.id, actor_id="bob")

    async def test_publishes_approved_version_and_sets_active(self):
        svc, repo, audit = make_service()
        proc = _make_procedure()
        version = _make_version(
            procedure_id=proc.id, status=ProcedureStatus.APPROVED
        )

        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_approved_version = AsyncMock(return_value=version)
        repo.get_published_version = AsyncMock(return_value=None)

        result = await svc.publish_procedure(proc.id, actor_id="bob")

        assert version.status == ProcedureStatus.PUBLISHED
        assert proc.active_version_id == version.id
        assert result.published_version_id == version.id
        assert result.deprecated_version_id is None
        audit.record_event.assert_awaited()

    async def test_archives_previously_published_version(self):
        """
        When a new version is published, the old published version must be
        automatically archived. Ongoing interventions referencing the old
        version_id are unaffected (FK to version, not to active_version_id).
        """
        svc, repo, audit = make_service()
        proc = _make_procedure()
        old_version = _make_version(
            version_id=uuid.uuid4(),
            procedure_id=proc.id,
            status=ProcedureStatus.PUBLISHED,
        )
        new_version = _make_version(
            version_id=uuid.uuid4(),
            procedure_id=proc.id,
            status=ProcedureStatus.APPROVED,
        )

        repo.get_with_versions = AsyncMock(return_value=proc)
        repo.get_approved_version = AsyncMock(return_value=new_version)
        repo.get_published_version = AsyncMock(return_value=old_version)

        result = await svc.publish_procedure(proc.id, actor_id="bob")

        # Old version must be archived
        assert old_version.status == ProcedureStatus.ARCHIVED
        # New version is now published
        assert new_version.status == ProcedureStatus.PUBLISHED
        # Response includes the deprecated version id
        assert result.deprecated_version_id == old_version.id
        # Two audit events: one for ARCHIVED, one for PUBLISHED
        assert audit.record_event.await_count == 2
