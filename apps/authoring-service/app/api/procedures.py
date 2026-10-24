"""
SmartLOTO Authoring Service — Endpoints Procédures LOTO (consommés par le dashboard HSE).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
import copy
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

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
    ResolveClarificationPayload,
)
from app.services import procedure_service
from app.services.workflow_validation import apply_clarification_impact, validate_workflow
from app.schemas_workflow import ProcedureDraftV2

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

    def _build_list_item(p) -> ProcedureListItem:
        sorted_versions = sorted(p.versions, key=lambda v: v.version_number)
        current_version = sorted_versions[-1] if sorted_versions else None
        max_version_number = current_version.version_number if current_version else 1
        # Derive generation_source from the current version's generation metadata
        gen_source = "manual"
        open_errors = 0
        if current_version:
            wf = current_version.workflow_definition or {}
            if isinstance(wf, dict):
                meta = wf.get("_generation_metadata", {})
                if isinstance(meta, dict):
                    gen_source = meta.get("source_type", "manual") or "manual"
                # Count open validation errors: blocking diagnostics + unresolved clarifications (without double-counting)
                diags = [d for d in wf.get("validation_diagnostics", []) if isinstance(d, dict) and d.get("severity") in {"blocking", "error"} and d.get("category") != "source_integrity"]
                has_clarif_diags = any(d.get("code") == "CLARIFICATION_OPEN" for d in diags)
                clarifs = [q for q in wf.get("clarifications_required", []) if isinstance(q, dict) and q.get("status") == "unresolved"] if not has_clarif_diags else []
                open_errors = len(diags) + len(clarifs)
        has_published = any(v.status == "published" for v in p.versions)

        # Détermination du statut canonique normalisé (minuscule)
        raw_status = (current_version.status if current_version else p.status) or p.status or "draft_pending_review"
        canonical_status = str(raw_status).strip().lower()
        if canonical_status not in {"draft_pending_review", "approved", "published", "archived"}:
            if "publish" in canonical_status:
                canonical_status = "published"
            elif "approv" in canonical_status:
                canonical_status = "approved"
            else:
                canonical_status = "draft_pending_review"

        return ProcedureListItem(
            id=p.id,
            machine_id=p.machine_id,
            machine_name=p.machine_name,
            title=p.machine_name,
            created_by=p.created_by_hse,
            status=canonical_status,
            current_status=canonical_status,
            current_version_id=current_version.id if current_version else None,
            current_version_number=max_version_number,
            version_number=max_version_number,
            generation_source=gen_source,
            overall_confidence=None,  # computed per-step only; not aggregated here
            open_validation_errors=open_errors,
            has_published_version=has_published,
            workflow_definition=wf,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    result_items = [_build_list_item(p) for p in items]
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
        workflow = v.workflow_definition or {}
        if isinstance(workflow, dict) and workflow.get("schema_version") == "2.0":
            if "components" in workflow and isinstance(workflow["components"], list):
                from app.services.document_generation_service import enrich_component_signatures
                workflow["components"] = [
                    enrich_component_signatures(c, idx) if isinstance(c, dict) else c
                    for idx, c in enumerate(workflow["components"])
                ]
        metadata = workflow.get("_generation_metadata", {}) if isinstance(workflow, dict) else {}
        approvals_read = [
            ApprovalRead(
                id=a.id,
                version_id=a.version_id,
                reviewer_id=a.reviewer_id,
                decision=a.decision,
                notes=a.notes,
                created_at=a.created_at,
                approved_by=a.reviewer_id,
                decided_at=a.created_at,
            )
            for a in v.approvals
        ]
        versions_read.append(
            ProcedureVersionRead(
                id=v.id,
                procedure_id=v.procedure_id,
                version_number=v.version_number,
                status=v.status,
                workflow_definition=workflow,
                created_by=v.created_by,
                created_at=v.created_at,
                approvals=approvals_read,
                generation_source=metadata.get("source_type", "manual"),
                llm_model_used=metadata.get("llm_model"),
                schema_version=str(workflow.get("schema_version", "1.0")),
                validation_errors=list(dict.fromkeys(
                    [item.get("message", item.get("code", "Diagnostic")) for item in validate_workflow(workflow) if item.get("severity") in {"blocking", "error"} and item.get("category") != "source_integrity"] +
                    [str(q.get("question", "Clarification requise")) for q in workflow.get("clarifications_required", []) if isinstance(q, dict) and q.get("status") == "unresolved"]
                )),
                submitted_for_review_at=v.created_at,
                updated_at=v.created_at,
                latest_approval=approvals_read[-1] if approvals_read else None,
            )
        )

    active_id = proc.active_version_id
    active_version = next((v for v in versions_read if v.id == active_id), None)
    review_version = max(
        (v for v in versions_read if v.status == "draft_pending_review"),
        key=lambda item: (item.version_number, item.created_at),
        default=None,
    )
    if review_version is None and active_version is None and versions_read:
        review_version = max(versions_read, key=lambda item: (item.version_number, item.created_at))

    return ProcedureRead(
        id=proc.id,
        machine_id=proc.machine_id,
        machine_name=proc.machine_name,
        status=proc.status,
        active_version_id=proc.active_version_id,
        versions=versions_read,
        created_at=proc.created_at,
        updated_at=proc.updated_at,
        title=proc.machine_name,
        created_by=proc.created_by_hse,
        active_version=active_version,
        review_version=review_version,
    )


@router.patch("/{procedure_id}/draft", response_model=ProcedureVersionRead)
async def update_draft(
    procedure_id: str,
    payload: DraftUpdatePayload,
    x_user_id: Optional[str] = Header("hse_supervisor@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    workflow = payload.workflow_definition
    if workflow.get("schema_version") == "2.0":
        if workflow.get("machine_id") != procedure_id:
            raise HTTPException(status_code=422, detail="L'équipement du contenu doit correspondre à la ressource révisée.")
        try:
            workflow = ProcedureDraftV2.model_validate(workflow).model_dump(mode="json")
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "SCHEMA_INVALID", "issues": exc.errors(include_input=False)}) from exc
        workflow["validation_diagnostics"] = validate_workflow(workflow)
        for fact in workflow.get("technical_facts", []):
            if not isinstance(fact, dict) or fact.get("citation_status") != "manual_verified":
                continue
            citation_review = fact.get("citation_review")
            if isinstance(citation_review, dict) and str(citation_review.get("rationale", "")).strip():
                fact["citation_review"] = {
                    "rationale": str(citation_review["rationale"]).strip(),
                    "quote": str(fact.get("source_quote", "")),
                    "reviewed_by": x_user_id or "hse_supervisor@smartloto.io",
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }
        workflow["validation_diagnostics"] = validate_workflow(workflow)

    version = await procedure_service.update_procedure_draft(
        db,
        identifier=procedure_id,
        workflow_definition=workflow,
        actor_id=x_user_id or "hse_supervisor@smartloto.io",
        notes=payload.notes,
    )
    workflow = version.workflow_definition or {}
    metadata = workflow.get("_generation_metadata", {}) if isinstance(workflow, dict) else {}
    open_issues = [q.get("question", "Clarification requise") for q in workflow.get("clarifications_required", []) if isinstance(q, dict) and q.get("status") == "unresolved"]
    return ProcedureVersionRead(
        id=version.id,
        procedure_id=version.procedure_id,
        version_number=version.version_number,
        status=version.status,
        workflow_definition=version.workflow_definition or {},
        created_by=version.created_by,
        created_at=version.created_at,
        approvals=[],
        generation_source=metadata.get("source_type", "manual"),
        llm_model_used=metadata.get("llm_model"),
        schema_version=str(workflow.get("schema_version", "1.0")),
        validation_errors=list(dict.fromkeys(
            open_issues + [item.get("message", item.get("code", "Diagnostic")) for item in validate_workflow(workflow) if item.get("severity") in {"blocking", "error"} and item.get("category") != "source_integrity"]
        )),
        submitted_for_review_at=version.created_at,
        updated_at=version.created_at,
        latest_approval=None,
    )


@router.post("/{procedure_id}/resolve-clarification", response_model=ProcedureVersionRead)
async def resolve_clarification(
    procedure_id: str,
    payload: ResolveClarificationPayload,
    x_user_id: Optional[str] = Header("hse_supervisor@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    proc = await procedure_service.get_procedure_by_id(db, procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procédure introuvable.")

    versions = await procedure_service.get_versions(db, procedure_id)
    draft_version = next((v for v in reversed(versions) if v.status == "draft_pending_review"), None)
    if draft_version and draft_version.workflow_definition:
        workflow = copy.deepcopy(draft_version.workflow_definition)
    elif proc.workflow_stages:
        workflow = copy.deepcopy(proc.workflow_stages)
    else:
        raise HTTPException(status_code=400, detail="Aucun brouillon disponible pour cette procédure.")

    clarifications = workflow.get("clarifications_required", [])
    target_clarification = None
    for q in clarifications:
        if isinstance(q, dict) and str(q.get("id")) == str(payload.clarification_id):
            target_clarification = q
            break
    if not target_clarification:
        raise HTTPException(status_code=404, detail="Clarification introuvable dans le brouillon.")

    target_clarification["status"] = "resolved"
    target_clarification["resolution"] = {
        "answer": payload.answer,
        "rationale": payload.rationale or "Décision HSE validée",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": x_user_id or "hse_supervisor@smartloto.io",
    }
    target_clarification["affected_steps_reviewed"] = True

    affected_step_ids = set(target_clarification.get("affected_step_ids") or [])
    if payload.step_id:
        affected_step_ids.add(payload.step_id)

    # Adapt affected steps with the clarification answer
    for phase in workflow.get("phases", []):
        for stage in phase.get("stages", []):
            for step in stage.get("steps", []):
                s_id = str(step.get("step_id", ""))
                is_affected = s_id in affected_step_ids
                if not is_affected and target_clarification.get("related_component_ids"):
                    step_comps = set(step.get("component_refs") or [])
                    q_comps = set(target_clarification.get("related_component_ids") or [])
                    if step_comps & q_comps:
                        is_affected = True

                if is_affected:
                    verif = step.get("verification") or step.get("validation") or {}
                    criteria = verif.get("criteria", [])
                    new_criteria = []
                    replaced = False
                    for c in criteria:
                        c_str = str(c)
                        if "à définir" in c_str.lower() or "inférieure au seuil" in c_str.lower():
                            new_criteria.append(payload.answer)
                            replaced = True
                        else:
                            new_criteria.append(c_str)
                    if not replaced and payload.answer:
                        new_criteria.append(f"Critère validé : {payload.answer}")
                    verif["criteria"] = new_criteria
                    step["verification"] = verif

                    inst = str(step.get("instruction", ""))
                    if "à définir" in inst.lower():
                        inst = inst.replace("(à définir)", payload.answer).replace("à définir", payload.answer)
                        step["instruction"] = inst

    # Update clarification_needed on components
    all_unresolved_comps = set()
    for q in workflow.get("clarifications_required", []):
        if isinstance(q, dict) and q.get("status") != "resolved":
            for cid in q.get("related_component_ids") or []:
                all_unresolved_comps.add(str(cid).upper())
                all_unresolved_comps.add(str(cid).lower())

    for comp in workflow.get("components", []):
        c_internal = str(comp.get("internal_id") or "").upper()
        c_id = str(comp.get("component_id") or "").upper()
        if c_internal in all_unresolved_comps or c_id in all_unresolved_comps:
            comp["clarification_needed"] = True
        else:
            comp["clarification_needed"] = False

    apply_clarification_impact(workflow)
    workflow["validation_diagnostics"] = validate_workflow(workflow)

    updated_version = await procedure_service.update_procedure_draft(
        db,
        identifier=procedure_id,
        workflow_definition=workflow,
        actor_id=x_user_id or "hse_supervisor@smartloto.io",
        notes=f"Clarification '{str(target_clarification.get('question', ''))[:40]}' résolue",
    )

    wf = updated_version.workflow_definition or {}
    metadata = wf.get("_generation_metadata", {}) if isinstance(wf, dict) else {}
    open_issues = [
        q.get("question", "Clarification requise")
        for q in wf.get("clarifications_required", [])
        if isinstance(q, dict) and q.get("status") == "unresolved"
    ]
    return ProcedureVersionRead(
        id=updated_version.id,
        procedure_id=updated_version.procedure_id,
        version_number=updated_version.version_number,
        status=updated_version.status,
        workflow_definition=updated_version.workflow_definition or {},
        created_by=updated_version.created_by,
        created_at=updated_version.created_at,
        approvals=[],
        generation_source=metadata.get("source_type", "manual"),
        llm_model_used=metadata.get("llm_model"),
        schema_version=str(wf.get("schema_version", "1.0")),
        validation_errors=list(dict.fromkeys(
            open_issues + [item.get("message", item.get("code", "Diagnostic")) for item in validate_workflow(wf) if item.get("severity") in {"blocking", "error"} and item.get("category") != "source_integrity"]
        )),
        submitted_for_review_at=updated_version.created_at,
        updated_at=updated_version.created_at,
        latest_approval=None,
    )


@router.post("/{procedure_id}/versions/{version_id}/approve", response_model=ApprovalRead)
async def approve_procedure(
    procedure_id: str,
    version_id: str,
    payload: ApprovalCreatePayload,
    x_user_id: Optional[str] = Header("hse_reviewer@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    try:
        resolved_version_id = payload.version_id or version_id
        resolved_reviewer_id = payload.approved_by or x_user_id or "hse_reviewer@smartloto.io"
        approval = await procedure_service.approve_procedure_version(
            db,
            identifier=procedure_id,
            version_id=resolved_version_id,
            reviewer_id=resolved_reviewer_id,
            decision=payload.decision,
            notes=payload.notes or None,
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


@router.post("/{procedure_id}/versions/{version_id}/publish", response_model=ProcedurePublishResponse)
async def publish_procedure(
    procedure_id: str,
    version_id: str,
    x_user_id: Optional[str] = Header("hse_manager@smartloto.io"),
    db: AsyncSession = Depends(get_db),
):
    try:
        proc, version = await procedure_service.publish_procedure(
            db, identifier=procedure_id, version_id=version_id,
            actor_id=x_user_id or "hse_manager@smartloto.io"
        )
        return ProcedurePublishResponse(
            procedure_id=proc.id,
            published_version_id=version.id,
            published_at=proc.updated_at,
            published_by=x_user_id or "hse_manager@smartloto.io",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{procedure_id}/export")
async def export_procedure(
    procedure_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Exporte la procédure publiée sous forme de contrat JSON Unity déterministe et complet."""
    proc = await procedure_service.get_procedure_by_id(db, procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procédure introuvable.")

    active_id = proc.active_version_id
    versions = proc.versions or []
    target_version = next((v for v in versions if v.id == active_id), None)
    if not target_version:
        target_version = next((v for v in reversed(versions) if v.status == "published"), None)
    if not target_version and versions:
        target_version = versions[-1]

    if not target_version or not target_version.workflow_definition:
        raise HTTPException(status_code=400, detail="Aucune version de procédure disponible pour l'export.")

    wf = copy.deepcopy(target_version.workflow_definition)

    # Enrichir les composants si nécessaire
    if "components" in wf and isinstance(wf["components"], list):
        from app.services.document_generation_service import enrich_component_signatures
        wf["components"] = [
            enrich_component_signatures(c, idx) if isinstance(c, dict) else c
            for idx, c in enumerate(wf["components"])
        ]

    # Importer la normalisation stricte Unity de field-service ou équivalent
    from app.services.document_generation_service import POC_COMPONENT_SIGNATURES
    sig_map = {
        "marking": "MARQUAGE",
        "fixed_text": "MARQUAGE",
        "color_pattern": "MARQUAGE",
        "local_geometry": "GÉOMÉTRIE",
        "pictogram": "PICTOGRAMME",
        "symbol": "SYMBOLE",
    }

    clean_components = []
    for idx, c in enumerate(wf.get("components") or []):
        cid = str(c.get("component_id") or f"C{idx+1:02d}").strip()
        internal_id = str(c.get("internal_id") or cid).strip()
        tag = str(c.get("source_tag") or c.get("tag") or cid).strip()
        unity_class_id = str(c.get("unity_class_id") or "").strip()
        cname = str(c.get("component_name") or c.get("label") or cid).strip()
        label = str(c.get("label") or cname).strip()
        desc = str(c.get("description") or "").strip()

        clean_sigs = []
        for feat in (c.get("invariant_features") or []):
            ftype = str(feat.get("feature_type") or "marking").strip()
            clean_sigs.append({
                "signature_type": sig_map.get(ftype.lower(), "MARQUAGE"),
                "feature_type": ftype,
                "description": str(feat.get("description") or "").strip(),
                "details": str(feat.get("details") or "").strip(),
            })

        clean_rules = []
        for st in (c.get("verifiable_states") or c.get("states") or []):
            clean_rules.append({
                "state_name": str(st.get("state_name") or "").strip().upper(),
                "physical_rule": str(st.get("physical_rule") or "").strip(),
                "candidate_prompt": str(st.get("candidate_prompt") or unity_class_id).strip(),
                "supported_by_unity": bool(st.get("supported_by_unity", False)),
                "requires_human_confirmation": True,
            })

        clean_components.append({
            "component_id": cid,
            "internal_id": internal_id,
            "tag": tag,
            "source_tag": tag,
            "unity_class_id": unity_class_id,
            "component_name": cname,
            "label": label,
            "description": desc,
            "physical_signatures": clean_sigs,
            "invariant_features": clean_sigs,
            "state_rules": clean_rules,
            "verifiable_states": clean_rules,
            "relations": [str(r) for r in (c.get("relations") or [])],
            "clarification_needed": bool(c.get("clarification_needed", False)),
        })

    clean_phases = []
    for p_idx, p in enumerate(wf.get("phases", []), start=1):
        ptype = str(p.get("phase_type") or "").strip().upper()
        if "ISOLAT" in ptype or "LOCK" in ptype:
            canonical_phase_type = "ISOLATION"
        elif "ACCES" in ptype or "ACCESS" in ptype:
            canonical_phase_type = "ACCÈS"
        elif "INTERVENT" in ptype:
            canonical_phase_type = "INTERVENTION"
        elif "RESTOR" in ptype or "DECON" in ptype:
            canonical_phase_type = "RESTORATION"
        else:
            canonical_phase_type = ptype or "OPERATION"

        clean_stages = []
        for s_idx, s in enumerate(p.get("stages", []), start=1):
            sid_str = str(s.get("stage_id") or f"S{p_idx}-{s_idx}").strip()
            clean_steps = []
            for st_idx, st in enumerate(s.get("steps") or s.get("actions") or [], start=1):
                stid = str(st.get("step_id") or st.get("action_id") or f"A-{st_idx}").strip()
                instruction = str(st.get("instruction") or st.get("description") or "").strip()
                crefs = [str(r).strip() for r in (st.get("component_refs") or [])]
                v_raw = st.get("verification") or st.get("validation") or {}
                v_method = str(v_raw.get("method") or "visual_observation").strip()
                v_criteria = [str(cr).strip() for cr in (v_raw.get("criteria") or [])]
                v_evidence = [str(ev).strip() for ev in (v_raw.get("required_evidence") or [])]
                v_indeterminate = [str(ind).strip() for ind in (v_raw.get("indeterminate_when") or [])]
                v_prompts = [str(pr).strip() for pr in (v_raw.get("candidate_prompts") or v_raw.get("yolo_candidate_prompts") or [])]

                fallback_mode = str(v_raw.get("fallback_mode") or "none").strip()
                virtual_button = bool(v_raw.get("virtual_button", False))
                unity_hint = str(v_raw.get("unity_ui_hint") or "").strip()
                if v_method in {"measurement", "sensor_signal", "not_defined"}:
                    fallback_mode = "human_confirmation"
                    virtual_button = True
                    unity_hint = "Validation Humaine (Bouton Virtuel)"

                clean_steps.append({
                    "step_id": stid,
                    "action_id": stid,
                    "sequence": int(st.get("sequence", st_idx)),
                    "instruction": instruction,
                    "description": instruction,
                    "component_refs": crefs,
                    "primary_component": crefs[0] if crefs else "",
                    "vision_prompt": v_prompts[0] if v_prompts else ((crefs[0].lower() if crefs else "")),
                    "completion_check": v_criteria[0] if v_criteria else "",
                    "expected_result": str(st.get("expected_result") or v_raw.get("expected_state") or "").strip(),
                    "spatial_guide": None,
                    "verification": {
                        "method": v_method,
                        "criteria": v_criteria,
                        "required_evidence": v_evidence,
                        "instrument_refs": [str(ir).strip() for ir in (v_raw.get("instrument_refs") or [])],
                        "indeterminate_when": v_indeterminate,
                        "candidate_prompts": v_prompts,
                        "fallback_mode": fallback_mode,
                        "virtual_button": virtual_button,
                        "unity_ui_hint": unity_hint,
                    },
                })

            clean_stages.append({
                "stage_id": s_idx,
                "stage_code": sid_str,
                "sequence": int(s.get("sequence", s_idx)),
                "title": str(s.get("title") or f"Étape {s_idx}").strip(),
                "steps": clean_steps,
                "actions": clean_steps,
            })

        clean_phases.append({
            "phase_id": str(p.get("phase_id") or f"P{p_idx}").strip(),
            "phase_type": canonical_phase_type,
            "sequence": int(p.get("sequence", p_idx)),
            "title": str(p.get("title") or f"Phase {p_idx}").strip(),
            "description": str(p.get("description") or "").strip(),
            "stages": clean_stages,
        })

    clean_clarifications = []
    for q in wf.get("clarifications_required") or []:
        clean_clarifications.append({
            "id": str(q.get("id") or ""),
            "question": str(q.get("question") or ""),
            "status": str(q.get("status") or ""),
            "answer": str((q.get("resolution") or {}).get("answer") or ""),
            "rationale": str((q.get("resolution") or {}).get("rationale") or ""),
            "affected_step_ids": [str(x) for x in (q.get("affected_step_ids") or [])],
            "related_component_ids": [str(x) for x in (q.get("related_component_ids") or [])],
        })

    def _clean_nulls(item):
        if item is None:
            return ""
        if isinstance(item, dict):
            return {k: _clean_nulls(v) for k, v in item.items()}
        if isinstance(item, list):
            return [_clean_nulls(x) for x in item]
        return item

    maintenance_obj = str(wf.get("maintenance_objective") or "").strip()
    expected_final_state = str(wf.get("expected_final_state") or "").strip()

    enriched_workflow = dict(wf)
    enriched_workflow["schema_version"] = "2.0"
    enriched_workflow["procedure_id"] = proc.machine_id
    enriched_workflow["machine_id"] = proc.machine_id
    enriched_workflow["machine_name"] = proc.machine_name
    enriched_workflow["maintenance_objective"] = maintenance_obj
    enriched_workflow["expected_final_state"] = expected_final_state
    enriched_workflow["components"] = clean_components
    enriched_workflow["phases"] = clean_phases
    enriched_workflow["clarifications_required"] = clean_clarifications

    import json
    export_payload = {
        "procedure_id": proc.machine_id,
        "machine_id": proc.machine_id,
        "machine_name": proc.machine_name,
        "title": proc.machine_name,
        "version": target_version.id,
        "procedure_version_id": target_version.id,
        "schema_version": "2.0",
        "objective": maintenance_obj,
        "maintenance_objective": maintenance_obj,
        "expected_final_state": expected_final_state,
        "status": proc.status,
        "hse_approval_status": "approved" if str(proc.status).upper() in {"PUBLISHED", "APPROVED"} else str(proc.status).lower(),
        "created_by_hse": proc.created_by_hse,
        "components": clean_components,
        "phases": clean_phases,
        "clarifications_required": clean_clarifications,
        "workflow_stages": enriched_workflow,
        "workflow_json": json.dumps(enriched_workflow, ensure_ascii=False),
        "anchors": [],
    }

    return _clean_nulls(export_payload)


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
