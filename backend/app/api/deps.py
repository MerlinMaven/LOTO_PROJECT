"""
FastAPI dependency injection.

All services and repositories are wired here.
Swapping an implementation (e.g., StubVisionService → YOLOWorldVisionService)
requires a change in exactly one place: this file.

Auth is NOT enforced in Phase 2.
get_current_user() returns a StubUser. In Phase 3:
1. Uncomment the JWT decode block
2. The rest of the codebase is untouched
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.audit_repository import AuditRepository
from app.repositories.intervention_repository import InterventionRepository
from app.repositories.machine_repository import MachineRepository
from app.repositories.procedure_repository import ProcedureRepository
from app.services.audit_service import AuditService
from app.services.intervention_service import InterventionService
from app.services.machine_service import MachineService
from app.services.procedure_service import ProcedureService
from app.services.ports.vision_service import StubVisionService, VisionService
from app.services.ports.llm_service import StubLLMService, LLMService


# ── Auth stub (Phase 2) ───────────────────────────────────────────────────────

@dataclass
class CurrentUser:
    identifier: str
    role: str


async def get_current_user(request: Request) -> CurrentUser:
    """
    Phase 2 stub: extracts X-User-Id and X-User-Role from request headers.
    In Phase 3: decode the Bearer JWT token and verify with the DB.

    Any code that needs the current user calls:
        user: Annotated[CurrentUser, Depends(get_current_user)]
    """
    user_id = request.headers.get("X-User-Id", "anonymous")
    user_role = request.headers.get("X-User-Role", "operator")
    return CurrentUser(identifier=user_id, role=user_role)


# ── Repository factories ──────────────────────────────────────────────────────

def get_machine_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> MachineRepository:
    return MachineRepository(db)


def get_procedure_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> ProcedureRepository:
    return ProcedureRepository(db)


def get_intervention_repo(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> InterventionRepository:
    return InterventionRepository(db)


def get_audit_repo(db: Annotated[AsyncSession, Depends(get_db)]) -> AuditRepository:
    return AuditRepository(db)


# ── AI service stubs (Phase 2) ────────────────────────────────────────────────
# Phase 3: replace with real implementations, loaded from config

def get_vision_service() -> VisionService:
    return StubVisionService()


def get_llm_service() -> LLMService:
    return StubLLMService()


# ── Service factories ─────────────────────────────────────────────────────────

def get_audit_service(
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AuditService:
    return AuditService(audit_repo)


def get_machine_service(
    machine_repo: Annotated[MachineRepository, Depends(get_machine_repo)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> MachineService:
    return MachineService(machine_repo, audit_service)


def get_procedure_service(
    procedure_repo: Annotated[ProcedureRepository, Depends(get_procedure_repo)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> ProcedureService:
    return ProcedureService(procedure_repo, audit_service)


def get_intervention_service(
    intervention_repo: Annotated[InterventionRepository, Depends(get_intervention_repo)],
    procedure_repo: Annotated[ProcedureRepository, Depends(get_procedure_repo)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    vision_service: Annotated[VisionService, Depends(get_vision_service)],
) -> InterventionService:
    return InterventionService(
        intervention_repo, procedure_repo, audit_service, vision_service
    )


# ── Convenience type aliases ──────────────────────────────────────────────────

DBDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
MachineSvcDep = Annotated[MachineService, Depends(get_machine_service)]
ProcedureSvcDep = Annotated[ProcedureService, Depends(get_procedure_service)]
InterventionSvcDep = Annotated[InterventionService, Depends(get_intervention_service)]
AuditSvcDep = Annotated[AuditService, Depends(get_audit_service)]
