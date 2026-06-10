"""
StubLLMProvider — deterministic responses for tests and offline development.

The stub never calls an external API.
Responses are keyed by the first word of the system prompt so that
different prompt templates return different fixtures.

The default fixture is the SmartLOTO cardboard prototype — it represents
the maquette_test.json components in MachineKnowledgeRaw format.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from app.generation.providers.base import LLMProvider, LLMResponse, Message

# ── Cardboard prototype fixture ───────────────────────────────────────────────
# This is the ground-truth extraction for the maquette_test.json machine.
# Used by integration tests to validate the full pipeline without an API key.

_CARDBOARD_PROTOTYPE_FIXTURE = {
    "machine_name": "SmartLOTO Cardboard Prototype",
    "description": (
        "A physical cardboard prototype simulating industrial LOTO procedures "
        "for pipeline validation. Represents a minimal electrical system with "
        "power switch, battery energy source, safe storage, protective cover, "
        "and a light bulb maintenance target."
    ),
    "energy_types": ["electrical"],
    "components": [
        {
            "component_id": "main_switch",
            "component_type": "isolation_switch",
            "label": "Main Power Switch",
            "physical_description": "White rocker switch mounted on the front panel",
            "location_hint": "Front panel, upper left",
            "energy_type": "electrical",
            "state_active": "white switch pressed up",
            "state_locked": "white switch pressed down",
            "confidence": 0.95,
        },
        {
            "component_id": "battery_holder",
            "component_type": "energy_source",
            "label": "Battery Holder",
            "physical_description": "Red battery holder / compartment",
            "location_hint": "Main body, center",
            "energy_type": "electrical",
            "state_active": "battery inside the red holder",
            "state_locked": "empty red battery holder",
            "confidence": 0.95,
        },
        {
            "component_id": "safe_box",
            "component_type": "storage_unit",
            "label": "Lockout Safe Box",
            "physical_description": "Cardboard box marked with a padlock symbol",
            "location_hint": "Right side of prototype",
            "energy_type": None,
            "state_active": "empty safe box",
            "state_locked": "battery inside the cardboard box next to the padlock drawing",
            "confidence": 0.90,
        },
        {
            "component_id": "transparent_guard",
            "component_type": "safety_guard",
            "label": "Transparent Protective Cover",
            "physical_description": (
                "Sliding transparent cover with alignment markers — "
                "solid black circle means closed, empty circle means open"
            ),
            "location_hint": "Front face of the prototype",
            "energy_type": None,
            "state_active": "white square aligned with solid black circle",
            "state_locked": "white square aligned with empty circle",
            "confidence": 0.88,
        },
        {
            "component_id": "light_bulb",
            "component_type": "maintenance_target",
            "label": "Light Bulb",
            "physical_description": "Standard light bulb behind the transparent cover",
            "location_hint": "Center, behind transparent guard",
            "energy_type": None,
            "state_active": None,
            "state_locked": None,
            "confidence": 0.92,
        },
    ],
    "hazards": [
        {
            "hazard_type": "electrical",
            "description": "Risk of electric shock from battery-powered circuit",
            "severity": "medium",
            "associated_component_ids": ["main_switch", "battery_holder"],
            "mitigation": (
                "Switch main power OFF and physically remove the battery "
                "before opening the guard or touching the bulb."
            ),
        }
    ],
    "maintenance_objectives": ["Inspect or replace the light bulb"],
    "special_considerations": [
        "Verify battery polarity (+ terminal on + sign) when reinserting",
        "Ensure transparent guard is fully closed before restoring power",
    ],
}


class StubLLMProvider(LLMProvider):
    """
    Deterministic provider for testing.

    By default returns the cardboard prototype fixture for any prompt.
    Use `register_fixture` to override for specific test scenarios.
    """

    def __init__(self, latency_ms: float = 5.0) -> None:
        self._latency_ms = latency_ms
        self._fixtures: dict[str, dict] = {}
        self._call_count = 0

    @property
    def provider_name(self) -> str:
        return "stub"

    @property
    def default_model(self) -> str:
        return "stub-model-v1"

    def register_fixture(self, key: str, response: dict) -> None:
        """Register a custom JSON fixture keyed by a system prompt keyword."""
        self._fixtures[key] = response

    @property
    def call_count(self) -> int:
        return self._call_count

    async def complete(
        self,
        messages: list[Message],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        self._call_count += 1

        # Pick fixture: first matching keyword in the system prompt, else default
        system_content = next(
            (m.content for m in messages if m.role.value == "system"), ""
        )
        fixture = _CARDBOARD_PROTOTYPE_FIXTURE
        for key, custom in self._fixtures.items():
            if key.lower() in system_content.lower():
                fixture = custom
                break

        return LLMResponse(
            content=json.dumps(fixture, ensure_ascii=False),
            model_id=model or self.default_model,
            provider=self.provider_name,
            prompt_tokens=len(" ".join(m.content for m in messages)) // 4,
            completion_tokens=len(json.dumps(fixture)) // 4,
            latency_ms=self._latency_ms,
            finish_reason="stop",
        )
