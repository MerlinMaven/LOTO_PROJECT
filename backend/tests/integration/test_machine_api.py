"""
Integration tests for /api/v1/machines endpoints.

Tests exercise the full HTTP stack:
  request body validation → router → service (mocked) → response schema
  error cases:  domain exception → error handler → HTTP status + body

No database connection required.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.common import PaginatedResponse
from app.schemas.machine import MachineRead


# ── POST /api/v1/machines ─────────────────────────────────────────────────────

class TestRegisterMachine:
    async def test_201_on_valid_payload(
        self, client, mock_machine_service, sample_machine_read
    ):
        mock_machine_service.create_machine.return_value = sample_machine_read

        response = await client.post(
            "/api/v1/machines",
            json={
                "internal_code": "MCH-001",
                "name": "Hydraulic Press Alpha",
                "energy_types": ["hydraulic", "electrical"],
                "risk_level": "high",
                "manufacturer": "ACME",
            },
            headers={"X-User-Id": "alice", "X-User-Role": "hse_engineer"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["internal_code"] == "MCH-001"
        assert data["name"] == "Hydraulic Press Alpha"
        mock_machine_service.create_machine.assert_awaited_once()

    async def test_422_on_missing_required_fields(self, client):
        response = await client.post("/api/v1/machines", json={})
        assert response.status_code == 422

    async def test_422_on_invalid_energy_type(self, client):
        response = await client.post(
            "/api/v1/machines",
            json={
                "internal_code": "MCH-001",
                "name": "Test Machine",
                "energy_types": ["nuclear"],  # invalid
            },
        )
        assert response.status_code == 422

    async def test_409_when_machine_code_already_exists(self, client, mock_machine_service):
        mock_machine_service.create_machine.side_effect = ConflictError(
            "Machine with internal_code 'MCH-001' already exists."
        )

        response = await client.post(
            "/api/v1/machines",
            json={"internal_code": "MCH-001", "name": "Duplicate Machine"},
        )

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "CONFLICT"

    async def test_user_id_header_passed_to_service(
        self, client, mock_machine_service, sample_machine_read
    ):
        mock_machine_service.create_machine.return_value = sample_machine_read

        await client.post(
            "/api/v1/machines",
            json={"internal_code": "MCH-001", "name": "Test"},
            headers={"X-User-Id": "operator-123"},
        )

        call_kwargs = mock_machine_service.create_machine.call_args
        assert call_kwargs.kwargs.get("actor_id") == "operator-123"


# ── GET /api/v1/machines/{id} ─────────────────────────────────────────────────

class TestGetMachine:
    async def test_200_returns_machine(
        self, client, mock_machine_service, sample_machine_read, sample_machine_id
    ):
        mock_machine_service.get_machine.return_value = sample_machine_read

        response = await client.get(f"/api/v1/machines/{sample_machine_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_machine_id)
        assert data["internal_code"] == "MCH-001"
        mock_machine_service.get_machine.assert_awaited_once_with(sample_machine_id)

    async def test_404_when_machine_not_found(self, client, mock_machine_service):
        unknown_id = uuid.uuid4()
        mock_machine_service.get_machine.side_effect = NotFoundError("Machine", unknown_id)

        response = await client.get(f"/api/v1/machines/{unknown_id}")

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert "Machine" in body["error"]["message"]

    async def test_422_on_invalid_uuid(self, client):
        response = await client.get("/api/v1/machines/not-a-uuid")
        assert response.status_code == 422


# ── GET /api/v1/machines ──────────────────────────────────────────────────────

class TestListMachines:
    async def test_200_returns_paginated_list(
        self, client, mock_machine_service, sample_machine_read
    ):
        mock_machine_service.list_machines.return_value = PaginatedResponse(
            data=[sample_machine_read],
            total=1,
            page=1,
            page_size=20,
        )

        response = await client.get("/api/v1/machines")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["data"]) == 1
        assert data["page"] == 1

    async def test_422_on_invalid_page_params(self, client):
        response = await client.get("/api/v1/machines?page=0")
        assert response.status_code == 422

    async def test_default_pagination_passed_to_service(
        self, client, mock_machine_service, sample_machine_read
    ):
        mock_machine_service.list_machines.return_value = PaginatedResponse(
            data=[], total=0, page=1, page_size=20
        )

        await client.get("/api/v1/machines")

        mock_machine_service.list_machines.assert_awaited_once_with(
            page=1, page_size=20, site_id=None
        )


# ── POST /api/v1/machines/{id}/components ────────────────────────────────────

class TestAddComponent:
    async def test_201_adds_component(
        self, client, mock_machine_service, sample_machine_id
    ):
        from app.schemas.machine import ComponentRead
        from app.domain.enums import EnergyType

        comp = ComponentRead(
            id=uuid.uuid4(),
            machine_id=sample_machine_id,
            label="Main Circuit Breaker",
            energy_type=EnergyType.ELECTRICAL,
            physical_description="Panel B, Row 1",
            location_hint="North wall",
            default_vision_prompt=None,
            ar_anchor_id=None,
            is_active=True,
        )
        mock_machine_service.add_component.return_value = comp

        response = await client.post(
            f"/api/v1/machines/{sample_machine_id}/components",
            json={"label": "Main Circuit Breaker", "energy_type": "electrical"},
            headers={"X-User-Id": "alice"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "Main Circuit Breaker"
        assert data["energy_type"] == "electrical"

    async def test_404_when_machine_not_found(self, client, mock_machine_service):
        unknown_id = uuid.uuid4()
        mock_machine_service.add_component.side_effect = NotFoundError("Machine", unknown_id)

        response = await client.post(
            f"/api/v1/machines/{unknown_id}/components",
            json={"label": "Breaker", "energy_type": "electrical"},
        )

        assert response.status_code == 404
