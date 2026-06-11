"""
Async SQLAlchemy engine and session factory.

A single AsyncEngine is created once at startup and shared for the process lifetime.
Sessions are created per-request via the FastAPI dependency in api/deps.py.

Design notes:
- asyncpg is the async driver for PostgreSQL (fastest available).
- NullPool is used instead of the default pool when Supabase is behind a PgBouncer
  proxy in transaction mode (PgBouncer manages its own connection pool; SQLAlchemy
  pooling on top causes "prepared statement already exists" errors with asyncpg).
  Set SUPABASE_TRANSACTION_MODE=true in .env to activate NullPool.
- The synchronous engine is available exclusively for Alembic migrations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# ── Async engine (runtime) ────────────────────────────────────────────────────
# Supabase uses PgBouncer in transaction mode — NullPool avoids "prepared
# statement already exists" errors when the pooler is in front of asyncpg.
_use_nullpool = "pooler.supabase.com" in settings.DATABASE_URL

_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
    pool_pre_ping=True,
    **({
        "poolclass": NullPool,
        # PgBouncer transaction mode does not support prepared statements
        "connect_args": {"statement_cache_size": 0},
    } if _use_nullpool else {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
    }),
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,   # attributes remain accessible after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a request-scoped DB session.

    Usage in a router:
        @router.get("/...")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """Dispose the engine — call on app shutdown to release all connections."""
    await _engine.dispose()
