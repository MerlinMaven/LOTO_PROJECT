"""
MachineService — business logic for machine and component management.
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.enums import AuditEventType
from app.models.machine import Machine, MachineComponent
from app.repositories.machine_repository import MachineRepository
from app.schemas.machine import ComponentCreate, MachineCreate, MachineRead
from app.schemas.common import PaginatedResponse
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class MachineService:
    def __init__(
        self,
        machine_repo: MachineRepository,
        audit_service: AuditService,
    ) -> None:
        self.repo = machine_repo
        self.audit = audit_service

    async def create_machine(
        self,
        data: MachineCreate,
        *,
        actor_id: str = "system",
        ip_address: str | None = None,
    ) -> Machine:
        # Check for duplicate internal_code within the same site
        existing = await self.repo.get_by_internal_code(
            data.internal_code, site_id=data.site_id
        )
        if existing:
            raise ConflictError(
                f"Machine with internal_code '{data.internal_code}' already exists"
                + (f" in site '{data.site_id}'." if data.site_id else ".")
            )

        machine = Machine(
            internal_code=data.internal_code,
            name=data.name,
            manufacturer=data.manufacturer,
            model_reference=data.model_reference,
            serial_number=data.serial_number,
            energy_types=[e.value for e in data.energy_types],
            risk_level=data.risk_level,
            location_in_site=data.location_in_site,
            site_id=data.site_id,
        )
        machine = await self.repo.create(machine)

        # Create inline components if provided
        for comp_data in data.components:
            await self._add_component_to_machine(machine.id, comp_data)

        await self.audit.record_event(
            AuditEventType.MACHINE_REGISTERED,
            actor_id=actor_id,
            machine_id=machine.id,
            payload={"internal_code": machine.internal_code, "name": machine.name},
            ip_address=ip_address,
        )
        logger.info("machine_registered", machine_id=str(machine.id), code=machine.internal_code)
        return machine

    async def get_machine(self, machine_id: UUID) -> Machine:
        machine = await self.repo.get_with_components(machine_id)
        if not machine:
            raise NotFoundError("Machine", machine_id)
        return machine

    async def list_machines(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        site_id: UUID | None = None,
    ) -> PaginatedResponse[MachineRead]:
        machines, total = await self.repo.list_active(
            page=page, page_size=page_size, site_id=site_id
        )
        return PaginatedResponse(
            data=[self._to_read(m) for m in machines],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def add_component(
        self,
        machine_id: UUID,
        data: ComponentCreate,
        *,
        actor_id: str = "system",
    ) -> MachineComponent:
        machine = await self.repo.get(machine_id)
        if not machine:
            raise NotFoundError("Machine", machine_id)
        component = await self._add_component_to_machine(machine_id, data)
        await self.audit.record_event(
            AuditEventType.MACHINE_COMPONENT_ADDED,
            actor_id=actor_id,
            machine_id=machine_id,
            payload={"label": component.label, "energy_type": component.energy_type},
        )
        return component

    async def _add_component_to_machine(
        self, machine_id: UUID, data: ComponentCreate
    ) -> MachineComponent:
        component = MachineComponent(
            machine_id=machine_id,
            label=data.label,
            energy_type=data.energy_type,
            physical_description=data.physical_description,
            location_hint=data.location_hint,
            default_vision_prompt=data.default_vision_prompt,
            ar_anchor_id=data.ar_anchor_id,
        )
        return await self.repo.add_component(component)

    @staticmethod
    def _to_read(machine: Machine) -> MachineRead:
        from app.schemas.machine import ComponentRead
        components = [
            ComponentRead.model_validate(c) for c in (machine.components or [])
        ]
        active_version_id = None
        if machine.procedure and machine.procedure.active_version_id:
            active_version_id = machine.procedure.active_version_id
        return MachineRead(
            id=machine.id,
            internal_code=machine.internal_code,
            name=machine.name,
            manufacturer=machine.manufacturer,
            model_reference=machine.model_reference,
            serial_number=machine.serial_number,
            energy_types=machine.energy_types,
            risk_level=machine.risk_level,
            location_in_site=machine.location_in_site,
            site_id=machine.site_id,
            is_active=machine.is_active,
            components=components,
            active_procedure_version_id=active_version_id,
        )
