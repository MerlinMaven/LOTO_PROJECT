"""
SmartLOTO Field Service — API Procédures LOTO (consommé par SmartLOTOClient.cs).

Contrat figé Unity (ne pas modifier sans recompiler l'application Quest) :
  GET  /procedures
  GET  /procedures/{machine_id}
  POST /procedures/{machine_id}/anchors
"""

from __future__ import annotations

from typing import Any, Dict, List
import math
from fastapi import APIRouter, HTTPException, Query

import app.database as database
from app.models import AnchorsUpdate

router = APIRouter()


def _sanitize_spatial_guide(raw_guide: Any) -> Dict[str, Any] | None:
    """Return an AR pose only when it was explicitly calibrated and complete."""
    if not isinstance(raw_guide, dict):
        return None
    keys = ("pos_x", "pos_y", "pos_z", "rot_x", "rot_y", "rot_z")
    if any(key not in raw_guide or raw_guide[key] is None for key in keys):
        return None
    try:
        values = {key: float(raw_guide[key]) for key in keys}
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values.values()):
        return None
    return {"hologram_type": str(raw_guide.get("hologram_type", "")), **values}


def _sanitize_actions(raw_actions: Any) -> List[Dict[str, Any]]:
    """Garantit que actions est une liste d'ActionData conformes."""
    if not isinstance(raw_actions, list):
        return []
    actions: List[Dict[str, Any]] = []
    for idx, act in enumerate(raw_actions, start=1):
        if not isinstance(act, dict):
            continue
        if not act.get("action_id") or not act.get("description"):
            continue
        actions.append({
            "action_id": str(act["action_id"]),
            "description": str(act["description"]),
            "vision_prompt": str(act.get("vision_prompt", "")),
            "completion_check": str(act.get("completion_check") or "Verification to define"),
            "spatial_guide": _sanitize_spatial_guide(act.get("spatial_guide")),
        })
    return actions


def _sanitize_stages(raw_stages: Any) -> List[Dict[str, Any]]:
    """Garantit que chaque étape (StageData) a stage_id, title et actions."""
    if not isinstance(raw_stages, list):
        return []
    stages: List[Dict[str, Any]] = []
    for idx, stg in enumerate(raw_stages, start=1):
        if not isinstance(stg, dict):
            continue
        stages.append({
            "stage_id": int(stg.get("stage_id", idx)),
            "title": str(stg.get("title", f"Étape {idx}")),
            "actions": _sanitize_actions(stg.get("actions", [])),
        })
    return stages


def _sanitize_anchors(raw_anchors: Any) -> List[Dict[str, Any]]:
    """Keep only complete, finite calibrated poses; never create zero coordinates."""
    if not isinstance(raw_anchors, dict):
        return []
    clean: List[Dict[str, Any]] = []
    keys = ("pos_x", "pos_y", "pos_z", "rot_x", "rot_y", "rot_z")
    for organ_name, coords in raw_anchors.items():
        if not isinstance(coords, dict) or any(key not in coords or coords[key] is None for key in keys):
            continue
        try:
            pose = {key: float(coords[key]) for key in keys}
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(value) for value in pose.values()):
            clean.append({"organ_name": str(organ_name), **pose})
    return clean


SIGNATURE_TYPE_MAP = {
    "marking": "MARQUAGE",
    "fixed_text": "MARQUAGE",
    "color_pattern": "MARQUAGE",
    "local_geometry": "GÉOMÉTRIE",
    "pictogram": "PICTOGRAMME",
    "symbol": "SYMBOLE",
}


def _clean_null_values(item: Any) -> Any:
    """Remplace récursivement toute valeur None par des chaînes vides pour éviter les blocages Unity C#."""
    if item is None:
        return ""
    if isinstance(item, dict):
        return {k: _clean_null_values(v) for k, v in item.items()}
    if isinstance(item, list):
        return [_clean_null_values(x) for x in item]
    return item


