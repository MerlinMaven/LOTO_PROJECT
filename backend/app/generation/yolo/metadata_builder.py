"""
YoloMetadataBuilder — generates candidate YOLO-World detection prompts.

IMPORTANT: No inference is performed here.
This module prepares SUGGESTIONS for the HSE reviewer.
The reviewer must approve all prompts before YOLO activation (Phase 4).

Prompt generation strategy per component type:
  - Use physical_description as the base detection prompt
  - Use state_active / state_isolated from VisionMetadata as state prompts
  - Add component-type-specific template prompts
  - Flag components with thin descriptions (low detectability)

Output per component:
  {
    "component_id": str,
    "label": str,
    "candidate_detection_prompts": [...],   # What YOLO should look for
    "state_prompts": {                       # Per-state prompts
      "active":   [...],
      "isolated": [...],
    },
    "confidence_threshold_suggestion": float,
    "detection_difficulty": str,
    "notes_for_reviewer": str,
  }
"""

from __future__ import annotations

from app.generation.models.machine_knowledge import (
    ComponentType,
    MachineComponent,
    MachineKnowledge,
)


# ── Type-specific prompt templates ────────────────────────────────────────────
# Each template is a list of generic prompts for this component type.
# They are combined with the specific description for richer coverage.

_TYPE_TEMPLATES: dict[ComponentType, dict] = {
    ComponentType.ISOLATION_SWITCH: {
        "active_suffixes": ["in ON position", "pressed up", "activated"],
        "isolated_suffixes": ["in OFF position", "pressed down", "deactivated"],
        "confidence_suggestion": 0.80,
        "difficulty": "medium",
    },
    ComponentType.ENERGY_SOURCE: {
        "active_suffixes": ["installed", "inserted", "connected"],
        "isolated_suffixes": ["removed", "disconnected", "absent"],
        "confidence_suggestion": 0.75,
        "difficulty": "medium",
    },
    ComponentType.SAFETY_GUARD: {
        "active_suffixes": ["closed", "secured", "in closed position"],
        "isolated_suffixes": ["open", "slid open", "moved aside"],
        "confidence_suggestion": 0.80,
        "difficulty": "easy",
    },
    ComponentType.ACCESS_PANEL: {
        "active_suffixes": ["closed", "latched"],
        "isolated_suffixes": ["open", "removed"],
        "confidence_suggestion": 0.80,
        "difficulty": "easy",
    },
    ComponentType.MAINTENANCE_TARGET: {
        "active_suffixes": ["in place", "installed"],
        "isolated_suffixes": ["being worked on", "under maintenance"],
        "confidence_suggestion": 0.60,
        "difficulty": "hard",
    },
    ComponentType.STORAGE_UNIT: {
        "active_suffixes": ["empty"],
        "isolated_suffixes": ["containing item", "occupied"],
        "confidence_suggestion": 0.75,
        "difficulty": "medium",
    },
    ComponentType.LOCKOUT_POINT: {
        "active_suffixes": ["unlocked", "hasp open"],
        "isolated_suffixes": ["locked", "padlock applied"],
        "confidence_suggestion": 0.85,
        "difficulty": "easy",
    },
    ComponentType.INDICATOR: {
        "active_suffixes": ["showing alignment", "marker visible"],
        "isolated_suffixes": ["misaligned", "offset"],
        "confidence_suggestion": 0.70,
        "difficulty": "hard",
    },
    ComponentType.SAFETY_DEVICE: {
        "active_suffixes": ["applied", "locked"],
        "isolated_suffixes": ["removed"],
        "confidence_suggestion": 0.85,
        "difficulty": "easy",
    },
    ComponentType.SENSOR: {
        "active_suffixes": ["triggered", "active state"],
        "isolated_suffixes": ["not triggered", "inactive"],
        "confidence_suggestion": 0.65,
        "difficulty": "hard",
    },
}

_DEFAULT_TEMPLATE = {
    "active_suffixes": ["active", "in use"],
    "isolated_suffixes": ["isolated", "locked out"],
    "confidence_suggestion": 0.70,
    "difficulty": "medium",
}


class YoloMetadataBuilder:
    """
    Enriches MachineKnowledge component VisionMetadata with candidate prompts.

    Also returns a summary dict suitable for storage in GenerationResult.yolo_metadata.
    """

    def build_for_knowledge(self, knowledge: MachineKnowledge) -> dict:
        """
        Build YOLO metadata for all components in MachineKnowledge.

        Returns a dict keyed by component_id, each value being
        the per-component metadata dict.
        """
        result: dict = {}
        for component in knowledge.components:
            result[component.component_id] = self.build_for_component(component)
        return result

    def build_for_component(self, component: MachineComponent) -> dict:
        """
        Generate YOLO metadata for a single component.
        Also mutates component.vision_metadata in place with enriched prompts.
        """
        tmpl = _TYPE_TEMPLATES.get(component.component_type, _DEFAULT_TEMPLATE)
        description = component.physical_description
        label = component.label.lower()

        # ── Candidate detection prompts (not state-specific) ─────────────────
        base_prompts = list({
            description,
            label,
            component.physical_description.lower(),
        })
        candidate_prompts = [p for p in base_prompts if p]

        # ── State prompts ─────────────────────────────────────────────────────
        state_prompts: dict[str, list[str]] = dict(
            component.vision_metadata.state_prompts
        )  # start from existing

        # Enrich "active" state
        existing_active = state_prompts.get("active", [])
        active_additions = [
            f"{description} {suffix}" for suffix in tmpl["active_suffixes"]
        ]
        state_prompts["active"] = list(
            dict.fromkeys(existing_active + active_additions)
        )[:4]  # cap at 4 prompts per state

        # Enrich "isolated" state
        existing_isolated = state_prompts.get("isolated", [])
        isolated_additions = [
            f"{description} {suffix}" for suffix in tmpl["isolated_suffixes"]
        ]
        state_prompts["isolated"] = list(
            dict.fromkeys(existing_isolated + isolated_additions)
        )[:4]

        # ── Notes for reviewer ─────────────────────────────────────────────────
        notes = self._reviewer_notes(component, tmpl["difficulty"])

        # Mutate the component's vision metadata with enriched data
        component.vision_metadata.state_prompts = state_prompts
        component.vision_metadata.candidate_detection_prompts = candidate_prompts
        component.vision_metadata.detection_difficulty = tmpl["difficulty"]
        component.vision_metadata.notes_for_reviewer = notes

        return {
            "component_id": component.component_id,
            "label": component.label,
            "component_type": component.component_type.value,
            "candidate_detection_prompts": candidate_prompts,
            "state_prompts": state_prompts,
            "confidence_threshold_suggestion": tmpl["confidence_suggestion"],
            "detection_difficulty": tmpl["difficulty"],
            "notes_for_reviewer": notes,
        }

    @staticmethod
    def _reviewer_notes(component: MachineComponent, difficulty: str) -> str:
        lines: list[str] = [
            "Auto-generated prompts — review before YOLO activation.",
        ]

        if difficulty == "hard":
            lines.append(
                "Detection difficulty: HARD. "
                "Consider adding more specific prompts or increasing confidence threshold."
            )

        if component.extraction_confidence < 0.7:
            lines.append(
                f"Low extraction confidence ({component.extraction_confidence:.0%}). "
                "Verify this component exists before approving YOLO prompts."
            )

        if not component.vision_metadata.state_prompts.get("isolated"):
            lines.append(
                "No isolated-state prompt found. "
                "Add a prompt describing what this component looks like when locked out."
            )

        return " | ".join(lines)
