"""
SmartLOTO Authoring Service — Routeur Central.
Agrège les routes sous /api/v1 et /v1 pour compatibilité totale avec le dashboard React.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import audit, generation, interventions, procedures

v1_router = APIRouter()

v1_router.include_router(procedures.router, prefix="/procedures", tags=["Procédures LOTO"])
v1_router.include_router(generation.router, tags=["Génération LLM"])
v1_router.include_router(interventions.router, prefix="/interventions", tags=["Interventions"])
v1_router.include_router(audit.router, prefix="/audit", tags=["Piste d'Audit"])

# Routeur racine qui monte les routes avec /api/v1, /v1 et directement à la racine pour compatibilité totale
api_router = APIRouter()
api_router.include_router(v1_router, prefix="/api/v1")
api_router.include_router(v1_router, prefix="/v1")
api_router.include_router(v1_router)
