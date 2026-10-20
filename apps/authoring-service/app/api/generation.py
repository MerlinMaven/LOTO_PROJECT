"""
SmartLOTO Authoring Service — API de Génération LLM Assistée.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import GenerationRunRequest, GenerationRunResponse
from app.services.generation_service import run_generation_pipeline
from app.services.procedure_service import update_procedure_draft

router = APIRouter()


@router.post("/generation/run", response_model=GenerationRunResponse)
async def run_generation(
    req: GenerationRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exécute la chaîne d'extraction et de génération structurée de procédure LOTO."""
    res = await run_generation_pipeline(req)

    # Si la procédure est publiable, on crée automatiquement le draft en base
    if res.is_publishable and res.workflow_definition:
        version = await update_procedure_draft(
            db,
            identifier=req.machine_id,
            workflow_definition=res.workflow_definition,
            actor_id=req.requested_by,
            notes=f"Généré automatiquement via LLM ({res.llm_provider})",
        )
        res.procedure_id = req.machine_id

    return res
