"""
SmartLOTO Authoring Service — Service d'Audit.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    event_type: str,
    actor_id: str,
    *,
    machine_id: Optional[str] = None,
    procedure_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        machine_id=machine_id,
        procedure_id=procedure_id,
        payload=payload or {},
    )
    db.add(event)
    await db.flush()
    return event
