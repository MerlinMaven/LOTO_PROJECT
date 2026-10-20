"""
SmartLOTO Authoring Service — Session et Moteur de Base de Données (SQLAlchemy Async).
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
    """Dépendance FastAPI fournissant une session SQLAlchemy asynchrone."""
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
    """Crée les tables au démarrage si elles n'existent pas encore et injecte le seed."""
    from app.models import Procedure, ProcedureVersion
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Vérification et injection de la procédure par défaut pour test immédiat
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res = await session.execute(select(Procedure).where(Procedure.machine_id == "PUMP-001"))
        proc = res.scalar_one_or_none()

        sample_workflow = {
            "lockout": [
                {
                    "stage_id": 1,
                    "title": "Consignation Électrique",
                    "actions": [
                        {
                            "action_id": "step_1",
                            "description": "Tourner le sectionneur Q1 sur la position 0 (OFF) et apposer le cadenas rouge.",
                            "vision_prompt": "red padlock on electrical rotary switch in off position",
                            "completion_check": "Cadenas en place et sectionneur verrouillé.",
                            "spatial_guide": {
                                "hologram_type": "padlock",
                                "pos_x": 0.15, "pos_y": 1.20, "pos_z": 0.45,
                                "rot_x": 0.0, "rot_y": 90.0, "rot_z": 0.0
                            }
                        }
                    ]
                },
                {
                    "stage_id": 2,
                    "title": "Vérification d'Absence de Tension (VAT)",
                    "actions": [
                        {
                            "action_id": "step_2",
                            "description": "Contrôler la tension résiduelle aux bornes du moteur à l'aide d'un multimètre certifié (VAT).",
                            "vision_prompt": "digital multimeter measuring zero voltage display",
                            "completion_check": "Affichage 0.00 V confirmé.",
                            "spatial_guide": {
                                "hologram_type": "sensor",
                                "pos_x": -0.20, "pos_y": 0.95, "pos_z": 0.50,
                                "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                            }
                        }
                    ]
                }
            ],
            "restoration": [
                {
                    "stage_id": 3,
                    "title": "Déconsignation et Remise en Service",
                    "actions": [
                        {
                            "action_id": "step_3",
                            "description": "Retirer le cadenas de consignation et réarmer le sectionneur principal sur 1 (ON).",
                            "vision_prompt": "electrical rotary switch in on position without padlock",
                            "completion_check": "Sectionneur réarmé sur 1 (ON).",
                            "spatial_guide": {
                                "hologram_type": "switch",
                                "pos_x": 0.15, "pos_y": 1.20, "pos_z": 0.45,
                                "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                            }
                        }
                    ]
                }
            ],
            "anchors": {
                "Sectionneur_Q1": {
                    "pos_x": 0.15, "pos_y": 1.20, "pos_z": 0.45,
                    "rot_x": 0.0, "rot_y": 90.0, "rot_z": 0.0
                },
                "Moteur_Pompe": {
                    "pos_x": -0.20, "pos_y": 0.95, "pos_z": 0.50,
                    "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0
                }
            }
        }

        if not proc:
            proc = Procedure(
                machine_id="PUMP-001",
                machine_name="Pompe Principale d'Extraction",
                created_by_hse="hse_supervisor@smartloto.io",
                status="APPROVED",
                workflow_stages=sample_workflow,
            )
            session.add(proc)
            await session.flush()

        v_res = await session.execute(
            select(ProcedureVersion).where(ProcedureVersion.procedure_id == "PUMP-001")
        )
        if not v_res.scalar_one_or_none():
            version = ProcedureVersion(
                procedure_id="PUMP-001",
                version_number=1,
                status="published",
                workflow_definition=sample_workflow,
                created_by="hse_supervisor@smartloto.io",
            )
            session.add(version)

        await session.commit()
        print(f"[OK] Auto-seed PUMP-001 pret et verifie sur la base partagee ({SQLITE_DB_PATH})")

    print(f"[OK] Base de donnees partagee active : {SQLITE_DB_PATH}")


async def close_db() -> None:
    """Ferme les connexions lors de l'arrêt."""
    await engine.dispose()
