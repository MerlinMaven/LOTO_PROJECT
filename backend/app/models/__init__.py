"""
SQLAlchemy ORM models.

Import order matters for circular-FK resolution.
The __all__ list is consumed by Alembic's env.py to auto-detect all tables.
"""

from app.models.base import Base
from app.models.machine import Machine, MachineComponent
from app.models.procedure import Procedure, ProcedureApproval, ProcedureVersion
from app.models.intervention import Intervention, InterventionStep
from app.models.audit import AuditEvent

__all__ = [
    "Base",
    "Machine",
    "MachineComponent",
    "Procedure",
    "ProcedureVersion",
    "ProcedureApproval",
    "Intervention",
    "InterventionStep",
    "AuditEvent",
]
