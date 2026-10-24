"""
SmartLOTO Authoring Service — Point d'assemblage FastAPI.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import CORS_ORIGINS
from app.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialisation de la base de données
    await init_db()
    # Démarrage du worker de traitement documentaire asynchrone
    from app.services import document_generation_service
    await document_generation_service.start_worker()
    yield
    # Arrêt propre du worker
    await document_generation_service.stop_worker()
    # Fermeture propre de la base de données
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SmartLOTO Authoring Service API",
        description="Service de génération LLM, validation HSE et publication des procédures LOTO",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    app.include_router(api_router)

    @app.options("/{full_path:path}", include_in_schema=False)
    async def preflight_options_handler(full_path: str):
        from fastapi.responses import Response
        res = Response()
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        res.headers["Access-Control-Allow-Headers"] = "*"
        return res

    @app.get("/health", tags=["Health"])
    @app.get("/", tags=["Health"])
    async def health_check():
        return {
            "status": "online",
            "service": "SmartLOTO Authoring Service",
            "version": "2.0.0",
        }

    return app


app = create_app()
