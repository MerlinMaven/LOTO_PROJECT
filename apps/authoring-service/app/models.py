"""
SmartLOTO Authoring Service — Modèles de Données SQLAlchemy.
Schéma consolidé et simplifié pour le cycle de vie HSE et l'audit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Procedure(Base):
    """Enveloppe principale de la procedure LOTO associee a un equipement."""
    __tablename__ = "procedures"

    # machine_id sert de cle primaire unique partagee avec field-service
    machine_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    machine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_hse: Mapped[str] = mapped_column(String(255), default="hse_supervisor@smartloto.io")
    status: Mapped[str] = mapped_column(String(50), default="APPROVED")
    workflow_stages: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def id(self) -> str:
        return self.machine_id

    @property
    def active_version_id(self) -> Optional[str]:
        if isinstance(self.workflow_stages, dict):
            return self.workflow_stages.get("_active_version_id")
        return None

    @active_version_id.setter
    def active_version_id(self, val: Optional[str]):
        if not isinstance(self.workflow_stages, dict):
            self.workflow_stages = {}
        self.workflow_stages["_active_version_id"] = val

    versions: Mapped[List[ProcedureVersion]] = relationship("ProcedureVersion", back_populates="procedure", cascade="all, delete-orphan")


class ProcedureVersion(Base):
    """Version immuable du contenu d'une procédure (workflow JSON et étapes)."""
    __tablename__ = "procedure_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    procedure_id: Mapped[str] = mapped_column(String(100), ForeignKey("procedures.machine_id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft_pending_review")
    workflow_definition: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    procedure: Mapped[Procedure] = relationship("Procedure", back_populates="versions")
    approvals: Mapped[List[ProcedureApproval]] = relationship("ProcedureApproval", back_populates="version", cascade="all, delete-orphan")


class ProcedureApproval(Base):
    """Enregistrement formel de la validation HSE d'une version de procédure."""
    __tablename__ = "procedure_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    procedure_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("procedure_versions.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # approved / rejected
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    version: Mapped[ProcedureVersion] = relationship("ProcedureVersion", back_populates="approvals")


class AuditEvent(Base):
    """Piste d'audit immuable des actions critiques (OSHA 1910.147)."""
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    machine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    procedure_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Intervention(Base):
    """Intervention de maintenance réalisée sur le terrain (synchronisée avec field-service)."""
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    machine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="IN_PROGRESS")
    current_stage_id: Mapped[int] = mapped_column(Integer, default=1)
    logs: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    signature_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_report_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
