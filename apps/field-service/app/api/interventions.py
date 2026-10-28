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
import hashlib
import httpx
from uuid import uuid4
from datetime import datetime, timezone

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
    PreviewValidation,
    HumanConfirmation,
    TestConfirmation,
    GuidanceLocalization,
)
from app.services import pdf as pdf_service
from app.services import storage as storage_service
from app.services import vision as vision_service
from app.services import step_vision
from app.services import step_guidance
from app.services.signatures import operator_signature, hse_signature_for_intervention
from app.services.workflow import verification_context

router = APIRouter()


@router.post("/guidance/locate-step")
async def locate_step(data: GuidanceLocalization):
    """Locate a step's components without evaluating, saving or advancing it."""
    if data.test_mode:
        if database.db is None:
            raise HTTPException(status_code=503, detail="Base de données indisponible.")
        rows = database.db.table("procedure_versions").select("*").eq("id", data.version_id).execute().data
        if (not rows or rows[0].get("procedure_id") != data.machine_id
                or rows[0].get("status") not in {"published", "superseded", "draft_pending_review", "approved"}):
            raise HTTPException(status_code=409, detail="Révision de guidage introuvable.")
        workflow = rows[0]["workflow_definition"]
        try:
            if isinstance(workflow, str):
                workflow = json.loads(workflow)
            context = verification_context(workflow, data.action_id, data.stage_id, data.stage_code)
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="Contexte de guidage invalide.") from exc
    else:
        intervention, context = _intervention_context(data)
        if (intervention["machine_id"] != data.machine_id
                or context["procedure_version_id"] != data.version_id):
            raise HTTPException(status_code=409, detail="Le guidage ne correspond pas à la révision de l'intervention.")
    image, content = _camera_image(data.image_base64)
    try:
        targets = await step_guidance.locate_components(image, context)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(status_code=503, detail="Localisation IA indisponible.") from exc
    return {"guidance_only": True, "verified": False, "test_mode": data.test_mode,
            "request_id": data.request_id, "action_id": data.action_id,
            "procedure_version_id": data.version_id, "image_sha256": hashlib.sha256(content).hexdigest(),
            "image_width": image.shape[1], "image_height": image.shape[0], "targets": targets}


@router.post("/tests/verify-step")
async def preview_step(data: PreviewValidation):
    """Historical image test: production evaluator, no intervention, evidence or audit writes."""
    if database.db is None:
        raise HTTPException(status_code=503, detail="Base de données indisponible.")
    rows = database.db.table("procedure_versions").select("*").eq("id", data.version_id).execute().data
    if (not rows or rows[0].get("procedure_id") != data.machine_id
            or rows[0].get("status") not in {"published", "superseded", "draft_pending_review", "approved"}):
        raise HTTPException(status_code=409, detail="Révision de test introuvable pour cet équipement.")
    workflow = rows[0]["workflow_definition"]
    if isinstance(workflow, str):
        workflow = json.loads(workflow)
    try:
        context = verification_context(workflow, data.action_id, data.stage_id, data.stage_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    image, content = _camera_image(data.image_base64)
    result = await step_vision.evaluate_step(image, context)
    return {**result, "test_mode": True, "revision_status": rows[0]["status"], "request_id": data.request_id, "action_id": data.action_id,
            "procedure_version_id": data.version_id, "image_sha256": hashlib.sha256(content).hexdigest(),
            "image_width": image.shape[1], "image_height": image.shape[0]}


def _human_result(context, data):
    if context["verification"].get("method") != "human_confirmation":
        raise HTTPException(status_code=409, detail="Cette étape requiert une autre méthode de validation.")
    if not data.confirmed:
        raise HTTPException(status_code=422, detail="Confirmez explicitement la réalisation de l'opération.")
    return {"verified": True, "outcome": "human_confirmed", "evaluation_mode": "human_confirmation",
            "message": "Opération confirmée par l'opérateur.", "observed_state": "Attestation humaine ; aucune inférence visuelle.",
            "request_id": data.request_id, "action_id": data.action_id, "targets": [],
            "execution_phase": context["execution_phase"], "validation_method": "human_confirmation"}


@router.post("/interventions/confirm-step")
async def confirm_step(data: HumanConfirmation):
    intervention, context = _intervention_context(data)
    result = _human_result(context, data)
    logs = intervention.get("logs") or []
    # Retransmission of the same attestation must not create a second audit event.
    if not any(log.get("request_id") == data.request_id and log.get("type") == "human_confirmation" for log in logs):
        logs.append({"timestamp": datetime.now().isoformat(), "stage_id": data.stage_id,
            "stage_code": context["stage_code"], "action_id": data.action_id, "request_id": data.request_id,
            "action_description": context["instruction"], "type": "human_confirmation", "success": True,
            "execution_phase": context["execution_phase"], "verification_method": "human_confirmation",
            "operator_name": intervention.get("operator_name", ""),
            "details": data.statement.strip() or "L'opérateur confirme avoir réalisé l'opération.",
            "verification_context": context})
        database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()
    return {**result, "procedure_version_id": context["procedure_version_id"]}


@router.post("/tests/confirm-step")
async def test_confirm_step(data: TestConfirmation):
    if database.db is None:
        raise HTTPException(status_code=503, detail="Base de données indisponible.")
    rows = database.db.table("procedure_versions").select("*").eq("id", data.version_id).execute().data
    if not rows or rows[0].get("procedure_id") != data.machine_id:
        raise HTTPException(status_code=409, detail="Révision de test introuvable.")
    workflow = rows[0]["workflow_definition"]
    if isinstance(workflow, str): workflow = json.loads(workflow)
    try: context = verification_context(workflow, data.action_id, data.stage_id, data.stage_code)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**_human_result(context, data), "test_mode": True, "procedure_version_id": data.version_id,
            "revision_status": rows[0]["status"]}


