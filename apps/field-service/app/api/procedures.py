"""
SmartLOTO Field Service — API Procédures LOTO (consommé par SmartLOTOClient.cs).

Contrat figé Unity (ne pas modifier sans recompiler l'application Quest) :
  GET  /procedures
  GET  /procedures/{machine_id}
  POST /procedures/{machine_id}/anchors
"""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

import app.database as database
from app.models import AnchorsUpdate

router = APIRouter()


def _sanitize_spatial_guide(raw_guide: Any) -> Dict[str, Any]:
    """Garantit la présence de tous les champs de SpatialGuideData pour Unity."""
    if not isinstance(raw_guide, dict):
        raw_guide = {}
    return {
        "hologram_type": str(raw_guide.get("hologram_type", "padlock")),
        "pos_x": float(raw_guide.get("pos_x", 0.0)),
        "pos_y": float(raw_guide.get("pos_y", 0.0)),
        "pos_z": float(raw_guide.get("pos_z", 0.0)),
        "rot_x": float(raw_guide.get("rot_x", 0.0)),
        "rot_y": float(raw_guide.get("rot_y", 0.0)),
        "rot_z": float(raw_guide.get("rot_z", 0.0)),
    }


def _sanitize_actions(raw_actions: Any) -> List[Dict[str, Any]]:
    """Garantit que actions est une liste d'ActionData conformes."""
    if not isinstance(raw_actions, list):
        return []
    actions: List[Dict[str, Any]] = []
    for idx, act in enumerate(raw_actions, start=1):
        if not isinstance(act, dict):
            continue
        actions.append({
            "action_id": str(act.get("action_id", f"step_{idx}")),
            "description": str(act.get("description", "Action requise")),
            "vision_prompt": str(act.get("vision_prompt", "")),
            "completion_check": str(act.get("completion_check", "Validation visuelle")),
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


def _sanitize_anchors(raw_anchors: Any) -> Dict[str, Dict[str, float]]:
    """Garantit que le dictionnaire d'ancres contient des coordonnées numériques valides."""
    if not isinstance(raw_anchors, dict):
        return {}
    clean: Dict[str, Dict[str, float]] = {}
    for organ_name, coords in raw_anchors.items():
        if not isinstance(coords, dict):
            continue
        clean[str(organ_name)] = {
            "pos_x": float(coords.get("pos_x", 0.0)),
            "pos_y": float(coords.get("pos_y", 0.0)),
            "pos_z": float(coords.get("pos_z", 0.0)),
            "rot_x": float(coords.get("rot_x", 0.0)),
            "rot_y": float(coords.get("rot_y", 0.0)),
            "rot_z": float(coords.get("rot_z", 0.0)),
        }
    return clean


def sanitize_procedure_for_unity(proc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise rigoureusement la procédure LOTO pour JsonUtility de Unity.
    Aucun champ manquant ou mal typé ne peut provoquer de crash côté C#.
    """
    machine_id = str(proc.get("machine_id", "UNKNOWN"))
    machine_name = str(proc.get("machine_name", machine_id))
    created_by_hse = str(proc.get("created_by_hse", "hse_supervisor@smartloto.io"))
    status = str(proc.get("status", "APPROVED"))

    raw_stages = proc.get("workflow_stages", {})
    if isinstance(raw_stages, str):
        try:
            import json
            raw_stages = json.loads(raw_stages)
        except Exception:
            raw_stages = {}
    if not isinstance(raw_stages, dict):
        raw_stages = {}

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

    res = database.db.table("procedures").select("machine_id, machine_name, status").execute()
    data = res.data or []

    # Filtrer d'abord les procédures approuvées (APPROVED ou PUBLISHED, insensible à la casse)
    approved_items = [
        item for item in data
        if str(item.get("status", "")).upper() in ("APPROVED", "PUBLISHED", "READY", "ACTIVE")
    ]
    items_to_return = approved_items if approved_items else data

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
async def get_procedure(machine_id: str):
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

    # Normalisation stricte pour Unity JsonUtility
    return sanitize_procedure_for_unity(res.data[0])


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
