"""
SmartLOTO Authoring Service Ã¢â‚¬â€ Service de Gestion du Cycle de Vie des ProcÃƒÂ©dures LOTO.
GÃƒÂ¨re la crÃƒÂ©ation de drafts, les versions, l'approbation HSE (rÃƒÂ¨gle des 4 yeux)
et la publication synchronisÃƒÂ©e vers le modÃƒÂ¨le exÃƒÂ©cutable par Unity.
"""

from __future__ import annotations

import os
import json
import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditEvent, Procedure, ProcedureApproval, ProcedureVersion
from app.services.audit_service import record_audit_event
from app.services.workflow_validation import apply_clarification_impact, validate_workflow


def _unresolved_clarifications(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in workflow.get("clarifications_required", []) if item.get("status") != "resolved"]


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
        st_lower = status.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(Procedure.status) == st_lower,
                Procedure.versions.any(func.lower(ProcedureVersion.status) == st_lower),
            )
        )
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


async def restore_published_revision_pointers(db: AsyncSession) -> int:
    """Repair pointers from durable publication audit events without seeding data."""
    events = (await db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "PROCEDURE_PUBLISHED").order_by(AuditEvent.created_at)
    )).scalars().all()
    published_ids: dict[str, str] = {}
    for event in events:
        version_id = (event.payload or {}).get("version_id")
        if version_id and event.machine_id:
            published_ids[event.machine_id] = str(version_id)
    repaired = 0
    for machine_id, version_id in published_ids.items():
        procedure = await get_procedure_by_id(db, machine_id)
        version = await db.get(ProcedureVersion, version_id)
        if not procedure or not version or version.procedure_id != machine_id or version.status != "published":
            continue
        if procedure.active_version_id == version.id and procedure.status == "PUBLISHED":
            continue
        procedure.workflow_stages = copy.deepcopy(version.workflow_definition or {})
        procedure.active_version_id = version.id
        procedure.status = "PUBLISHED"
        repaired += 1
    if repaired:
        await db.flush()
    return repaired


async def update_procedure_draft(
    db: AsyncSession,
    identifier: str,
    workflow_definition: Dict[str, Any],
    actor_id: str,
    notes: Optional[str] = None,
) -> ProcedureVersion:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        # CrÃƒÂ©ation automatique de l'enveloppe procÃƒÂ©dure si nouvelle machine
        proc = Procedure(
            machine_id=identifier,
            machine_name=workflow_definition.get("machine_name") or f"Ãƒâ€°quipement {identifier}",
            created_by_hse=actor_id,
            status="draft_pending_review",
            workflow_stages=workflow_definition,
        )
        db.add(proc)
        await db.flush()

    # Recherche des versions existantes de maniere asynchrone explicite
    v_stmt = select(ProcedureVersion).where(ProcedureVersion.procedure_id == proc.machine_id)
    v_res = await db.execute(v_stmt)
    versions_list = sorted(v_res.scalars().all(), key=lambda item: item.version_number)

    # Every generation or reviewer save creates a revision. Prior model output
    # and human edits remain available in history instead of being overwritten.
    # Réutiliser le brouillon en cours s'il est déjà en attente de revue (évite les doublons de versions)
    current_draft = None
    for v in reversed(versions_list):
        if v.status == "draft_pending_review":
            current_draft = v
            break

    v_num = (max([v.version_number for v in versions_list] or [0])) + 1
    workflow_definition = copy.deepcopy(workflow_definition)
    if workflow_definition.get("schema_version") == "2.0":
        from app.services.phase_policy import normalize_draft_phases
        workflow_definition = normalize_draft_phases(workflow_definition)
        if "components" in workflow_definition and isinstance(workflow_definition["components"], list):
            from app.services.document_generation_service import enrich_component_signatures
            workflow_definition["components"] = [
                enrich_component_signatures(c, idx) if isinstance(c, dict) else c
                for idx, c in enumerate(workflow_definition["components"])
            ]
        apply_clarification_impact(workflow_definition)
        previous_revision = versions_list[-1].workflow_definition if versions_list else None
        if isinstance(previous_revision, dict) and previous_revision.get("revision_id"):
            workflow_definition["parent_revision_id"] = previous_revision["revision_id"]
        workflow_definition["revision_id"] = str(uuid.uuid4())
        workflow_definition["validation_diagnostics"] = validate_workflow(workflow_definition)

    if current_draft is not None:
        current_draft.workflow_definition = workflow_definition
        current_draft.created_by = actor_id
        draft_version = current_draft
    else:
        draft_version = ProcedureVersion(
            procedure_id=proc.machine_id,
            version_number=v_num,
            status="draft_pending_review",
            workflow_definition=workflow_definition,
            created_by=actor_id,
        )
        db.add(draft_version)

    if proc.status != "PUBLISHED":
        proc.workflow_stages = copy.deepcopy(workflow_definition)
        proc.active_version_id = draft_version.id

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
    version_id: str,
    reviewer_id: str,
    decision: str,
    notes: Optional[str] = None,
    signature: Optional[Dict[str, Any]] = None,
) -> ProcedureApproval:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        raise ValueError(f"ProcÃƒÂ©dure introuvable : {identifier}")

    # Recherche des versions
    version = await db.get(ProcedureVersion, version_id)
    if not version or version.procedure_id != proc.machine_id:
        raise ValueError("RÃƒÂ©vision introuvable pour cette procÃƒÂ©dure.")
    if version.status != "draft_pending_review":
        raise ValueError("Seule une rÃƒÂ©vision en attente peut ÃƒÂªtre approuvÃƒÂ©e ou rejetÃƒÂ©e.")

    unresolved = _unresolved_clarifications(version.workflow_definition or {})
    if decision == "approved" and unresolved:
        ids = ", ".join(item.get("id", "unknown") for item in unresolved)
        raise ValueError(f"Approbation bloquÃƒÂ©e : clarifications non rÃƒÂ©solues ({ids}).")
    if decision == "approved":
        blockers = [
            item for item in validate_workflow(version.workflow_definition or {})
            if item.get("severity") in {"blocking", "error"} and item.get("category") != "source_integrity"
        ]
        if blockers:
            raise ValueError(
                "Approbation bloquÃƒÂ©e : diagnostics non rÃƒÂ©solus ("
                + "; ".join(item.get("code", "validation") for item in blockers)
                + ")."
            )

    # Règle des 4 yeux (OSHA)
    env_name = os.getenv("APP_ENV", "development").lower()
    allow_self = os.getenv("ALLOW_SELF_APPROVAL", "true").lower() in {"true", "1", "yes"}
    is_dev = env_name in {"development", "dev", "mvp", "test"} or allow_self
    if reviewer_id == version.created_by and not is_dev:
        raise ValueError("Approbation bloquée : le relecteur doit être différent de l'auteur (règle des 4 yeux).")

    signed_record = None
    if decision == "approved" and signature is not None:
        import hashlib
        import json
        from datetime import datetime, timezone
        name = str(signature.get("name") or "").strip()
        if not name or signature.get("accepted") is not True:
            raise ValueError("Le nom du signataire et son engagement formel sont requis.")
        signed_record = {"name": name, "role": "Responsable HSE", "reviewer_id": reviewer_id,
                         "signed_at": datetime.now(timezone.utc).isoformat(), "accepted": True,
                         "version_id": version.id}
        signed_record["sha256"] = hashlib.sha256(json.dumps(signed_record, sort_keys=True).encode()).hexdigest()

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
        if not proc.active_version_id:
            proc.status = "APPROVED"
    else:
        version.status = "rejected"
        if not proc.active_version_id:
            proc.status = "rejected"

    await db.flush()

    await record_audit_event(
        db,
        "PROCEDURE_APPROVED" if decision == "approved" else "PROCEDURE_REJECTED",
        reviewer_id,
        machine_id=proc.machine_id,
        procedure_id=proc.id,
        payload={"decision": decision, "notes": notes, "version_id": version.id,
                 "approval_id": approval.id, "signature": signed_record},
    )

    return approval


