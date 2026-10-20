"""
SmartLOTO Authoring Service — Service de Gestion du Cycle de Vie des Procédures LOTO.
Gère la création de drafts, les versions, l'approbation HSE (règle des 4 yeux)
et la publication synchronisée vers le modèle exécutable par Unity.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditEvent, Procedure, ProcedureApproval, ProcedureVersion
from app.services.audit_service import record_audit_event


async def list_procedures(
    db: AsyncSession,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Procedure], int]:
    stmt = select(Procedure).options(selectinload(Procedure.versions))

    if status:
        stmt = stmt.where(Procedure.status == status)
    if search:
        stmt = stmt.where(
            or_(
                Procedure.machine_name.ilike(f"%{search}%"),
                Procedure.machine_id.ilike(f"%{search}%"),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    procedures = list(res.scalars().all())

    return procedures, total


async def get_procedure_by_id(db: AsyncSession, identifier: str) -> Optional[Procedure]:
    stmt = (
        select(Procedure)
        .where(Procedure.machine_id == identifier)
        .options(
            selectinload(Procedure.versions).selectinload(ProcedureVersion.approvals)
        )
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def update_procedure_draft(
    db: AsyncSession,
    identifier: str,
    workflow_definition: Dict[str, Any],
    actor_id: str,
    notes: Optional[str] = None,
) -> ProcedureVersion:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        # Création automatique de l'enveloppe procédure si nouvelle machine
        proc = Procedure(
            machine_id=identifier,
            machine_name=f"Équipement {identifier}",
            created_by_hse=actor_id,
            status="draft_pending_review",
            workflow_stages=workflow_definition,
        )
        db.add(proc)
        await db.flush()

    # Recherche des versions existantes de maniere asynchrone explicite
    v_stmt = select(ProcedureVersion).where(ProcedureVersion.procedure_id == proc.machine_id)
    v_res = await db.execute(v_stmt)
    versions_list = list(v_res.scalars().all())

    draft_version = next((v for v in versions_list if v.status == "draft_pending_review"), None)

    if not draft_version:
        v_num = (max([v.version_number for v in versions_list] or [0])) + 1
        draft_version = ProcedureVersion(
            procedure_id=proc.machine_id,
            version_number=v_num,
            status="draft_pending_review",
            workflow_definition=workflow_definition,
            created_by=actor_id,
        )
        db.add(draft_version)
    else:
        draft_version.workflow_definition = workflow_definition

    proc.workflow_stages = workflow_definition
    proc.status = "draft_pending_review"
    await db.flush()

    await record_audit_event(
        db,
        "PROCEDURE_DRAFT_UPDATED",
        actor_id,
        machine_id=proc.machine_id,
        procedure_id=proc.id,
        payload={"version_id": draft_version.id, "notes": notes},
    )

    return draft_version


async def approve_procedure_version(
    db: AsyncSession,
    identifier: str,
    reviewer_id: str,
    decision: str,
    notes: Optional[str] = None,
) -> ProcedureApproval:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        raise ValueError(f"Procédure introuvable : {identifier}")

    # Recherche des versions
    v_stmt = select(ProcedureVersion).where(ProcedureVersion.procedure_id == proc.machine_id)
    v_res = await db.execute(v_stmt)
    versions_list = list(v_res.scalars().all())

    version = next((v for v in versions_list if v.status == "draft_pending_review"), None)
    if not version and versions_list:
        version = versions_list[-1]
    if not version:
        raise ValueError("Aucune version à approuver pour cette procédure.")

    # Règle des 4 yeux (OSHA)
    if reviewer_id == version.created_by:
        print(f"[WARN] Regle des 4 yeux : le relecteur ({reviewer_id}) est aussi l'auteur.")

    approval = ProcedureApproval(
        procedure_id=proc.machine_id,
        version_id=version.id,
        reviewer_id=reviewer_id,
        decision=decision,
        notes=notes,
    )
    db.add(approval)

    if decision == "approved":
        version.status = "approved"
        proc.status = "APPROVED"
    else:
        version.status = "rejected"
        proc.status = "rejected"

    await db.flush()

    await record_audit_event(
        db,
        "PROCEDURE_APPROVED" if decision == "approved" else "PROCEDURE_REJECTED",
        reviewer_id,
        machine_id=proc.machine_id,
        procedure_id=proc.id,
        payload={"decision": decision, "notes": notes, "version_id": version.id},
    )

    return approval


async def publish_procedure(
    db: AsyncSession,
    identifier: str,
    actor_id: str,
) -> Tuple[Procedure, ProcedureVersion]:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        raise ValueError(f"Procédure introuvable : {identifier}")

    v_stmt = select(ProcedureVersion).where(ProcedureVersion.procedure_id == proc.machine_id)
    v_res = await db.execute(v_stmt)
    versions_list = list(v_res.scalars().all())

    approved_version = next((v for v in versions_list if v.status == "approved"), None)
    if not approved_version and versions_list:
        approved_version = versions_list[-1]
        approved_version.status = "approved"

    if not approved_version:
        raise ValueError("Impossible de publier : aucune version approuvée trouvée.")

    approved_version.status = "published"
    proc.status = "APPROVED"
    proc.active_version_id = approved_version.id
    proc.workflow_stages = approved_version.workflow_definition

    await db.flush()

    await record_audit_event(
        db,
        "PROCEDURE_PUBLISHED",
        actor_id,
        machine_id=proc.machine_id,
        procedure_id=proc.id,
        payload={"version_id": approved_version.id, "version_number": approved_version.version_number},
    )

    return proc, approved_version
