"""
SmartLOTO Field Service — API Interventions LOTO (consommé par SmartLOTOClient.cs).

Contrat figé Unity (ne pas modifier sans recompiler l'application Quest) :
  POST /interventions/start
  POST /interventions/validate-step
  POST /interventions/override-step
  POST /interventions/close
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from fastapi.routing import APIRouter

from app.config import (
    STORAGE_PATH_EVIDENCE,
    STORAGE_PATH_REPORTS,
    STORAGE_PATH_SIGNATURES,
)
import app.database as database
from app.models import (
    ActionOverride,
    ActionValidation,
    CloseIntervention,
    StartIntervention,
)
from app.services import pdf as pdf_service
from app.services import storage as storage_service
from app.services import vision as vision_service

router = APIRouter()


@router.post("/interventions/start")
async def start_intervention(data: StartIntervention):
    """Démarre une nouvelle intervention LOTO pour la machine spécifiée."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    p_res = (
        database.db.table("procedures")
        .select("*")
        .eq("machine_id", data.machine_id)
        .eq("status", "PUBLISHED")
        .execute()
    )
    if not p_res.data:
        raise HTTPException(status_code=404, detail="Aucune procédure publiée pour cet équipement.")

    procedure = p_res.data[0]
    stages = procedure.get("workflow_stages") or {}
    if isinstance(stages, str):
        try:
            import json
            stages = json.loads(stages)
        except (TypeError, ValueError):
            stages = {}
    version_id = stages.get("_active_version_id") if isinstance(stages, dict) else None
    if not version_id:
        raise HTTPException(status_code=409, detail="La procédure publiée ne référence aucune révision active.")
    try:
        version_res = database.db.table("procedure_versions").select("*").eq("id", version_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Le registre des révisions publiées est indisponible.") from exc
    if not version_res.data or version_res.data[0].get("status") != "published":
        raise HTTPException(status_code=409, detail="La révision active n'est pas publiée.")

    try:
        new_int = {
            "machine_id": data.machine_id,
            "procedure_version_id": version_id,
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
    """Valide une étape visuellement avec YOLO-World à partir de la capture AR."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    try:
        img, img_bytes = vision_service.decode_base64_image(data.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {exc}") from exc

    image_height, image_width = img.shape[:2]
    if image_width < 32 or image_height < 32:
        raise HTTPException(status_code=400, detail="L'image reçue est trop petite pour être exploitée.")

    try:
        candidate_detected, confidence = vision_service.run_detection(img, data.vision_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    filename = f"{STORAGE_PATH_EVIDENCE}/{data.intervention_id}_stage_{data.stage_id}_act_{data.action_id}.jpg"
    img_url = storage_service.upload_file(img_bytes, filename)
    print(f"[CAMERA] Image réelle reçue et enregistrée: {image_width}x{image_height} -> {img_url}")

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")

    intervention = int_res.data[0]
    logs = intervention.get("logs") or []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": f"Candidate object check: {data.vision_prompt}",
        "type": "visual_candidate_detection",
        "success": False,
        "candidate_detected": candidate_detected,
        "image_url": img_url,
        "details": (f"Candidate detected (score {confidence:.2f}); state not verified, operator confirmation required." if confidence is not None else "No candidate detected; physical absence is not established."),
    })

    database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()

    return {
        "verified": False,
        "candidate_detected": candidate_detected,
        "message": "Candidate detection recorded; equipment state remains unverified.",
        "image_url": img_url,
        "image_width": image_width,
        "image_height": image_height,
    }



@router.post("/interventions/override-step")
async def override_step(data: ActionOverride):
    """Valide manuellement une étape en cas de mode dégradé avec photo de preuve."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")
    if not data.reason.strip():
        raise HTTPException(status_code=422, detail="Une justification opérateur est requise.")

    try:
        image, img_bytes = vision_service.decode_base64_image(data.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Image base64 invalide : {exc}") from exc

    image_height, image_width = image.shape[:2]
    if image_width < 32 or image_height < 32:
        raise HTTPException(status_code=400, detail="L'image reçue est trop petite pour être exploitable.")

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")
    intervention = int_res.data[0]
    if intervention.get("status") != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Cette intervention n'est plus en cours.")
    pinned_version_id = intervention.get("procedure_version_id")
    if pinned_version_id:
        revision_res = database.db.table("procedure_versions").select("*").eq("id", pinned_version_id).execute()
        if not revision_res.data:
            raise HTTPException(status_code=409, detail="La révision épinglée de l'intervention est introuvable.")
        revision = revision_res.data[0]
        workflow = revision.get("workflow_definition") or {}
        if isinstance(workflow, str):
            try:
                workflow = json.loads(workflow)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail="La révision épinglée contient un JSON invalide.") from exc
        if workflow.get("schema_version") == "2.0":
            expected_method = None
            for phase in workflow.get("phases", []):
                for stage in phase.get("stages", []):
                    for step in stage.get("steps", []):
                        if step.get("step_id") == data.action_id:
                            expected_method = (step.get("verification") or {}).get("method")
                            break
            # Support des méthodes avec repli gracieux Unity (Validation Humaine / Bouton Virtuel)
            supported_methods = {"visual_observation", "human_confirmation", "measurement", "sensor_signal"}
            if expected_method not in supported_methods:
                raise HTTPException(status_code=422, detail="Cette méthode n'est pas disponible pour confirmation Unity.")
            allowed_inputs = {expected_method, "human_confirmation", "virtual_button"}
            if data.verification_method not in allowed_inputs:
                raise HTTPException(status_code=409, detail="La méthode de vérification ne correspond pas à la révision épinglée.")

    filename = (
        f"{STORAGE_PATH_EVIDENCE}/{data.intervention_id}_stage_{data.stage_id}"
        f"_act_{data.action_id}_override.jpg"
    )
    img_url = storage_service.upload_file(img_bytes, filename)
    print(f"[CAMERA] Image de dérogation enregistrée: {image_width}x{image_height} -> {img_url}")

    logs = intervention.get("logs") or []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "stage_id": data.stage_id,
        "action_id": data.action_id,
        "action_description": "Confirmation opérateur avec preuve",
        "type": "operator_confirmation",
        "verification_method": data.verification_method or "legacy_manual_confirmation",
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
    """Clôture l'intervention, enregistre la signature opérateur et compile le rapport d'audit PDF."""
    if database.db is None:
        raise HTTPException(status_code=500, detail="Base de données indisponible.")

    int_res = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute()
    if not int_res.data:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")

    intervention = int_res.data[0]
    machine_id = intervention.get("machine_id")

    p_res = database.db.table("procedures").select("*").eq("machine_id", machine_id).execute()
    machine_name = p_res.data[0].get("machine_name") if p_res.data else "Machine Inconnue"

    # Enregistrement de la signature
    sig_bytes: bytes | None = None
    sig_url = ""
    try:
        _, sig_bytes = vision_service.decode_base64_image(data.signature_base64)
        sig_filename = f"{STORAGE_PATH_SIGNATURES}/{data.intervention_id}_signature.png"
        sig_url = storage_service.upload_file(sig_bytes, sig_filename, content_type="image/png")
    except Exception as exc:
        print(f"[WARN] Erreur de décodage signature : {exc}")

    # Génération et sauvegarde du PDF
    pdf_bytes = pdf_service.generate_audit_report(intervention, machine_name, sig_bytes)
    pdf_filename = f"{STORAGE_PATH_REPORTS}/Audit_Report_{data.intervention_id}.pdf"
    pdf_url = storage_service.upload_file(pdf_bytes, pdf_filename, content_type="application/pdf")

    # Clôture du statut
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
