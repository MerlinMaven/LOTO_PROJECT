"""
Pydantic request / response models for the Runtime (Field Service) API.

These shapes are consumed by Unity (SmartLOTOClient.cs) and the Streamlit
dashboard.  Their field names and types are part of the public API contract
and MUST NOT change without a corresponding update to the Unity C# classes.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


# ── Request models ────────────────────────────────────────────────────────────


class StartIntervention(BaseModel):
    """POST /interventions/start — begin a new LOTO session."""
    machine_id: str
    operator_name: str


class ActionValidation(BaseModel):
    """POST /interventions/validate-step — YOLO-World visual verification."""
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str
    vision_prompt: str


class ActionOverride(BaseModel):
    """POST /interventions/override-step — manual bypass with photographic evidence."""
    intervention_id: str
    stage_id: int
    action_id: str
    image_base64: str
    reason: str


class CloseIntervention(BaseModel):
    """POST /interventions/close — submit operator signature and generate audit PDF."""
    intervention_id: str
    signature_base64: str


class AnchorItem(BaseModel):
    """A single calibrated spatial anchor (organ name + 6-DOF pose)."""
    organ_name: str
    pos_x: float
    pos_y: float
    pos_z: float
    rot_x: float
    rot_y: float
    rot_z: float


class AnchorsUpdate(BaseModel):
    """POST /procedures/{machine_id}/anchors — upload Quest-calibrated anchor list."""
    anchors_list: List[AnchorItem]
