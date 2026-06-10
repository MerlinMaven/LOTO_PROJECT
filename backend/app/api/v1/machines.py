"""
Machine endpoints.

POST   /api/v1/machines                 Register a new machine
GET    /api/v1/machines                 List active machines (paginated)
GET    /api/v1/machines/{id}            Get machine detail with components
POST   /api/v1/machines/{id}/components Add a component to an existing machine
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.deps import CurrentUserDep, MachineSvcDep
from app.schemas.common import PaginatedResponse
from app.schemas.machine import ComponentCreate, ComponentRead, MachineCreate, MachineRead

router = APIRouter()


@router.post("", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
async def register_machine(
    body: MachineCreate,
    request: Request,
    svc: MachineSvcDep,
    user: CurrentUserDep,
) -> MachineRead:
    """
    Register a new machine in the system.

    Optionally include `components` in the request body to create
    energy isolation point records in a single operation.
    """
    machine = await svc.create_machine(
        body, actor_id=user.identifier, ip_address=request.client.host if request.client else None
    )
    return MachineRead.model_validate(machine)


@router.get("", response_model=PaginatedResponse[MachineRead])
async def list_machines(
    svc: MachineSvcDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    site_id: UUID | None = Query(None),
) -> PaginatedResponse[MachineRead]:
    """List all active machines. Filter by site_id if provided."""
    return await svc.list_machines(page=page, page_size=page_size, site_id=site_id)


@router.get("/{machine_id}", response_model=MachineRead)
async def get_machine(machine_id: UUID, svc: MachineSvcDep) -> MachineRead:
    """Get full machine details including components and active procedure reference."""
    machine = await svc.get_machine(machine_id)
    return MachineRead.model_validate(machine)


@router.post(
    "/{machine_id}/components",
    response_model=ComponentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_component(
    machine_id: UUID,
    body: ComponentCreate,
    svc: MachineSvcDep,
    user: CurrentUserDep,
) -> ComponentRead:
    """Add an energy isolation component to an existing machine."""
    component = await svc.add_component(machine_id, body, actor_id=user.identifier)
    return ComponentRead.model_validate(component)
