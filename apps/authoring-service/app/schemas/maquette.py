"""
Pydantic v2 models for the SmartLOTO cardboard prototype (maquette) procedure format.

This schema represents the FLAT procedure structure used by the POC:
    Procedure
      └── Metadata
      └── List[Step]
              └── YoloValidation  (optional)

This is intentionally distinct from the production workflow schema
(phases → stages → steps) defined in app/schemas/procedure.py.
The POC format is consumed by the YOLO-World validation pipeline directly.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProcedureStatus(str, Enum):
    """Lifecycle states for a maquette procedure version."""
    DRAFT_PENDING_REVIEW = "draft_pending_review"
    APPROVED             = "approved"
    PUBLISHED            = "published"
    ARCHIVED             = "archived"


class StepType(str, Enum):
    """
    Classifies the nature of each LOTO step.

    - PHYSICAL_ACTION: the operator must physically interact with a component
      (switch, lock, cable…). Validated by YOLO-World vision.
    - HUMAN_ACTION: a cognitive or procedural action (inspection, verification).
      Vision validation is optional / best-effort.
    """
    PHYSICAL_ACTION = "physical_action"
    HUMAN_ACTION    = "human_action"


# ── Sub-models ────────────────────────────────────────────────────────────────

class YoloValidation(BaseModel):
    """
    Configuration block consumed by the YOLO-World detection pipeline.

    `target_objects` are zero-shot text prompts passed directly to YOLO-World.
    ALL listed objects must be detected above `confidence_threshold` for the
    step to be considered validated.
    """
    target_objects: List[str] = Field(
        ...,
        min_length=1,
        description="List of zero-shot YOLO-World text prompts. At least one required.",
        examples=[["white switch pressed down"]],
    )
    confidence_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence to consider the step validated (0.0–1.0).",
        examples=[0.85],
    )

    @field_validator("target_objects")
    @classmethod
    def prompts_must_not_be_empty_strings(cls, v: List[str]) -> List[str]:
        for prompt in v:
            if not prompt.strip():
                raise ValueError("Each target_object prompt must be a non-empty string.")
        return v


class Metadata(BaseModel):
    """Procedure lifecycle metadata — tracks authorship and approval state."""
    version: str = Field(
        ...,
        description="Semantic version of this procedure document (e.g. '1.0', '2.3').",
        examples=["1.0"],
    )
    status: ProcedureStatus = Field(
        ...,
        description="Current lifecycle state. Transitions enforced by the state machine.",
    )
    created_by: str = Field(
        ...,
        min_length=1,
        description="Identifier of the HSE expert who authored this procedure.",
        examples=["expert_hse_01"],
    )
    approved_by: Optional[str] = Field(
        None,
        description="Identifier of the approver. Null while status is draft_pending_review.",
        examples=[None, "approver_hse_02"],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp of procedure creation (ISO 8601).",
        examples=["2026-06-10T18:30:00Z"],
    )

    @field_validator("approved_by")
    @classmethod
    def approved_by_required_when_approved(
        cls, v: Optional[str], info
    ) -> Optional[str]:
        """
        Soft constraint: warn if the status is approved/published/archived
        but approved_by is still null. Full enforcement lives in the service layer.
        """
        return v


class Step(BaseModel):
    """
    A single atomic LOTO step the operator must execute.

    `state_before` documents the expected physical state of the machine
    BEFORE this step is executed — used as context for the vision pipeline
    and as a human-readable safety checkpoint.
    """
    step_id: int = Field(
        ...,
        ge=1,
        description="Unique sequential identifier for this step within the procedure.",
        examples=[1],
    )
    step_type: StepType = Field(
        ...,
        description="Nature of the action: physical manipulation or human verification.",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Short label summarising what this step achieves.",
        examples=["Couper l'alimentation principale"],
    )
    operator_instruction: str = Field(
        ...,
        min_length=1,
        description="Detailed, unambiguous instruction shown to the operator on the AR headset.",
        examples=["Appuyer sur l'interrupteur vers le bas pour le mettre en position OFF."],
    )
    state_before: List[str] = Field(
        default_factory=list,
        description=(
            "List of YOLO-World prompts describing the expected machine state "
            "BEFORE this step. Can be empty for the first step or human actions."
        ),
        examples=[["white switch pressed up"]],
    )
    yolo_validation: Optional[YoloValidation] = Field(
        None,
        description=(
            "YOLO-World validation config for this step. "
            "Null only for fully manual steps with no vision checkpoint."
        ),
    )


# ── Root model ────────────────────────────────────────────────────────────────

class Procedure(BaseModel):
    """
    Root model for a SmartLOTO maquette LOTO procedure.

    Represents the flat POC format (steps directly under the procedure root).
    The production format uses a phases → stages → steps hierarchy
    defined in app/schemas/procedure.py.
    """

    model_config = ConfigDict(
        # Allows .model_validate(orm_object) if needed in the future.
        from_attributes=True,
        # Populates the Swagger /docs "Example Value" with the full maquette JSON.
        json_schema_extra={
            "example": {
                "procedure_id": "LOTO_CARTON_POC_V1",
                "machine_name": "SmartLOTO Cardboard Prototype",
                "metadata": {
                    "version": "1.0",
                    "status": "draft_pending_review",
                    "created_by": "expert_hse_01",
                    "approved_by": None,
                    "created_at": "2026-06-10T18:30:00Z",
                },
                "steps": [
                    {
                        "step_id": 1,
                        "step_type": "physical_action",
                        "description": "Couper l'alimentation principale",
                        "operator_instruction": "Appuyer sur l'interrupteur vers le bas pour le mettre en position OFF.",
                        "state_before": ["white switch pressed up"],
                        "yolo_validation": {
                            "target_objects": ["white switch pressed down"],
                            "confidence_threshold": 0.85,
                        },
                    },
                    {
                        "step_id": 2,
                        "step_type": "physical_action",
                        "description": "Isoler la source d'énergie",
                        "operator_instruction": "Retirer la pile du conteneur rouge.",
                        "state_before": ["battery inside the red holder"],
                        "yolo_validation": {
                            "target_objects": ["empty red battery holder"],
                            "confidence_threshold": 0.80,
                        },
                    },
                    {
                        "step_id": 3,
                        "step_type": "physical_action",
                        "description": "Consignation (Lockout)",
                        "operator_instruction": "Placer la pile dans la Safe Box, à côté du symbole de cadenas.",
                        "state_before": ["empty safe box"],
                        "yolo_validation": {
                            "target_objects": [
                                "battery inside the cardboard box next to the padlock drawing"
                            ],
                            "confidence_threshold": 0.80,
                        },
                    },
                    {
                        "step_id": 4,
                        "step_type": "physical_action",
                        "description": "Ouverture du carter de protection",
                        "operator_instruction": "Faire glisser le carter transparent jusqu'à ce que le carré blanc coïncide avec le cercle vide.",
                        "state_before": ["white square aligned with solid black circle"],
                        "yolo_validation": {
                            "target_objects": [
                                "white square aligned with empty circle",
                                "transparent cover open",
                            ],
                            "confidence_threshold": 0.75,
                        },
                    },
                    {
                        "step_id": 5,
                        "step_type": "human_action",
                        "description": "Intervention de maintenance",
                        "operator_instruction": "Effectuer la vérification ou le remplacement de l'ampoule.",
                        "state_before": [],
                        "yolo_validation": {
                            "target_objects": ["hand interacting with the bulb"],
                            "confidence_threshold": 0.60,
                        },
                    },
                    {
                        "step_id": 6,
                        "step_type": "physical_action",
                        "description": "Fermeture du carter de protection",
                        "operator_instruction": "Refermer le carter. Le carré blanc doit coïncider avec le cercle noir plein.",
                        "state_before": ["white square aligned with empty circle"],
                        "yolo_validation": {
                            "target_objects": [
                                "white square aligned with solid black circle",
                                "transparent cover closed",
                            ],
                            "confidence_threshold": 0.85,
                        },
                    },
                    {
                        "step_id": 7,
                        "step_type": "physical_action",
                        "description": "Remise en place de l'énergie (Vérification Polarité)",
                        "operator_instruction": "Insérer la pile dans l'emplacement sans le 'X'. S'assurer que le pôle + est sur le signe +.",
                        "state_before": ["empty red battery holder"],
                        "yolo_validation": {
                            "target_objects": [
                                "battery in the right slot of the red holder",
                                "battery positive terminal aligned with the drawn plus sign",
                                "empty slot with X mark",
                            ],
                            "confidence_threshold": 0.70,
                        },
                    },
                    {
                        "step_id": 8,
                        "step_type": "physical_action",
                        "description": "Remise en marche",
                        "operator_instruction": "Appuyer sur l'interrupteur vers le haut pour le mettre en position ON.",
                        "state_before": ["white switch pressed down"],
                        "yolo_validation": {
                            "target_objects": ["white switch pressed up"],
                            "confidence_threshold": 0.85,
                        },
                    },
                ],
            }
        },
    )

    procedure_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier for this procedure document.",
        examples=["LOTO_CARTON_POC_V1"],
    )
    machine_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name of the machine this procedure applies to.",
        examples=["SmartLOTO Cardboard Prototype"],
    )
    metadata: Metadata
    steps: List[Step] = Field(
        ...,
        min_length=1,
        description="Ordered list of LOTO steps. Must contain at least one step.",
    )

    @field_validator("steps")
    @classmethod
    def step_ids_must_be_unique_and_sequential(cls, v: List[Step]) -> List[Step]:
        ids = [s.step_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique within a procedure.")
        if sorted(ids) != list(range(1, len(ids) + 1)):
            raise ValueError(
                "step_id values must be sequential integers starting at 1 "
                f"(expected 1–{len(ids)}, got {sorted(ids)})."
            )
        return v
