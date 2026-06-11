"""
Procedure endpoints.

POST   /api/v1/procedures               Create a draft procedure
GET    /api/v1/procedures               List procedures (HSE dashboard home)
GET    /api/v1/procedures/{id}          Get procedure detail with versions
PATCH  /api/v1/procedures/{id}/draft    Edit the current draft version (HSE review)
POST   /api/v1/procedures/{id}/approve  Approve (or reject) the draft version
POST   /api/v1/procedures/{id}/publish  Publish the approved version
GET    /api/v1/procedures/{id}/active   Get published version (used by Quest)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.deps import CurrentUserDep, ProcedureSvcDep
from app.domain.enums import ProcedureStatus
from app.schemas.common import PaginatedResponse
from app.schemas.procedure import (
    ApprovalCreate,
    ApprovalRead,
    DraftUpdate,
    ProcedureCreate,
    ProcedureListItem,
    ProcedurePublishResponse,
    ProcedureRead,
    ProcedureVersionRead,
)

router = APIRouter()


@router.post("", response_model=ProcedureRead, status_code=status.HTTP_201_CREATED)
async def create_procedure(
    body: ProcedureCreate,
    request: Request,
    svc: ProcedureSvcDep,
    user: CurrentUserDep,
) -> ProcedureRead:
    """
    Create a LOTO procedure draft for a machine.

    Creates both the Procedure envelope and the first ProcedureVersion (v1.0.0)
    in a single atomic operation. The workflow_definition is validated against
    the canonical schema; errors are stored but do not block creation.
    """
    return await svc.create_draft(
        body,
        actor_id=user.identifier,
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=PaginatedResponse[ProcedureListItem])
async def list_procedures(
    svc: ProcedureSvcDep,
    status_filter: ProcedureStatus | None = Query(
        None,
        alias="status",
        description="Filter by the procedure's current (latest version) status.",
    ),
    search: str | None = Query(None, description="Case-insensitive title search."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProcedureListItem]:
    """
    List procedures for the HSE dashboard home.

    Powers the Draft / Approved / Published / Archived tabs plus search.
    Each row carries the derived current status, generation confidence, and
    open validation error count so the dashboard can render without N+1 fetches.
    """
    return await svc.list_procedures(
        status=status_filter,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/{procedure_id}", response_model=ProcedureRead)
async def get_procedure(procedure_id: UUID, svc: ProcedureSvcDep) -> ProcedureRead:
    """Get a procedure with all its versions and the active (published) version detail."""
    return await svc.get_procedure(procedure_id)


@router.delete(
    "/{procedure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive (soft-delete) a procedure",
)
async def archive_procedure(
    procedure_id: UUID,
    request: Request,
    svc: ProcedureSvcDep,
    user: CurrentUserDep,
) -> None:
    """
    Soft-deletes a procedure by archiving all its versions.
    The procedure envelope is retained for OSHA 1910.147 audit compliance.
    Published procedures become archived; drafts/approved versions are discarded.
    """
    await svc.archive_procedure(
        procedure_id,
        actor_id=user.identifier,
        ip_address=request.client.host if request.client else None,
    )


@router.patch(
    "/{procedure_id}/draft",
    response_model=ProcedureVersionRead,
    summary="Edit the current draft version (HSE review edits)",
)
async def update_draft(
    procedure_id: UUID,
    body: DraftUpdate,
    request: Request,
    svc: ProcedureSvcDep,
) -> ProcedureVersionRead:
    """
    Replace the workflow_definition of the procedure's current draft version.

    This is the single write path behind every edit surface in the review
    screens — component edits, workflow step edits, and vision prompt edits all
    mutate the one workflow_definition document. The edit is re-validated against
    the canonical schema; errors are stored but do not block the save.

    Only `draft_pending_review` versions can be edited.
    """
    return await svc.update_draft(
        procedure_id,
        body,
        ip_address=request.client.host if request.client else None,
    )


@router.post(
    "/{procedure_id}/approve",
    response_model=ApprovalRead,
    summary="Approve or reject the current draft version",
)
async def approve_procedure(
    procedure_id: UUID,
    body: ApprovalCreate,
    request: Request,
    svc: ProcedureSvcDep,
) -> ApprovalRead:
    """
    Approve or reject the current draft version.

    State transition: `draft_pending_review` → `approved` (on approval)

    Business rules enforced:
    - The approver (`approved_by`) must not be the same as the version author (4-eyes rule).
    - Only a `draft_pending_review` version can be approved.
    - An approved version cannot be re-approved (immutability).
    """
    return await svc.approve_procedure(
        procedure_id,
        body,
        ip_address=request.client.host if request.client else None,
    )


@router.post(
    "/{procedure_id}/publish",
    response_model=ProcedurePublishResponse,
    summary="Publish the approved version — makes it executable on the field",
)
async def publish_procedure(
    procedure_id: UUID,
    request: Request,
    svc: ProcedureSvcDep,
    user: CurrentUserDep,
) -> ProcedurePublishResponse:
    """
    Publish the approved version.

    State transition: `approved` → `published`

    The previously published version (if any) is atomically archived.
    All ongoing interventions referencing the old version are unaffected.
    """
    return await svc.publish_procedure(
        procedure_id,
        actor_id=user.identifier,
        ip_address=request.client.host if request.client else None,
    )


@router.get(
    "/{procedure_id}/active",
    response_model=ProcedureVersionRead,
    summary="Get the currently published version — used by Quest before intervention",
)
async def get_active_version(
    procedure_id: UUID, svc: ProcedureSvcDep
) -> ProcedureVersionRead:
    """
    Returns the published ProcedureVersion for the given Procedure.
    This is the endpoint the Quest client calls when starting an intervention.
    """
    procedure = await svc.get_procedure(procedure_id)
    if not procedure.active_version_id:
        from app.core.exceptions import NoActiveVersionError
        from uuid import UUID as _UUID
        raise NoActiveVersionError(_UUID(str(procedure.machine_id)))
    return procedure.active_version
