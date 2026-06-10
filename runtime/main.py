"""
SmartLOTO Field Service — FastAPI application factory.

This module is the single place where middleware, routers, and startup
events are assembled.  ``backend.py`` imports ``app`` from here so that
``uvicorn backend:app`` continues to work without change.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runtime.api.interventions import router as interventions_router
from runtime.api.procedures import router as procedures_router
from runtime.config import CORS_ORIGINS

app = FastAPI(
    title="SmartLOTO API",
    description="Backend d'assistance cognitive AR/MR pour la consignation industrielle (LOTO)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(procedures_router)
app.include_router(interventions_router)


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "SmartLOTO API",
        "timestamp": datetime.now().isoformat(),
    }
