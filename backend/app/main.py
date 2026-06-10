"""
SmartLOTO FastAPI application entry point.

Wires together:
  - FastAPI application instance
  - CORS middleware
  - All v1 API routers
  - Domain exception → HTTP error handlers
  - Structured logging (JSON in production, colored in dev)
  - Async engine lifecycle (startup pool init, shutdown connection drain)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import close_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Startup: configure structured logging, warm the connection pool.
    Shutdown: drain open DB connections cleanly.
    """
    settings = get_settings()

    # Configure structlog before the first request arrives.
    configure_logging()

    logger.info(
        "smartloto_startup",
        environment=settings.APP_ENV,
        log_level=settings.LOG_LEVEL,
    )

    yield  # Application is running

    # Drain the async engine connection pool on shutdown.
    await close_engine()
    logger.info("smartloto_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SmartLOTO API",
        description=(
            "Cyber-physical LOTO (Lockout-Tagout) safety platform. "
            "Manages procedure lifecycle, operator interventions, "
            "and tamper-evident audit trails for industrial maintenance compliance."
        ),
        version="2.0.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Domain exception → HTTP error mapping ─────────────────────────────────
    register_error_handlers(app)

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health_check() -> dict:
        return {"status": "ok", "service": "smartloto-api", "version": "2.0.0"}

    return app


app = create_app()
