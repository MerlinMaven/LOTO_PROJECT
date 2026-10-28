"""Export the approved matrix itself, never a demonstration component template."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.api.procedures import export_procedure
from app.services import procedure_service


class GenericUnityExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_published_custom_matrix_and_flat_hse_answers_survive_export(self):
        workflow = {
            "schema_version": "2.0", "objective": "Inspect a hydraulic coupling",
            "expected_final_state": "Coupling sealed",
            # C01 deliberately overlaps the old demo's ID but is a different component.
            "components": [{"component_id": "C01", "tag": "HYD-88", "label": "Hydraulic coupling",
                "physical_signatures": [{"signature_type": "GÉOMÉTRIE", "description": "Hexagonal coupling"}],
                "state_rules": [{"state_name": "SEALED", "physical_rule": "No visible gap"}]}],
            "phases": [{"phase_id": "inspect", "phase_type": "inspection", "stages": [
                {"stage_id": "coupling-check", "steps": [{"step_id": "check-gap", "primary_component": "HYD-88",
                    "instruction": "Inspect the gap", "verification": {"method": "visual_observation", "criteria": ["No visible gap"]}}]}
            ]}],
            "clarifications_required": [{"id": "decision", "status": "resolved", "answer": "Inspect the entire circumference", "affected_step_ids": ["check-gap"]}],
        }
        version = SimpleNamespace(id="published-88", status="published", workflow_definition=workflow)
        procedure = SimpleNamespace(machine_id="HYDRAULIC-88", machine_name="Hydraulic unit", active_version_id=version.id,
                                    versions=[version], status="PUBLISHED", created_by_hse="test-reviewer")
        with patch.object(procedure_service, "get_procedure_by_id", AsyncMock(return_value=procedure)):
            payload = await export_procedure("HYDRAULIC-88", db=None)
        self.assertEqual(payload["objective"], workflow["objective"])
        self.assertEqual(payload["components"][0]["physical_signatures"][0]["description"], "Hexagonal coupling")
        self.assertEqual(payload["components"][0]["physical_signatures"][0]["signature_type"], "GÉOMÉTRIE")
        self.assertEqual(payload["components"][0]["state_rules"][0]["state_name"], "SEALED")
        self.assertEqual(payload["phases"][0]["stages"][0]["steps"][0]["primary_component"], "HYD-88")
        self.assertEqual(payload["clarifications_required"][0]["answer"], "Inspect the entire circumference")
        self.assertEqual(json.loads(payload["workflow_json"]), workflow)
