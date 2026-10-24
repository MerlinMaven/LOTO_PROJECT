"""
SmartLOTO Authoring Service Ã¢â‚¬â€ Session et Moteur de Base de DonnÃƒÂ©es (SQLAlchemy Async).
"""

from __future__ import annotations

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import DATABASE_URL, SQLITE_DB_PATH

Base = declarative_base()

# Configuration du moteur
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs = {"echo": False}
if not _is_sqlite:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """DÃƒÂ©pendance FastAPI fournissant une session SQLAlchemy asynchrone."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create missing tables without inserting or rewriting procedure data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if _is_sqlite:
            columns = await conn.exec_driver_sql("PRAGMA table_info(interventions)")
            if "procedure_version_id" not in {row[1] for row in columns.fetchall()}:
                await conn.exec_driver_sql(
                    "ALTER TABLE interventions ADD COLUMN procedure_version_id VARCHAR(36)"
                )
    from app.services.procedure_service import restore_published_revision_pointers
    async with AsyncSessionLocal() as session:
        repaired = await restore_published_revision_pointers(session)
        await session.commit()
    print(f"[OK] Database active: {SQLITE_DB_PATH}; restored {repaired} audited publication pointer(s), inserted no demonstration procedure.")

async def close_db() -> None:
    """Ferme les connexions lors de l'arrÃƒÂªt."""
    await engine.dispose()
