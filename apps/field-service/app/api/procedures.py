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

    if not raw_stages and proc.get("phases"):
        raw_stages = proc
    if raw_stages.get("schema_version") == "2.0" or raw_stages.get("phases"):
        import json
        from app.services.workflow import normalize_workflow
        if not isinstance(raw_stages.get("phases"), list):
            raise HTTPException(status_code=409, detail="Canonical workflow has no valid phases array.")
        workflow = normalize_workflow(raw_stages)
        objective = workflow.get("maintenance_objective") or proc.get("maintenance_objective") or proc.get("objective") or ""
        return {
            "procedure_id": machine_id, "machine_id": machine_id,
            "machine_name": machine_name, "title": machine_name,
            "version": version_id, "procedure_version_id": version_id,
            "schema_version": "2.0", "status": status,
            "created_by_hse": created_by_hse,
            "hse_approval_status": "approved" if status.upper() in {"PUBLISHED", "APPROVED"} else status.lower(),
            "objective": objective, "maintenance_objective": objective,
            "expected_final_state": workflow.get("expected_final_state", ""),
            "components": workflow.get("components", []),
            "phases": workflow.get("phases", []),
            "clarifications_required": workflow.get("clarifications_required", []),
            "workflow_stages": workflow,
            "workflow_json": json.dumps(raw_stages, ensure_ascii=False),
            "anchors": _sanitize_anchors(raw_stages.get("anchors") or proc.get("anchors") or {}),
        }

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
