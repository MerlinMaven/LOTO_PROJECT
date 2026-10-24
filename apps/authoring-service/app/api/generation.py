"""
SmartLOTO Authoring Service — API de Génération Asynchrone Persistante.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.services import document_generation_service

router = APIRouter()


@router.post("/generation/documents", status_code=202)
async def submit_document(
    file: UploadFile = File(...),
    x_user_id: str = Header("hse_user@smartloto.io"),
    x_idempotency_key: Optional[str] = Header(None),
):
    """Reçoit un fichier PDF et initialise une tâche de traitement asynchrone persistante."""
    if file.content_type not in {"application/pdf", "application/octet-stream"} and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Importez un fichier PDF.")
    actor_id = x_user_id or "hse_user@smartloto.io"
    return await document_generation_service.accept_pdf(file, actor_id, x_idempotency_key)


@router.get("/generation/jobs")
async def list_generation_jobs(
    limit: int = 50,
    x_user_id: str = Header("hse_user@smartloto.io"),
):
    """Liste l'historique des tâches de génération de l'utilisateur."""
    actor_id = x_user_id or "hse_user@smartloto.io"
    return await document_generation_service.list_jobs(actor_id, limit=limit)


@router.get("/generation/jobs/{job_id}")
async def read_generation_job(
    job_id: str,
    x_user_id: str = Header("hse_user@smartloto.io"),
):
    """Consulte l'état, l'étape actuelle et le résultat d'une tâche de génération."""
    actor_id = x_user_id or "hse_user@smartloto.io"
    job = await document_generation_service.get_job(job_id, actor_id)
    if not job:
        existing_any = await document_generation_service.find_job_any_owner(job_id)
        if existing_any:
            raise HTTPException(status_code=403, detail="Accès non autorisé à cette tâche.")
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    return job


@router.post("/generation/jobs/{job_id}/retry", status_code=202)
async def retry_generation_job(
    job_id: str,
    x_user_id: str = Header("hse_user@smartloto.io"),
    x_idempotency_key: Optional[str] = Header(None),
):
    """Relance l'analyse d'une tâche en échec à partir du PDF conservé côté serveur."""
    actor_id = x_user_id or "hse_user@smartloto.io"
    return await document_generation_service.retry_job(job_id, actor_id, x_idempotency_key)


@router.get("/generation/documents/{document_id}")
async def download_source_document(document_id: str):
    """Télécharge le document PDF source conservé sur le serveur."""
    path = document_generation_service.find_document_path(document_id)
    if not path:
        raise HTTPException(status_code=404, detail="Document source introuvable.")
    return FileResponse(path, media_type="application/pdf", filename=f"{document_id}.pdf")


@router.post("/generation/run")
async def run_generation():
    """Ancienne route de génération texte désactivée."""
    raise HTTPException(status_code=410, detail="Cette route texte est désactivée. Importez un PDF via /generation/documents.")