def sanitize_procedure_for_unity(proc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise rigoureusement la procédure LOTO pour JsonUtility et Newtonsoft.Json de Unity.
    Aucun champ manquant ou mal typé ne peut provoquer de crash côté C#.
    """
    machine_id = str(proc.get("machine_id") or "").strip()
    if not machine_id:
        raise HTTPException(status_code=422, detail="Identifiant equipement manquant dans la procedure.")
    machine_name = str(proc.get("machine_name") or machine_id)
    created_by_hse = str(proc.get("created_by_hse") or "")
    status = str(proc.get("status") or "UNKNOWN")
    version_id = str(proc.get("procedure_version_id") or "")

    raw_stages = proc.get("workflow_stages", {})
    if isinstance(raw_stages, str):
        try:
            import json
            raw_stages = json.loads(raw_stages)
        except Exception:
            raw_stages = {}
    if not isinstance(raw_stages, dict):
        raw_stages = {}

    if raw_stages.get("schema_version") == "2.0":
        if not isinstance(raw_stages.get("phases"), list):
            raise HTTPException(status_code=409, detail="Canonical workflow has no valid phases array.")

        maintenance_obj = str(raw_stages.get("maintenance_objective") or proc.get("maintenance_objective") or "").strip()
        expected_final_state = str(raw_stages.get("expected_final_state") or "").strip()

        # 1. Matrice Vision AR : Normalisation rigoureuse des 7 composants
        clean_components = []
        raw_comps = raw_stages.get("components") or []
        for idx, c in enumerate(raw_comps):
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
                sig_type = SIGNATURE_TYPE_MAP.get(ftype.lower(), "MARQUAGE")
                fdesc = str(feat.get("description") or "").strip()
                clean_sigs.append({
                    "signature_type": sig_type,
                    "feature_type": ftype,
                    "description": fdesc,
                    "details": str(feat.get("details") or "").strip(),
                })

            clean_rules = []
            for st in (c.get("verifiable_states") or c.get("states") or []):
                sname = str(st.get("state_name") or "").strip().upper()
                prule = str(st.get("physical_rule") or "").strip()
                cprompt = str(st.get("candidate_prompt") or unity_class_id).strip()
                clean_rules.append({
                    "state_name": sname,
                    "physical_rule": prule,
                    "candidate_prompt": cprompt,
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

        # 2. Workflow séquentiel canonique : Normalisation des phases, stages et steps
        clean_phases = []
        for p_idx, p in enumerate(raw_stages.get("phases", []), start=1):
            pid = str(p.get("phase_id") or f"P{p_idx}").strip()
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
                sseq = int(s.get("sequence", s_idx))
                stitle = str(s.get("title") or f"Étape {s_idx}").strip()

                clean_steps = []
                for st_idx, st in enumerate(s.get("steps") or s.get("actions") or [], start=1):
                    stid = str(st.get("step_id") or st.get("action_id") or f"A-{st_idx}").strip()
                    stseq = int(st.get("sequence", st_idx))
                    instruction = str(st.get("instruction") or st.get("description") or "").strip()
                    crefs = [str(r).strip() for r in (st.get("component_refs") or [])]
                    primary_comp = crefs[0] if crefs else ""

                    v_raw = st.get("verification") or st.get("validation") or {}
                    v_method = str(v_raw.get("method") or "visual_observation").strip()
                    v_criteria = [str(cr).strip() for cr in (v_raw.get("criteria") or [])]
                    v_evidence = [str(ev).strip() for ev in (v_raw.get("required_evidence") or [])]
                    v_indeterminate = [str(ind).strip() for ind in (v_raw.get("indeterminate_when") or [])]
                    v_prompts = [str(pr).strip() for pr in (v_raw.get("candidate_prompts") or v_raw.get("yolo_candidate_prompts") or [])]

                    fallback_mode = str(v_raw.get("fallback_mode") or "none").strip()
                    virtual_button = bool(v_raw.get("virtual_button", False))
                    unity_hint = str(v_raw.get("unity_ui_hint") or "").strip()

                    # Repli gracieux Unity pour les vérifications physiques
                    if v_method in {"measurement", "sensor_signal", "not_defined"}:
                        fallback_mode = "human_confirmation"
                        virtual_button = True
                        unity_hint = "Validation Humaine (Bouton Virtuel)"

                    clean_verif = {
                        "method": v_method,
                        "criteria": v_criteria,
                        "required_evidence": v_evidence,
                        "instrument_refs": [str(ir).strip() for ir in (v_raw.get("instrument_refs") or [])],
                        "indeterminate_when": v_indeterminate,
                        "candidate_prompts": v_prompts,
                        "fallback_mode": fallback_mode,
                        "virtual_button": virtual_button,
                        "unity_ui_hint": unity_hint,
                    }

                    clean_steps.append({
                        "step_id": stid,
                        "action_id": stid,
                        "sequence": stseq,
                        "instruction": instruction,
                        "description": instruction,
                        "component_refs": crefs,
                        "primary_component": primary_comp,
                        "vision_prompt": v_prompts[0] if v_prompts else (primary_comp.lower() if primary_comp else ""),
                        "completion_check": v_criteria[0] if v_criteria else "",
                        "expected_result": str(st.get("expected_result") or v_raw.get("expected_state") or "").strip(),
                        "spatial_guide": None,
                        "verification": clean_verif,
                    })

                clean_stages.append({
                    "stage_id": s_idx,
                    "stage_code": sid_str,
                    "sequence": sseq,
                    "title": stitle,
                    "steps": clean_steps,
                    "actions": clean_steps,
                })

            clean_phases.append({
                "phase_id": pid,
                "phase_type": canonical_phase_type,
                "sequence": int(p.get("sequence", p_idx)),
                "title": str(p.get("title") or f"Phase {p_idx}").strip(),
                "description": str(p.get("description") or "").strip(),
                "stages": clean_stages,
            })

        # 3. Clarifications HSE résolues intégrées
        clean_clarifications = []
        for q in raw_stages.get("clarifications_required") or []:
            clean_clarifications.append({
                "id": str(q.get("id") or ""),
                "question": str(q.get("question") or ""),
                "status": str(q.get("status") or ""),
                "answer": str((q.get("resolution") or {}).get("answer") or ""),
                "rationale": str((q.get("resolution") or {}).get("rationale") or ""),
                "affected_step_ids": [str(x) for x in (q.get("affected_step_ids") or [])],
                "related_component_ids": [str(x) for x in (q.get("related_component_ids") or [])],
            })

        enriched_workflow = dict(raw_stages)
        enriched_workflow["schema_version"] = "2.0"
        enriched_workflow["procedure_id"] = machine_id
        enriched_workflow["machine_id"] = machine_id
        enriched_workflow["machine_name"] = machine_name
        enriched_workflow["maintenance_objective"] = maintenance_obj
        enriched_workflow["expected_final_state"] = expected_final_state
        enriched_workflow["components"] = clean_components
        enriched_workflow["phases"] = clean_phases
        enriched_workflow["clarifications_required"] = clean_clarifications

        import json
        payload = {
            "procedure_id": machine_id,
            "machine_id": machine_id,
            "machine_name": machine_name,
            "title": machine_name,
            "version": version_id,
            "procedure_version_id": version_id,
            "schema_version": "2.0",
            "objective": maintenance_obj,
            "maintenance_objective": maintenance_obj,
            "expected_final_state": expected_final_state,
            "status": status,
            "hse_approval_status": "approved" if str(status).upper() in {"PUBLISHED", "APPROVED"} else str(status).lower(),
            "created_by_hse": created_by_hse,
            "components": clean_components,
            "phases": clean_phases,
            "clarifications_required": clean_clarifications,
            "workflow_stages": enriched_workflow,
            "workflow_json": json.dumps(enriched_workflow, ensure_ascii=False),
            "anchors": [],
        }
        return _clean_null_values(payload)

    lockout = _sanitize_stages(raw_stages.get("lockout", []))
    restoration = _sanitize_stages(raw_stages.get("restoration", []))

    # Extraction sécurisée des ancres spatiales
    raw_anchors = raw_stages.get("anchors")
    if raw_anchors is None:
        raw_anchors = proc.get("anchors", {})

    anchors_dict = _sanitize_anchors(raw_anchors)

    # Construction de l'objet final conforme à LOTOProcedure (SmartLOTOClient.cs)
    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "created_by_hse": created_by_hse,
        "status": status,
        "procedure_version_id": version_id,
        "schema_version": str(raw_stages.get("schema_version", "1.0")),
        "maintenance_objective": str(raw_stages.get("maintenance_objective") or ""),
        "workflow_json": __import__("json").dumps(raw_stages, ensure_ascii=False),
        "workflow_stages": {
            "lockout": lockout,
            "restoration": restoration,
        },
        "anchors": anchors_dict,
    }


@router.get("/procedures")
async def list_procedures():
    """Retourne la liste des procédures approuvées sous forme de tableau JSON strict pour Unity."""
    if database.db is None:
        return []

    res = database.db.table("procedures").select("*").execute()
    data = res.data or []

    # Filtrer d'abord les procédures approuvées (APPROVED ou PUBLISHED, insensible à la casse)
    items_to_return = []
    for item in data:
        if str(item.get("status", "")).upper() != "PUBLISHED":
            continue
        stages = item.get("workflow_stages") or {}
        if isinstance(stages, str):
            try:
                import json
                stages = json.loads(stages)
            except (TypeError, ValueError):
                continue
        version_id = stages.get("_active_version_id") if isinstance(stages, dict) else None
        if not version_id:
            continue
        try:
            revision = database.db.table("procedure_versions").select("*").eq("id", version_id).execute()
        except Exception:
            continue
        if revision.data and revision.data[0].get("status") == "published":
            items_to_return.append(item)

    # Nettoyage strict pour désérialisation Unity (ProcedureListWrapper)
    cleaned = [
        {
            "machine_id": str(item.get("machine_id", "")),
            "machine_name": str(item.get("machine_name") or item.get("machine_id", "")),
        }
        for item in items_to_return
        if item.get("machine_id")
    ]
    return cleaned


@router.get("/procedures/{machine_id}")
async def get_procedure(machine_id: str, version_id: str | None = Query(default=None)):
    """Retourne le détail complet et normalisé de la procédure approuvée pour la machine."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    res = (
        database.db.table("procedures")
        .select("*")
        .eq("machine_id", machine_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune procédure trouvée pour la machine {machine_id}.",
        )

    procedure = res.data[0]
    if str(procedure.get("status", "")).upper() != "PUBLISHED":
        raise HTTPException(status_code=404, detail="Procedure not published for operator use.")

    stages = procedure.get("workflow_stages") or {}
    if isinstance(stages, str):
        try:
            import json
            stages = json.loads(stages)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="Invalid published workflow JSON.") from exc
    active_version_id = stages.get("_active_version_id") if isinstance(stages, dict) else None
    requested_version_id = version_id or active_version_id
    if not requested_version_id:
        raise HTTPException(status_code=409, detail="Published procedure has no active revision reference.")
    try:
        revision = database.db.table("procedure_versions").select("*").eq("id", requested_version_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Published revision registry is unavailable.") from exc
    if not revision.data or revision.data[0].get("procedure_id") != machine_id:
        raise HTTPException(status_code=404, detail="Procedure revision not found.")
    if revision.data[0].get("status") not in {"published", "superseded"}:
        raise HTTPException(status_code=409, detail="Requested procedure revision has not been published.")
    definition = revision.data[0].get("workflow_definition") or {}
    if isinstance(definition, str):
        try:
            import json
            definition = json.loads(definition)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="Published revision has invalid workflow JSON.") from exc
    procedure["workflow_stages"] = definition
    procedure["procedure_version_id"] = requested_version_id

    # Normalisation stricte pour Unity JsonUtility
    return sanitize_procedure_for_unity(procedure)


