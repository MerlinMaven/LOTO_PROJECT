"""
LLMService port (Phase 2 LLM integration extension point).

Defines the abstract interface for LLM-based procedure generation.
Phase 2 provides a StubLLMService that returns an empty template.

When Phase 2 LLM is fully wired:
1. Create OpenRouterLLMService(LLMService) in infrastructure/
2. Swap the dependency in api/deps.py
3. Zero changes to the service or API layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMGenerationResult:
    workflow_definition: dict
    model_used: str
    generation_source: str    # "llm_text" | "llm_vision"
    raw_response: str | None = None


class LLMService(ABC):
    """
    Abstract interface for LLM-driven procedure generation.

    Implementations:
    - StubLLMService       (Phase 2, returns template skeleton)
    - OpenRouterLLMService (Phase 2+, calls OpenRouter/Qwen)
    - VisionLLMService     (Phase 3, calls multimodal model with image)
    """

    @abstractmethod
    async def generate_procedure(
        self,
        machine_id: str,
        machine_name: str,
        components: list[dict],
        **kwargs,
    ) -> LLMGenerationResult:
        """
        Generate a LOTO procedure workflow_definition from machine metadata.

        The returned workflow_definition must conform to schema v1.0.
        The caller (ProcedureService) validates the schema before storing.
        """
        ...


class StubLLMService(LLMService):
    """
    Phase 2 stub — returns a minimal valid workflow template.

    Allows the full procedure creation pipeline to be tested without
    an actual LLM API key configured.
    """

    async def generate_procedure(
        self,
        machine_id: str,
        machine_name: str,
        components: list[dict],
        **kwargs,
    ) -> LLMGenerationResult:
        workflow = {
            "phases": [
                {
                    "phase_id": "ph_lockout",
                    "phase_type": "lockout",
                    "sequence": 1,
                    "title": "Lockout Phase (Generated Stub)",
                    "stages": [
                        {
                            "stage_id": "st_001",
                            "sequence": 1,
                            "title": "Energy Isolation",
                            "steps": [
                                {
                                    "step_id": "stp_001",
                                    "sequence": 1,
                                    "component_ref": components[0]["id"] if components else "N/A",
                                    "instruction": "Isolate all energy sources as per safety procedure.",
                                    "validation": {
                                        "method": "manual_confirmation",
                                        "timeout_seconds": 120,
                                        "override_policy": {
                                            "allowed": True,
                                            "requires_reason": True,
                                            "requires_evidence_photo": False,
                                        },
                                    },
                                    "ar_config": None,
                                    "audit_config": {
                                        "evidence_photo_required": False,
                                        "step_criticality": "high",
                                    },
                                }
                            ],
                        }
                    ],
                },
                {
                    "phase_id": "ph_restoration",
                    "phase_type": "restoration",
                    "sequence": 2,
                    "title": "Restoration Phase (Generated Stub)",
                    "stages": [
                        {
                            "stage_id": "st_002",
                            "sequence": 1,
                            "title": "Energy Restoration",
                            "steps": [
                                {
                                    "step_id": "stp_002",
                                    "sequence": 1,
                                    "component_ref": components[0]["id"] if components else "N/A",
                                    "instruction": "Restore energy sources in reverse order of isolation.",
                                    "validation": {
                                        "method": "manual_confirmation",
                                        "timeout_seconds": 120,
                                        "override_policy": {
                                            "allowed": True,
                                            "requires_reason": True,
                                            "requires_evidence_photo": False,
                                        },
                                    },
                                    "ar_config": None,
                                    "audit_config": {
                                        "evidence_photo_required": False,
                                        "step_criticality": "medium",
                                    },
                                }
                            ],
                        }
                    ],
                },
            ]
        }
        return LLMGenerationResult(
            workflow_definition=workflow,
            model_used="stub_phase2",
            generation_source="manual",
        )
