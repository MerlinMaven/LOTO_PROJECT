"""
Shared schema primitives used across all domain schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AppBaseModel(BaseModel):
    """Base for all Pydantic schemas. ORM mode enabled globally."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedResponse(AppBaseModel, Generic[T]):
    """Standard paginated list wrapper returned by all list endpoints."""
    data: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class ErrorDetail(AppBaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(AppBaseModel):
    error: ErrorDetail
