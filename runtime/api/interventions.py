"""
Interventions API — LOTO runtime lifecycle endpoints.

Frozen contract (do NOT change without recompiling the Quest app):
  POST /interventions/start
  POST /interventions/validate-step
  POST /interventions/override-step
  POST /interventions/close
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from fastapi.routing import APIRouter

import runtime.database as database
from runtime.config import STORAGE_PATH_EVIDENCE, STORAGE_PATH_REPORTS, STORAGE_PATH_SIGNATURES
from runtime.models import ActionOverride, ActionValidation, CloseIntervention, StartIntervention
from runtime.services import pdf as pdf_service
from runtime.services import storage as storage_service
from runtime.services import vision as vision_service

router = APIRouter()


@router.post("/interventions/start")
async def start_intervention(data: StartIntervention):
    """Start a new LOTO intervention for the given machine."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    p_res = (
        database.db.table("procedures")
        .select("*")
        .eq("machine_id", data.machine_id)
        .eq("status", "APPROVED")
        .execute()
    )
    if not p_res.data:
        raise HTTPException(status_code=404, detail="Procédure non trouvée ou non approuvée.")

    try:
        new_int = {
            "machine_id": data.machine_id,
            "operator_name": data.operator_name,
            "status": "IN_PROGRESS",
            "current_stage_id": 1,
            "logs": [],
        }
        res = database.db.table("interventions").insert(new_int).execute()
        return {"status": "success", "intervention": res.data[0]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/interventions/validate-step")
async def validate_step(data: ActionValidation):
    """Validate a LOTO step via YOLO-World zero-shot visual detection."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    try:
        img, img_bytes = vision_service.decode_base64_image(data.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {exc}") from exc

    is_detected, confidence = vision_service.run_detection(img, data.vision_prompt)

    filename = f"{STORAGE_PATH_EVIDENCE}/{data.intervention_id}_stage_{data.stage_id}_act_{data.action_id}.jpg"
    img_url = storage_service.upload_file(img_bytes, filename)

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")

    intervention = int_res.data[0]
    logs = intervention.get("logs") or []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": f"Vérification de '{data.vision_prompt}'",
        "type": "vision_detection",
        "success": is_detected,
        "image_url": img_url,
        "details": f"Confiance détection : {confidence:.2f}" if confidence is not None else "Non détecté",
    })

    database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()

    return {
        "verified": is_detected,
        "message": (
            "Proxy de condamnation détecté avec succès"
            if is_detected
            else "Objet non détecté ou visuel non conforme"
        ),
        "image_url": img_url,
    }


@router.post("/interventions/override-step")
async def override_step(data: ActionOverride):
    """Manually validate a step with photographic evidence (degraded-mode override)."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    try:
        _, img_bytes = vision_service.decode_base64_image(data.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {exc}") from exc

    filename = (
        f"{STORAGE_PATH_EVIDENCE}/{data.intervention_id}_stage_{data.stage_id}"
        f"_act_{data.action_id}_override.jpg"
    )
    img_url = storage_service.upload_file(img_bytes, filename)

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")

    intervention = int_res.data[0]
    logs = intervention.get("logs") or []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": "Dérogation manuelle par l'opérateur",
        "type": "manual_override_with_evidence",
        "success": True,
        "image_url": img_url,
        "details": f"Raison de la dérogation : {data.reason}",
    })

    database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()

    return {
        "verified": True,
        "message": "Dérogation manuelle enregistrée avec succès.",
        "image_url": img_url,
    }


@router.post("/interventions/close")
async def close_intervention(data: CloseIntervention):
    """Close an intervention, upload the digital signature, and generate the PDF audit report."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")

    intervention = int_res.data[0]
    machine_id = intervention.get("machine_id")

    p_res = database.db.table("procedures").select("*").eq("machine_id", machine_id).execute()
    machine_name = p_res.data[0].get("machine_name") if p_res.data else "Machine Inconnue"

    # Upload operator signature
    sig_bytes: bytes | None = None
    sig_url = ""
    try:
        _, sig_bytes = vision_service.decode_base64_image(data.signature_base64)
        sig_filename = f"{STORAGE_PATH_SIGNATURES}/{data.intervention_id}_signature.png"
        sig_url = storage_service.upload_file(sig_bytes, sig_filename, content_type="image/png")
    except Exception as exc:
        print(f"Erreur de décodage de la signature : {exc}")

    # Generate and upload PDF audit report
    pdf_bytes = pdf_service.generate_audit_report(intervention, machine_name, sig_bytes)
    pdf_filename = f"{STORAGE_PATH_REPORTS}/Audit_Report_{data.intervention_id}.pdf"
    pdf_url = storage_service.upload_file(pdf_bytes, pdf_filename, content_type="application/pdf")

    # Mark intervention as COMPLETED
    database.db.table("interventions").update({
        "status": "COMPLETED",
        "signature_url": sig_url,
        "pdf_report_url": pdf_url,
        "completed_at": datetime.now().isoformat(),
    }).eq("id", data.intervention_id).execute()

    return {
        "status": "success",
        "message": "Intervention clôturée avec succès et rapport PDF généré.",
        "pdf_report_url": pdf_url,
    }
