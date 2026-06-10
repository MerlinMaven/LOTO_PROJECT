"""
Integration tests for the Phase 4 HSE-dashboard procedure endpoints:

  GET   /api/v1/procedures          list + filter + search
  PATCH /api/v1/procedures/{id}/draft   edit the current draft version

Exercises HTTP → schema validation → router → mocked service → error mapping.
No DB, no network — the service layer is mocked via conftest fixtures.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ApprovedProcedureImmutableError, NotFoundError
from app.domain.enums import GenerationSource, ProcedureStatus
from app.schemas.common import PaginatedResponse
from app.schemas.procedure import ProcedureListItem, ProcedureVersionRead

pytestmark = pytest.mark.asyncio


_WORKFLOW = {
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
                    "title": "Isolation",
                    "steps": [
                        {
                            "step_id": "stp_1",
                            "sequence": 1,
                            "instruction": "Open the main breaker.",
                            "validation": {"method": "manual_confirmation"},
                        }
                    ],
                }
            ],
        }
    ],
    "_generation_metadata": {"overall_confidence": 0.91},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _list_item(status=ProcedureStatus.DRAFT_PENDING_REVIEW, confidence=0.91):
    return ProcedureListItem(
        id=uuid.uuid4(),
        machine_id=uuid.uuid4(),
        title="Hydraulic Press LOTO",
        created_by="generator",
        current_status=status,
        current_version_id=uuid.uuid4(),
        current_version_number="1.0.0",
        generation_source=GenerationSource.LLM_TEXT,
        overall_confidence=confidence,
        open_validation_errors=0,
        has_published_version=False,
        created_at=_now(),
        updated_at=_now(),
    )


def _version_read(
    procedure_id, version_id, status=ProcedureStatus.DRAFT_PENDING_REVIEW
):
    return ProcedureVersionRead(
        id=version_id,
        procedure_id=procedure_id,
        version_number="1.0.0",
        status=status,
        generation_source=GenerationSource.LLM_TEXT,
        llm_model_used="stub-model-v1",
        schema_version="1.0",
        workflow_definition=_WORKFLOW,
        validation_errors=None,
        created_by="generator",
        submitted_for_review_at=None,
        created_at=_now(),
        updated_at=_now(),
        latest_approval=None,
    )


# ── GET /api/v1/procedures ────────────────────────────────────────────────────

class TestListProcedures:
    async def test_200_returns_paginated_list(self, client, mock_procedure_service):
        mock_procedure_service.list_procedures.return_value = PaginatedResponse[
            ProcedureListItem
        ](data=[_list_item(), _list_item()], total=2, page=1, page_size=20)

        response = await client.get("/api/v1/procedures")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2
        assert body["data"][0]["current_status"] == "draft_pending_review"

    async def test_status_filter_passed_to_service(self, client, mock_procedure_service):
        mock_procedure_service.list_procedures.return_value = PaginatedResponse[
            ProcedureListItem
        ](data=[_list_item(status=ProcedureStatus.PUBLISHED)], total=1, page=1, page_size=20)

        response = await client.get("/api/v1/procedures?status=published")

        assert response.status_code == 200
        kwargs = mock_procedure_service.list_procedures.call_args.kwargs
        assert kwargs["status"] == ProcedureStatus.PUBLISHED

    async def test_search_and_pagination_passed_to_service(
        self, client, mock_procedure_service
    ):
        mock_procedure_service.list_procedures.return_value = PaginatedResponse[
            ProcedureListItem
        ](data=[], total=0, page=2, page_size=5)

        response = await client.get("/api/v1/procedures?search=press&page=2&page_size=5")

        assert response.status_code == 200
        kwargs = mock_procedure_service.list_procedures.call_args.kwargs
        assert kwargs["search"] == "press"
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 5

    async def test_422_on_invalid_status(self, client, mock_procedure_service):
        response = await client.get("/api/v1/procedures?status=not_a_status")
        assert response.status_code == 422

    async def test_confidence_surfaced_in_row(self, client, mock_procedure_service):
        mock_procedure_service.list_procedures.return_value = PaginatedResponse[
            ProcedureListItem
        ](data=[_list_item(confidence=0.42)], total=1, page=1, page_size=20)

        response = await client.get("/api/v1/procedures")
        assert response.json()["data"][0]["overall_confidence"] == 0.42


# ── PATCH /api/v1/procedures/{id}/draft ───────────────────────────────────────

class TestUpdateDraft:
    async def test_200_on_valid_edit(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        version_id = uuid.uuid4()
        mock_procedure_service.update_draft.return_value = _version_read(
            procedure_id, version_id
        )

        response = await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={"workflow_definition": _WORKFLOW, "edited_by": "hse_bob"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(version_id)

    async def test_edit_summary_forwarded(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        mock_procedure_service.update_draft.return_value = _version_read(
            procedure_id, uuid.uuid4()
        )

        await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={
                "workflow_definition": _WORKFLOW,
                "edited_by": "hse_bob",
                "edit_summary": "Renamed main_switch component",
            },
        )

        body = mock_procedure_service.update_draft.call_args.args[1]
        assert body.edit_summary == "Renamed main_switch component"

    async def test_422_on_empty_workflow(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={"workflow_definition": {}, "edited_by": "hse_bob"},
        )
        assert response.status_code == 422

    async def test_422_on_missing_editor(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={"workflow_definition": _WORKFLOW},
        )
        assert response.status_code == 422

    async def test_404_when_no_draft_version(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        mock_procedure_service.update_draft.side_effect = NotFoundError(
            "Draft version for procedure", procedure_id
        )

        response = await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={"workflow_definition": _WORKFLOW, "edited_by": "hse_bob"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    async def test_422_when_draft_is_immutable(self, client, mock_procedure_service):
        procedure_id = uuid.uuid4()
        version_id = uuid.uuid4()
        mock_procedure_service.update_draft.side_effect = (
            ApprovedProcedureImmutableError(version_id, "approved")
        )

        response = await client.patch(
            f"/api/v1/procedures/{procedure_id}/draft",
            json={"workflow_definition": _WORKFLOW, "edited_by": "hse_bob"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "APPROVED_PROCEDURE_IMMUTABLE"
