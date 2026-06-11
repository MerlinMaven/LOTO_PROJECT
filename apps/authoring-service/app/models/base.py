"""
SQLAlchemy declarative base and shared mixins.

All models inherit from Base.
TimestampMixin adds created_at / updated_at automatically.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Application-wide SQLAlchemy declarative base."""
    metadata = MetaData(schema="authoring")


class TimestampMixin:
    """
    Adds created_at and updated_at columns.
    updated_at is refreshed automatically on every UPDATE via server_onupdate.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def new_uuid() -> uuid.UUID:
    """Helper used as the Python-side default for UUID primary keys."""
    return uuid.uuid4()
