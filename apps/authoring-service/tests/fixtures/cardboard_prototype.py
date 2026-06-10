"""
Cardboard prototype test fixtures.

Provides MachineKnowledge and workflow_definition for the SmartLOTO
cardboard prototype machine — without any LLM call.

Used by:
- Unit tests (validator, generator, YOLO builder)
- Integration tests (full pipeline with StubLLMProvider)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import EnergyType
from app.generation.models.machine_knowledge import (
    ComponentType,
    ComponentVisionMetadata,
    ExtractionMetadata,
    Hazard,
    HazardSeverity,
    MachineComponent,
    MachineKnowledge,
)


def make_cardboard_knowledge() -> MachineKnowledge:
    """
    Ground-truth MachineKnowledge for the cardboard prototype.
    Directly mirrors maquette_test.json components.
    """
    return MachineKnowledge(
        machine_name="SmartLOTO Cardboard Prototype",
        description="Cardboard prototype for LOTO pipeline validation.",
        energy_types=[EnergyType.ELECTRICAL],
        components=[
            MachineComponent(
                component_id="main_switch",
                component_type=ComponentType.ISOLATION_SWITCH,
                label="Main Power Switch",
                physical_description="White rocker switch on the front panel",
                location_hint="Front panel, upper left",
                energy_type=EnergyType.ELECTRICAL,
                vision_metadata=ComponentVisionMetadata(
                    state_prompts={
                        "active": ["white switch pressed up"],
                        "isolated": ["white switch pressed down"],
                    }
                ),
                extraction_confidence=0.95,
            ),
            MachineComponent(
                component_id="battery_holder",
                component_type=ComponentType.ENERGY_SOURCE,
                label="Battery Holder",
                physical_description="Red battery holder / compartment",
                location_hint="Main body, center",
                energy_type=EnergyType.ELECTRICAL,
                vision_metadata=ComponentVisionMetadata(
                    state_prompts={
                        "active": ["battery inside the red holder"],
                        "isolated": ["empty red battery holder"],
                    }
                ),
                extraction_confidence=0.95,
            ),
            MachineComponent(
                component_id="safe_box",
                component_type=ComponentType.STORAGE_UNIT,
                label="Lockout Safe Box",
                physical_description="Cardboard box with padlock symbol",
                location_hint="Right side of prototype",
                energy_type=None,
                vision_metadata=ComponentVisionMetadata(
                    state_prompts={
                        "active": ["empty safe box"],
                        "isolated": ["battery inside the cardboard box next to the padlock drawing"],
                    }
                ),
                extraction_confidence=0.90,
                is_lockout_required=False,
            ),
            MachineComponent(
                component_id="transparent_guard",
                component_type=ComponentType.SAFETY_GUARD,
                label="Transparent Protective Cover",
                physical_description="Sliding transparent cover with alignment markers",
                location_hint="Front face of the prototype",
                energy_type=None,
                vision_metadata=ComponentVisionMetadata(
                    state_prompts={
                        "active": ["white square aligned with solid black circle"],
                        "isolated": ["white square aligned with empty circle"],
                    }
                ),
                extraction_confidence=0.88,
            ),
            MachineComponent(
                component_id="light_bulb",
                component_type=ComponentType.MAINTENANCE_TARGET,
                label="Light Bulb",
                physical_description="Standard light bulb accessible through the guard",
                location_hint="Center, behind transparent guard",
                energy_type=None,
                vision_metadata=ComponentVisionMetadata(
                    state_prompts={
                        "active": ["hand interacting with the bulb"],
                    }
                ),
                extraction_confidence=0.92,
            ),
        ],
        hazards=[
            Hazard(
                hazard_type="electrical",
                description="Risk of electric shock from battery circuit",
                severity=HazardSeverity.MEDIUM,
                associated_component_ids=["main_switch", "battery_holder"],
                mitigation="Switch OFF and remove battery before maintenance.",
            )
        ],
        maintenance_objectives=["Inspect or replace the light bulb"],
        special_considerations=[
            "Verify battery polarity when reinserting",
            "Ensure transparent guard is fully closed before restoring power",
        ],
        extraction_metadata=ExtractionMetadata(
            source_document_type="text",
            llm_model_used="stub-model-v1",
            prompt_template_name="component_extraction",
            prompt_version="1",
            overall_confidence=0.92,
            extraction_timestamp=datetime(2026, 6, 10, 18, 30, 0, tzinfo=timezone.utc),
        ),
    )


def make_cardboard_workflow() -> dict:
    """
    Minimal but valid workflow_definition for the cardboard prototype.
    Has all four required phases with at least one step each.
    """
    return {
        "phases": [
            {
                "phase_id": "ph_lockout",
                "phase_type": "lockout",
                "sequence": 1,
                "title": "Lockout",
                "stages": [
                    {
                        "stage_id": "st_isolate_main_switch",
                        "sequence": 1,
                        "title": "Isolate Main Switch",
                        "steps": [
                            {
                                "step_id": "ph_lockout.st_isolate_main_switch.stp_1",
                                "sequence": 1,
                                "instruction": "Move Main Power Switch to OFF position.",
                                "component_ref": "main_switch",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": ["white switch pressed down"],
                                },
                            }
                        ],
                    },
                    {
                        "stage_id": "st_remove_battery_holder",
                        "sequence": 2,
                        "title": "Remove Battery",
                        "steps": [
                            {
                                "step_id": "ph_lockout.st_remove_battery_holder.stp_1",
                                "sequence": 1,
                                "instruction": "Remove battery from red holder.",
                                "component_ref": "battery_holder",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": ["empty red battery holder"],
                                },
                            },
                            {
                                "step_id": "ph_lockout.st_remove_battery_holder.stp_2",
                                "sequence": 2,
                                "instruction": "Place battery in lockout safe box.",
                                "component_ref": "safe_box",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": [
                                        "battery inside the cardboard box next to the padlock drawing"
                                    ],
                                },
                            },
                        ],
                    },
                ],
            },
            {
                "phase_id": "ph_verification",
                "phase_type": "verification",
                "sequence": 2,
                "title": "Verification",
                "stages": [
                    {
                        "stage_id": "st_zero_energy",
                        "sequence": 1,
                        "title": "Zero-Energy Verification",
                        "steps": [
                            {
                                "step_id": "ph_verify.st_zero_energy.stp_1",
                                "sequence": 1,
                                "instruction": "Verify main switch is in OFF position.",
                                "component_ref": "main_switch",
                                "validation": {"method": "manual_confirmation"},
                            },
                            {
                                "step_id": "ph_verify.st_zero_energy.stp_2",
                                "sequence": 2,
                                "instruction": "Verify battery holder is empty.",
                                "component_ref": "battery_holder",
                                "validation": {"method": "manual_confirmation"},
                            },
                        ],
                    },
                    {
                        "stage_id": "st_access_preparation",
                        "sequence": 2,
                        "title": "Access Preparation",
                        "steps": [
                            {
                                "step_id": "ph_verify.st_access.stp_1",
                                "sequence": 1,
                                "instruction": "Open transparent protective cover.",
                                "component_ref": "transparent_guard",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": [
                                        "white square aligned with empty circle"
                                    ],
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "phase_id": "ph_maintenance",
                "phase_type": "maintenance",
                "sequence": 3,
                "title": "Maintenance",
                "stages": [
                    {
                        "stage_id": "st_light_bulb_maintenance",
                        "sequence": 1,
                        "title": "Light Bulb Maintenance",
                        "steps": [
                            {
                                "step_id": "ph_maintenance.st_light_bulb.stp_1",
                                "sequence": 1,
                                "instruction": "Inspect or replace the light bulb.",
                                "component_ref": "light_bulb",
                                "validation": {"method": "manual_confirmation"},
                            }
                        ],
                    }
                ],
            },
            {
                "phase_id": "ph_restoration",
                "phase_type": "restoration",
                "sequence": 4,
                "title": "Restoration",
                "stages": [
                    {
                        "stage_id": "st_access_closure",
                        "sequence": 1,
                        "title": "Close Guard",
                        "steps": [
                            {
                                "step_id": "ph_restoration.st_closure.stp_1",
                                "sequence": 1,
                                "instruction": "Close transparent guard fully.",
                                "component_ref": "transparent_guard",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": [
                                        "white square aligned with solid black circle"
                                    ],
                                },
                            }
                        ],
                    },
                    {
                        "stage_id": "st_restore_battery_holder",
                        "sequence": 2,
                        "title": "Restore Battery",
                        "steps": [
                            {
                                "step_id": "ph_restoration.st_restore_battery.stp_1",
                                "sequence": 1,
                                "instruction": "Reinsert battery with correct polarity.",
                                "component_ref": "battery_holder",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": [
                                        "battery inside the red holder"
                                    ],
                                },
                            }
                        ],
                    },
                    {
                        "stage_id": "st_activate_main_switch",
                        "sequence": 3,
                        "title": "Activate Switch",
                        "steps": [
                            {
                                "step_id": "ph_restoration.st_activate_main_switch.stp_1",
                                "sequence": 1,
                                "instruction": "Move Main Power Switch to ON position.",
                                "component_ref": "main_switch",
                                "validation": {
                                    "method": "vision_detection",
                                    "yolo_candidate_prompts": ["white switch pressed up"],
                                },
                            }
                        ],
                    },
                ],
            },
        ]
    }