@router.post("/procedures/{machine_id}/anchors")
async def update_procedure_anchors(machine_id: str, data: AnchorsUpdate):
    """Enregistre les coordonnées spatiales 3D des organes calibrés depuis Unity."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    res = database.db.table("procedures").select("*").eq("machine_id", machine_id).execute()
    if not res.data:
        raise HTTPException(
            status_code=404,
            detail=f"Procédure non trouvée pour la machine {machine_id}.",
        )

    proc = res.data[0]
    if str(proc.get("status", "")).upper() == "PUBLISHED":
        raise HTTPException(status_code=409, detail="Published revisions are immutable; create a new draft to recalibrate anchors.")
    stages = proc.get("workflow_stages", {})
    if not isinstance(stages, dict):
        stages = {"lockout": [], "restoration": []}

    anchors_dict = {
        item.organ_name: {
            "pos_x": float(item.pos_x),
            "pos_y": float(item.pos_y),
            "pos_z": float(item.pos_z),
            "rot_x": float(item.rot_x),
            "rot_y": float(item.rot_y),
            "rot_z": float(item.rot_z),
        }
        for item in data.anchors_list
    }
    stages["anchors"] = anchors_dict

    database.db.table("procedures").update({"workflow_stages": stages}).eq("machine_id", machine_id).execute()
    return {"status": "success", "message": "Ancrages enregistrés avec succès."}
