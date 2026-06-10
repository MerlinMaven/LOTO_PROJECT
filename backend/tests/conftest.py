"""
Shared pytest fixtures.

Integration tests use httpx.AsyncClient against the real FastAPI app
with service-layer dependencies overridden by AsyncMock factories.
This tests the full HTTP → schema validation → error mapping stack
without requiring a live database.

Unit tests (tests/unit/) do not use these fixtures — they instantiate
services directly with mocked repositories.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_audit_service,
    get_intervention_service,
    get_machine_service,
    get_procedure_service,
)
from app.domain.enums import (
    EnergyType,
    GenerationSource,
    ProcedureStatus,
    RiskLevel,
)
from app.main import create_app
from app.schemas.common import PaginatedResponse
from app.schemas.machine import ComponentRead, MachineRead
from app.schemas.procedure import (
    ApprovalRead,
    ProcedurePublishResponse,
    ProcedureRead,
    ProcedureVersionRead,
    ProcedureVersionSummary,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ── Canonical fixtures for read responses ─────────────────────────────────────

@pytest.fixture
def sample_machine_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sample_machine_read(sample_machine_id) -> MachineRead:
    return MachineRead(
        id=sample_machine_id,
        internal_code="MCH-001",
        name="Hydraulic Press Alpha",
        manufacturer="ACME",
        model_reference="HP-500",
        serial_number="SN-001",
        energy_types=[EnergyType.HYDRAULIC, EnergyType.ELECTRICAL],
        risk_level=RiskLevel.HIGH,
        location_in_site="Zone B, Row 3",
        site_id=None,
        is_active=True,
        components=[],
        active_procedure_version_id=None,
    )


@pytest.fixture
def sample_procedure_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def sample_version_id() -> uuid.UUID:
    return uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def sample_procedure_read(
    sample_procedure_id, sample_machine_id, sample_version_id
) -> ProcedureRead:
    version_summary = ProcedureVersionSummary(
        id=sample_version_id,
        version_number="1.0.0",
        status=ProcedureStatus.DRAFT_PENDING_REVIEW,
        created_by="alice",
        created_at=_now(),
    )
    return ProcedureRead(
        id=sample_procedure_id,
        machine_id=sample_machine_id,
        title="Hydraulic Press LOTO Procedure",
        created_by="alice",
        active_version_id=None,
        created_at=_now(),
        updated_at=_now(),
        versions=[version_summary],
        active_version=None,
    )


# ── Mock service factories ────────────────────────────────────────────────────

@pytest.fixture
def mock_machine_service():
    svc = MagicMock()
    svc.create_machine = AsyncMock()
    svc.get_machine = AsyncMock()
    svc.list_machines = AsyncMock()
    svc.add_component = AsyncMock()
    return svc


@pytest.fixture
def mock_procedure_service():
    svc = MagicMock()
    svc.create_draft = AsyncMock()
    svc.get_procedure = AsyncMock()
    svc.approve_procedure = AsyncMock()
    svc.publish_procedure = AsyncMock()
    svc.get_active_version_for_machine = AsyncMock()
    svc.list_procedures = AsyncMock()
    svc.update_draft = AsyncMock()
    return svc


@pytest.fixture
def mock_intervention_service():
    svc = MagicMock()
    svc.start_intervention = AsyncMock()
    svc.get_intervention = AsyncMock()
    svc.complete_intervention = AsyncMock()
    svc.abort_intervention = AsyncMock()
    svc.pause_intervention = AsyncMock()
    svc.resume_intervention = AsyncMock()
    svc.enter_step = AsyncMock()
    svc.validate_step = AsyncMock()
    svc.reject_step = AsyncMock()
    svc.override_step = AsyncMock()
    svc.get_progress = AsyncMock()
    svc.get_current_step = AsyncMock()
    svc.get_audit_trail = AsyncMock()
    return svc


@pytest.fixture
def mock_audit_service():
    svc = MagicMock()
    svc.record_event = AsyncMock()
    svc.query_events = AsyncMock()
    return svc


# ── Test application with overridden dependencies ─────────────────────────────

@pytest_asyncio.fixture
async def client(
    mock_machine_service,
    mock_procedure_service,
    mock_intervention_service,
    mock_audit_service,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client connected to the FastAPI app.

    All service dependencies are replaced with mocks — no DB, no network.
    Tests control behaviour by configuring the mock return values directly.
    """
    app = create_app()

    app.dependency_overrides[get_machine_service] = lambda: mock_machine_service
    app.dependency_overrides[get_procedure_service] = lambda: mock_procedure_service
    app.dependency_overrides[get_intervention_service] = lambda: mock_intervention_service
    app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
