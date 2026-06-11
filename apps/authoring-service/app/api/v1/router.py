"""Central v1 API router. Aggregates all domain routers."""

from fastapi import APIRouter

from app.api.v1 import machines, procedures, interventions, audit, generation

router = APIRouter(prefix="/api/v1")

router.include_router(machines.router, prefix="/machines", tags=["Machines"])
router.include_router(procedures.router, prefix="/procedures", tags=["Procedures"])
router.include_router(interventions.router, prefix="/interventions", tags=["Interventions"])
router.include_router(audit.router, prefix="/audit", tags=["Audit"])
router.include_router(generation.router, tags=["Generation"])
