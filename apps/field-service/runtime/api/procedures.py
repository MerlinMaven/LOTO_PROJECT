"""
Procedures API — Unity-facing read endpoints and anchor calibration.

Frozen contract (do NOT change without recompiling the Quest app):
  GET  /procedures
  GET  /procedures/{machine_id}
  POST /procedures/{machine_id}/anchors
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import runtime.database as database
from runtime.models import AnchorsUpdate

router = APIRouter()


@router.get("/procedures")
async def list_procedures():
    """Return all APPROVED procedures (machine_id + machine_name only)."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    res = database.db.table("procedures").select("machine_id, machine_name").eq("status", "APPROVED").execute()
    return res.data


@router.get("/procedures/{machine_id}")
async def get_procedure(machine_id: str):
    """Return a single APPROVED procedure by machine_id."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    res = (
        database.db.table("procedures")
        .select("*")
        .eq("machine_id", machine_id)
        .eq("status", "APPROVED")
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune procédure approuvée trouvée pour la machine {machine_id}.",
        )
    return res.data[0]


@router.post("/procedures/{machine_id}/anchors")
async def update_procedure_anchors(machine_id: str, data: AnchorsUpdate):
    """Persist calibrated spatial anchor positions for a procedure."""
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
            "pos_x": item.pos_x,
            "pos_y": item.pos_y,
            "pos_z": item.pos_z,
            "rot_x": item.rot_x,
            "rot_y": item.rot_y,
            "rot_z": item.rot_z,
        }
        for item in data.anchors_list
    }
    stages["anchors"] = anchors_dict

    database.db.table("procedures").update({"workflow_stages": stages}).eq("machine_id", machine_id).execute()
    return {"status": "success", "message": "Ancrages enregistrés avec succès."}