def _intervention_context(data):
    if database.db is None:
        raise HTTPException(status_code=503, detail="Base de données indisponible.")
    rows = database.db.table("interventions").select("*").eq("id", data.intervention_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Intervention non trouvée.")
    intervention = rows[0]
    if intervention.get("status") != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Cette intervention n'est plus en cours.")
    revisions = database.db.table("procedure_versions").select("*").eq("id", intervention.get("procedure_version_id")).execute().data
    if not revisions or revisions[0].get("procedure_id") != intervention["machine_id"]:
        raise HTTPException(status_code=409, detail="Révision épinglée absente ou liée à un autre équipement.")
    revision = revisions[0]
    if revision.get("status") not in {"published", "superseded"}:
        raise HTTPException(status_code=409, detail="La révision épinglée n'a pas été publiée.")
    workflow = revision.get("workflow_definition") or {}
    try:
        if isinstance(workflow, str):
            workflow = json.loads(workflow)
        context = verification_context(workflow, data.action_id, data.stage_id, data.stage_code)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    context["procedure_version_id"] = revision["id"]
    return intervention, context


def _camera_image(encoded):
    try:
        image, content = vision_service.decode_base64_image(encoded)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=f"Image invalide : {exc}") from exc
    if min(image.shape[:2]) < 32:
        raise HTTPException(status_code=400, detail="Image trop petite pour être exploitée.")
    return image, content


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
    if (not version_res.data or version_res.data[0].get("status") != "published"
            or version_res.data[0].get("procedure_id") != data.machine_id):
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
    """Evaluate the camera frame using only the intervention's published revision."""
    _, context = _intervention_context(data)
    image, content = _camera_image(data.image_base64)
    result = await step_vision.evaluate_step(image, context)
    # Re-read after inference so a closed intervention cannot receive a late success.
    intervention, _ = _intervention_context(data)
    filename = f"{STORAGE_PATH_EVIDENCE}/{uuid4().hex}.jpg"
    image_url = storage_service.upload_file(content, filename)
    logs = intervention.get("logs") or []
    logs.append({
        "timestamp": datetime.now().isoformat(), "stage_id": data.stage_id,
        "stage_code": context["stage_code"], "action_id": data.action_id,
        "action_description": context["instruction"], "type": "contextual_vision",
        "success": result["verified"], "image_url": image_url,
        "details": result["message"], "verification_context": context,
        "execution_phase": context["execution_phase"], "verification_method": context["verification"].get("method"),
        "observation": result,
    })
    database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()
    return {**result, "request_id": data.request_id, "action_id": data.action_id,
            "procedure_version_id": context["procedure_version_id"], "image_sha256": hashlib.sha256(content).hexdigest(),
            "image_url": image_url, "image_width": image.shape[1], "image_height": image.shape[0]}


@router.post("/interventions/override-step")
async def override_step(data: ActionOverride):
    """Explicit, photographed exception to the published verification method."""
    intervention, context = _intervention_context(data)
    if not data.reason.strip():
        raise HTTPException(status_code=422, detail="Un motif de derogation est obligatoire.")
    _, content = _camera_image(data.image_base64)
    image_url = storage_service.upload_file(content, f"{STORAGE_PATH_EVIDENCE}/{uuid4().hex}_override.jpg")
    logs = intervention.get("logs") or []
    logs.append({
        "timestamp": datetime.now().isoformat(), "stage_id": data.stage_id,
        "stage_code": context["stage_code"], "action_id": data.action_id,
        "action_description": context["instruction"], "type": "operator_override",
        "verification_method": context["verification"].get("method", ""),
        "success": True, "image_url": image_url,
        "details": data.reason.strip(), "verification_context": context,
    })
    database.db.table("interventions").update({"logs": logs}).eq("id", data.intervention_id).execute()
    return {"verified": True, "message": "Derogation manuelle enregistree avec sa preuve.", "image_url": image_url}


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

    completed_at = datetime.now(timezone.utc).isoformat()
    signature_record, sig_bytes = operator_signature(intervention, completed_at, sig_bytes)
    if not sig_url:
        sig_filename = f"{STORAGE_PATH_SIGNATURES}/{data.intervention_id}_signature.png"
        sig_url = storage_service.upload_file(sig_bytes, sig_filename, content_type="image/png")
    signature_record["image_url"] = sig_url
    intervention["completed_at"] = completed_at
    intervention["operator_signature"] = signature_record
    intervention["hse_signature"] = hse_signature_for_intervention(database.db, intervention)
    logs = [log for log in (intervention.get("logs") or []) if log.get("type") != "operator_signature"]
    logs.append({"type": "operator_signature", "timestamp": completed_at, "signature": signature_record,
                 "success": True, "action_description": "Signature et clôture de l’intervention"})
    intervention["logs"] = logs

    # Génération et sauvegarde du PDF
    pdf_bytes = pdf_service.generate_audit_report(intervention, machine_name, sig_bytes)
    pdf_filename = f"{STORAGE_PATH_REPORTS}/Audit_Report_{data.intervention_id}.pdf"
    pdf_url = storage_service.upload_file(pdf_bytes, pdf_filename, content_type="application/pdf")

    # Clôture du statut
    database.db.table("interventions").update({
        "status": "COMPLETED",
        "signature_url": sig_url,
        "pdf_report_url": pdf_url,
        "completed_at": completed_at,
        "logs": logs,
    }).eq("id", data.intervention_id).execute()

    return {
        "status": "success",
        "message": "Intervention clôturée avec succès et rapport PDF généré.",
        "pdf_report_url": pdf_url,
    }