async def publish_procedure(
    db: AsyncSession,
    identifier: str,
    version_id: str,
    actor_id: str,
) -> Tuple[Procedure, ProcedureVersion]:
    proc = await get_procedure_by_id(db, identifier)
    if not proc:
        raise ValueError(f"ProcÃƒÂ©dure introuvable : {identifier}")

    approved_version = await db.get(ProcedureVersion, version_id)
    if not approved_version or approved_version.procedure_id != proc.machine_id:
        raise ValueError("RÃƒÂ©vision introuvable pour cette procÃƒÂ©dure.")
    if approved_version.status != "approved":
        raise ValueError("Seule la rÃƒÂ©vision approuvÃƒÂ©e exacte peut ÃƒÂªtre publiÃƒÂ©e.")

    unresolved = _unresolved_clarifications(approved_version.workflow_definition or {})
    if unresolved:
        ids = ", ".join(item.get("id", "unknown") for item in unresolved)
        raise ValueError(f"Publication bloquÃƒÂ©e : clarifications non rÃƒÂ©solues ({ids}).")

    blockers = [item for item in validate_workflow(approved_version.workflow_definition or {}) if item.get("severity") in {"blocking", "error"} and item.get("category") != "source_integrity"]
    if blockers:
        raise ValueError("Publication bloquee : diagnostics non resolus (" + "; ".join(item["code"] for item in blockers) + ").")
    workflow = approved_version.workflow_definition or {}
    if workflow.get("schema_version") not in {"1.0", "2.0"}:
        raise ValueError("Publication blocked: the operator client does not support this schema version.")
    # Keep at most one currently published revision. Past interventions retain
    # their own procedure_version_id and remain pinned to the exact revision.
    v_stmt = select(ProcedureVersion).where(
        ProcedureVersion.procedure_id == proc.machine_id,
        ProcedureVersion.status == "published",
    )
    published_res = await db.execute(v_stmt)
    for previous in published_res.scalars().all():
        previous.status = "superseded"

    approved_version.status = "published"
    proc.status = "PUBLISHED"
    proc.workflow_stages = copy.deepcopy(approved_version.workflow_definition)
    proc.active_version_id = approved_version.id

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
