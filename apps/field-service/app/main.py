"""
SmartLOTO Field Service — Point d'assemblage FastAPI.
Assure l'exposition des routes AR/MR Unity, le service des fichiers statiques
(photos de preuves et rapports PDF d'audit), la gestion CORS totale et l'auto-seed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import json
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.interventions import router as interventions_router
from app.api.procedures import router as procedures_router
from app.config import STORAGE_DIR
import app.database as database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Exécuté au démarrage : initialise la base et assure l'auto-seed de PUMP-001."""
    database.init_db()
    yield


app = FastAPI(
    title="SmartLOTO Field Service API",
    description="Backend d'assistance cognitive AR/MR pour la consignation industrielle (LOTO)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS permissif absolu pour dev local, Unity (HTTP) et Dashboard React (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Service des fichiers statiques locaux (preuves photos, signatures, PDF d'audit)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# Inclusion des routes Unity
app.include_router(procedures_router)
app.include_router(interventions_router)


@app.options("/{full_path:path}", include_in_schema=False)
async def preflight_options_handler(full_path: str):
    from fastapi.responses import Response
    res = Response()
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    res.headers["Access-Control-Allow-Headers"] = "*"
    return res


@app.get("/")
@app.get("/health")
def health_check():
    from app import config
    from app.services.step_vision import Observation, SYSTEM_PROMPT
    schema = json.dumps(Observation.model_json_schema(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "status": "online",
        "service": "SmartLOTO Field Service",
        "timestamp": datetime.now().isoformat(),
        "vision": {"provider": config.FIELD_VISION_PROVIDER, "model": config.FIELD_VISION_MODEL,
                   "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                   "observation_schema_sha256": hashlib.sha256(schema.encode()).hexdigest()},
    }
