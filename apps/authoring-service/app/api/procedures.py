"""
SmartLOTO Authoring Service — Endpoints Procédures LOTO (consommés par le dashboard HSE).
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ApprovalCreatePayload,
    ApprovalRead,
    DraftUpdatePayload,
    PaginatedResponse,
    ProcedureListItem,
    ProcedurePublishResponse,
    ProcedureRead,
    ProcedureVersionRead,
)
from app.services import procedure_service

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ProcedureListItem])
async def list_procedures(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    items, total = await procedure_service.list_procedures(
        db, status=status, search=search, page=page, page_size=page_size
    )
    result_items = [
        ProcedureListItem(
            id=p.id,
            machine_id=p.machine_id,
            machine_name=p.machine_name,
            status=p.status,
            version_number=p.versions[0].version_number if p.versions else 1,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in items
    ]
    return PaginatedResponse(
        data=result_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{procedure_id}", response_model=ProcedureRead)
async def get_procedure(
    procedure_id: str,
    db: AsyncSession = Depends(get_db),
):
    proc = await procedure_service.get_procedure_by_id(db, procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procédure introuvable.")

    versions_read = []
    for v in proc.versions:
        approvals_read = [
            ApprovalRead(
                id=a.id,
                version_id=a.version_id,
                reviewer_id=a.reviewer_id,
                decision=a.decision,
                notes=a.notes,
                created_at=a.created_at,
            )
            for a in v.approvals
        ]
        versions_read.append(
            ProcedureVersionRead(
                id=v.id,
                procedure_id=v.procedure_id,
                version_number=v.version_number,
                status=v.status,
                workflow_definition=v.workflow_definition or {},
                created_by=v.created_by,
                created_at=v.created_at,
                approvals=approvals_read,
            )
        )

    return ProcedureRead(
        id=proc.id,
        machine_id=proc.machine_id,
        machine_name=proc.machine_name,
        status=proc.status,
        active_version_id=proc.active_version_id,
        versions=versions_read,
        created_at=proc.created_at,
        updated_at=proc.updated_at,
    )


@router.patch("/{procedure_id}/draft", response_model=ProcedureVersionRead)
async def update_draft(
    procedure_id: str,
    payload: DraftUpdatePayload,
    x_user_id: Optional[str] = Header("hse_supervisor@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    version = await procedure_service.update_procedure_draft(
        db,
        identifier=procedure_id,
        workflow_definition=payload.workflow_definition,
        actor_id=x_user_id or "hse_supervisor@smartloto.io",
        notes=payload.notes,
    )
    return ProcedureVersionRead(
        id=version.id,
        procedure_id=version.procedure_id,
        version_number=version.version_number,
        status=version.status,
        workflow_definition=version.workflow_definition or {},
        created_by=version.created_by,
        created_at=version.created_at,
        approvals=[],
    )


@router.post("/{procedure_id}/approve", response_model=ApprovalRead)
async def approve_procedure(
    procedure_id: str,
    payload: ApprovalCreatePayload,
    x_user_id: Optional[str] = Header("hse_reviewer@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    try:
        approval = await procedure_service.approve_procedure_version(
            db,
            identifier=procedure_id,
            reviewer_id=x_user_id or "hse_reviewer@smartloto.io",
            decision=payload.decision,
            notes=payload.notes,
        )
        return ApprovalRead(
            id=approval.id,
            version_id=approval.version_id,
            reviewer_id=approval.reviewer_id,
            decision=approval.decision,
            notes=approval.notes,
            created_at=approval.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{procedure_id}/publish", response_model=ProcedurePublishResponse)
async def publish_procedure(
    procedure_id: str,
    x_user_id: Optional[str] = Header("hse_manager@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    try:
        proc, version = await procedure_service.publish_procedure(
            db, identifier=procedure_id, actor_id=x_user_id or "hse_manager@smartloto.io"
        )
        return ProcedurePublishResponse(
            procedure_id=proc.id,
            published_version_id=version.id,
            published_at=proc.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{procedure_id}", status_code=204)
async def archive_procedure(
    procedure_id: str,
    db: AsyncSession = Depends(get_db),
):
    proc = await procedure_service.get_procedure_by_id(db, procedure_id)
    if proc:
        proc.status = "archived"
        await db.flush()
    return None
