"""
SmartLOTO Field Service — Modèles de données Pydantic.
Contrats d'API stricts consommés par Unity (SmartLOTOClient.cs).
NE PAS RENOMMER les champs sans mettre à jour SmartLOTOClient.cs.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class StartIntervention(BaseModel):
    """POST /interventions/start — Démarre une session LOTO pour une machine."""
    machine_id: str
    operator_name: str


class ActionValidation(BaseModel):
    """POST /interventions/validate-step — Vérification visuelle YOLO-World."""
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str
    vision_prompt: str


class ActionOverride(BaseModel):
    """POST /interventions/override-step — Dérogation manuelle avec preuve photo."""
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str
    reason: str
    verification_method: Optional[str] = None


class CloseIntervention(BaseModel):
    """POST /interventions/close — Clôture, signature opérateur et génération PDF."""
    intervention_id: str
    signature_base64: str


class AnchorItem(BaseModel):
    """Point d'ancrage spatial calibré sur le casque Unity (pose 6-DOF)."""
    organ_name: str
    pos_x: float
    pos_y: float
    pos_z: float
    rot_x: float
    rot_y: float
    rot_z: float


class AnchorsUpdate(BaseModel):
    """POST /procedures/{machine_id}/anchors — Enregistrement des ancres Unity."""
    anchors_list: List[AnchorItem]
