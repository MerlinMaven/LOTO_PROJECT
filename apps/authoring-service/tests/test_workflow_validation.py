"""Deterministic contract tests using synthetic, non-industrial examples."""
from copy import deepcopy
import unittest

from app.services.workflow_validation import apply_clarification_impact, iter_steps, validate_workflow
from app.schemas_workflow import ProcedureDraftV2
from app.services.document_generation_service import _normalize_and_validate


def synthetic_draft():
    return {
        "schema_version": "2.0", "revision_id": "rev-synth-1",
        "machine_id": "DEMO-ENERGY-MIX", "machine_name": "Synthetic training rig",
        "maintenance_objective": "Inspect a replaceable drive component",
        "expected_final_state": "Equipment left in the state confirmed by the authorized maintainer",
        "source_documents": [
            {"source_id": "source-a", "filename": "synthetic-a.pdf", "page_count": 2},
            {"source_id": "source-b", "filename": "synthetic-b.pdf", "page_count": 1},
        ],
        "components": [
            {"component_id": "electric-feed", "label": "Electrical feed", "description": "Documented in synthetic example", "component_type": "energy_source", "relations": ["feeds motor"]},
            {"component_id": "pneumatic-feed", "label": "Pneumatic feed", "description": "Documented in synthetic example", "component_type": "energy_source", "relations": ["actuates clamp"]},
            {"component_id": "meter-1", "label": "Meter M-1", "description": "Instrument stated in example", "component_type": "instrument", "relations": []},
        ],
        "technical_facts": [
            {"fact_id": "fact-energy", "qualification": "documented", "category": "energy", "label": "Sources", "value": "Electrical and pneumatic sources are both described", "source_pages": [1], "source_quote": "Electrical and pneumatic sources are both described.", "source_refs": [{"source_id": "source-a", "page": 1, "quote": "Electrical and pneumatic sources are both described."}], "evidence_type": "text", "source_id": "source-a", "structured_value": None, "unit": "", "justification": ""},
            {"fact_id": "fact-conflict", "qualification": "contradictory", "category": "component", "label": "Drive module", "value": "Conflicting descriptions preserved", "source_pages": [1, 1], "source_quote": "", "source_refs": [], "evidence_type": "unknown", "source_id": "", "structured_value": None, "unit": "", "justification": "Two synthetic source statements conflict."},
        ],
        "visual_observations": [], "unknowns": [],
        "contradictions": [{"contradiction_id": "conflict-1", "subject": "Drive module", "statements": ["Source A: belt drive", "Source B: direct drive"], "source_pages": [1]}],
        "phases": [{"phase_id": "phase-inspect", "phase_type": "inspection", "sequence": 1, "title": "Inspect", "description": "Synthetic phase", "stages": [{"stage_id": "stage-a", "sequence": 1, "title": "Isolate", "steps": [
            {"step_id": "step-isolate", "sequence": 1, "instruction": "Have the authorized operator isolate both identified sources.", "component_refs": ["electric-feed", "pneumatic-feed"], "preconditions": [], "depends_on": [], "expected_result": "Both sources are isolated according to approved site practice.", "rationale": "Synthetic proposal requiring HSE review.", "basis": "reasoning_to_review", "fact_refs": ["fact-energy"], "evidence_refs": [], "unresolved_conditions": [], "verification": {"method": "human_confirmation", "criteria": ["Operator confirms each source was isolated"], "required_evidence": ["Operator statement"], "instrument_refs": [], "indeterminate_when": ["Operator cannot identify an isolation point"]}},
            {"step_id": "step-measure", "sequence": 2, "instruction": "Measure the specified condition with meter M-1.", "component_refs": ["meter-1"], "preconditions": ["Isolation is complete"], "depends_on": ["step-isolate"], "expected_result": "Recorded reading meets the value stated in the approved work instruction.", "rationale": "Synthetic measurement example.", "basis": "reasoning_to_review", "fact_refs": [], "evidence_refs": [{"source_id": "source-b", "page": 1}], "unresolved_conditions": [], "verification": {"method": "measurement", "criteria": ["Compare reading with approved limit"], "required_evidence": ["Recorded instrument reading"], "instrument_refs": ["meter-1"], "indeterminate_when": ["Instrument status or units are unknown"]}},
        ]}]}],
        "clarifications_required": [], "review": {"status": "draft_pending_review", "approved": False}, "validation_diagnostics": [],
    }


class WorkflowValidationTests(unittest.TestCase):
    def test_canonical_contract_accepts_multiple_energy_sources_and_methods(self):
        draft = ProcedureDraftV2.model_validate(synthetic_draft()).model_dump(mode="json")
        errors = [d for d in validate_workflow(draft) if d["severity"] in {"error", "blocking"}]
        warnings = [d for d in validate_workflow(draft) if d["severity"] == "warning"]
        self.assertEqual(errors, [])
        self.assertEqual({d["code"] for d in warnings}, {"VERIFICATION_METHOD_UNSUPPORTED_BY_OPERATOR_CLIENT"})
        steps = [step for phase in draft["phases"] for stage in phase["stages"] for step in stage["steps"]]
        self.assertEqual({ref for step in steps for ref in step["component_refs"]}, {"electric-feed", "pneumatic-feed", "meter-1"})
        self.assertEqual([step["verification"]["method"] for step in steps], ["human_confirmation", "measurement"])

    def test_missing_objective_is_diagnosed_without_inventing_actions(self):
        draft = synthetic_draft()
        draft["maintenance_objective"] = ""
        draft["phases"] = []
        result = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        codes = {item["code"] for item in validate_workflow(result)}
        self.assertIn("OBJECTIVE_REQUIRED", codes)
        self.assertEqual(result["phases"], [])

    def test_contradictions_remain_explicit_and_blocking_clarification_blocks_approval(self):
        draft = synthetic_draft()
        draft["clarifications_required"] = [{"id": "clarify-drive", "question": "Which drive design is installed?", "status": "unresolved", "affected_step_ids": ["step-measure"], "related_component_ids": [], "source_pages": [1]}]
        result = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        codes = {item["code"] for item in validate_workflow(result)}
        self.assertEqual(result["contradictions"][0]["statements"], ["Source A: belt drive", "Source B: direct drive"])
        self.assertIn("CLARIFICATION_OPEN", codes)

    def test_clarification_resolution_recomputes_only_affected_step_readiness(self):
        draft = synthetic_draft()
        draft["clarifications_required"] = [{"id": "clarify-drive", "question": "Which drive is installed?", "status": "unresolved", "affected_step_ids": ["step-measure"]}]
        apply_clarification_impact(draft)
        steps = {step["step_id"]: step for _, _, step in iter_steps(draft)}
        self.assertEqual(steps["step-measure"]["review_readiness"], "blocked")
        self.assertEqual(steps["step-isolate"]["review_readiness"], "reviewable")
        draft["clarifications_required"][0].update({"status": "resolved", "affected_steps_reviewed": True, "resolution": {"answer": "Drive type confirmed", "rationale": "Checked against revised equipment record"}})
        apply_clarification_impact(draft)
        self.assertEqual(steps["step-measure"]["review_readiness"], "reviewable")

    def test_manual_citation_review_requires_reason_and_preserves_fact_qualification(self):
        draft = synthetic_draft()
        fact = draft["technical_facts"][0]
        fact["citation_status"] = "unmatched"
        workflow = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        self.assertIn("FACT_CITATION_UNVERIFIED", {item["code"] for item in validate_workflow(workflow)})
        fact["citation_status"] = "manual_verified"
        fact["citation_review"] = {"rationale": "Checked against page 1 in the source PDF.", "quote": fact["source_quote"]}
        workflow = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        self.assertNotIn("FACT_CITATION_UNVERIFIED", {item["code"] for item in validate_workflow(workflow)})
        self.assertEqual(workflow["technical_facts"][0]["qualification"], "documented")

    def test_missing_instrument_and_dependency_cycle_are_blocking(self):
        draft = synthetic_draft()
        step = draft["phases"][0]["stages"][0]["steps"][1]
        step["verification"]["instrument_refs"] = []
        step["depends_on"] = ["step-isolate"]
        draft["phases"][0]["stages"][0]["steps"][0]["depends_on"] = ["step-measure"]
        result = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        codes = {item["code"] for item in validate_workflow(result)}
        self.assertIn("MEASURING_INSTRUMENT_UNSPECIFIED", codes)
        self.assertIn("DEPENDENCY_CYCLE", codes)

    def test_dependency_must_appear_before_the_step_that_depends_on_it(self):
        draft = synthetic_draft()
        steps = draft["phases"][0]["stages"][0]["steps"]
        steps[0]["depends_on"] = ["step-measure"]
        steps[1]["depends_on"] = []
        result = ProcedureDraftV2.model_validate(draft).model_dump(mode="json")
        codes = {item["code"] for item in validate_workflow(result)}
        self.assertIn("DEPENDENCY_ORDER", codes)


    def test_synthetic_model_response_is_normalized_without_legacy_duplicate_actions(self):
        extracted = {
            "filename": "synthetic-dossier.pdf", "sha256": "f" * 64, "content_version": "f" * 16,
            "size_bytes": 1234, "page_count": 1, "pages": [{"page": 1, "text": "Both electrical and pneumatic energy sources are documented."}],
            "text_characters": 62,
            "ocr_pages": [], "pages_without_text": [], "ocr_fallback_failed_pages": [],
        }
        response = {
            "machine_id": "SYNTH-ENERGY-RIG", "machine_name": "Synthetic energy rig", "maintenance_objective": "Inspect the drive", "expected_final_state": "Leave equipment isolated pending HSE decision",
            "components": [{"component_id": "power-electric", "label": "Electrical supply", "description": "Supply", "component_type": "energy_source", "relations": []}, {"component_id": "air-line", "label": "Air line", "description": "Pneumatic supply", "component_type": "energy_source", "relations": []}],
            "technical_facts": [
                {"fact_id": "fact-1", "qualification": "documented", "category": "energy", "label": "Energy sources", "value": "Electrical and pneumatic", "source_pages": [1], "source_quote": "Both electrical and pneumatic energy sources are documented.", "evidence_type": "text", "source_id": "source", "structured_value": {"value": "", "unit": "", "qualifier": ""}, "unit": "", "justification": ""},
                {"fact_id": "fact-2", "qualification": "documented", "category": "equipment", "label": "Unsupported paraphrase", "value": "A claim not in source", "source_pages": [1], "source_quote": "A very different sentence that is not there.", "evidence_type": "text", "source_id": "source", "structured_value": {"value": "", "unit": "", "qualifier": ""}, "unit": "", "justification": ""},
            ],
            "visual_observations": [{"observation_id": "obs-1", "source_id": "source", "page": 1, "figure_or_region": "Figure 1", "description": "A visual observation, not a quotation.", "component_refs": ["power-electric"]}],
            "unknowns": [], "contradictions": [],
            "phases": [{"phase_id": "phase-inspection", "phase_type": "inspection", "sequence": 1, "title": "Inspection", "description": "Synthetic phase", "stages": [{"stage_id": "stage-1", "sequence": 1, "title": "Confirm sources", "steps": [{"step_id": "step-1", "sequence": 1, "instruction": "Ask the authorized operator to identify both energy sources.", "component_refs": ["power-electric", "air-line"], "rationale": "Proposal based on the documented sources.", "basis": "reasoning_to_review", "preconditions": [], "depends_on": [], "expected_result": "Both sources are identified.", "fact_refs": ["fact-1"], "source_pages": [1], "validation": {"method": "manual_confirmation", "expected_state": "Both sources identified by operator", "criteria": ["Operator confirms both"], "required_evidence": ["Operator statement"], "instrument_refs": [], "indeterminate_when": ["A source cannot be identified"], "yolo_candidate_prompts": []}}]}]}],
            "clarifications_required": [],
        }
        workflow = _normalize_and_validate(response, extracted, "12345678-1234-1234-1234-123456789012")
        self.assertEqual(workflow["schema_version"], "2.0")
        self.assertEqual(workflow["technical_facts"][0]["qualification"], "documented")
        self.assertEqual(workflow["technical_facts"][1]["qualification"], "documented")
        self.assertEqual(workflow["technical_facts"][1]["citation_status"], "unmatched")
        self.assertTrue(workflow["technical_facts"][1]["source_quote"])
        self.assertEqual(workflow["visual_observations"][0]["description"], "A visual observation, not a quotation.")
        self.assertNotIn("lockout", workflow)
        self.assertNotIn("restoration", workflow)
        self.assertIn("FACT_CITATION_UNVERIFIED", {item["code"] for item in workflow["validation_diagnostics"]})
        normalized_response = deepcopy(response)
        normalized_response["technical_facts"][1]["source_quote"] = "both electrical and pneumatic energy sources are documented."
        normalized = _normalize_and_validate(normalized_response, extracted, "12345678-1234-1234-1234-123456789013")
        self.assertEqual(normalized["technical_facts"][1]["qualification"], "documented")
        self.assertIn(normalized["technical_facts"][1]["citation_status"], {"verified", "typography_normalized"})
        self.assertNotIn("FACT_CITATION_UNVERIFIED", {item["code"] for item in normalized["validation_diagnostics"]})

    def test_machine_identifier_and_filename_do_not_change_validation_rules(self):
        left = synthetic_draft()
        right = deepcopy(left)
        right["machine_id"] = "ANOTHER-DEMO"
        right["source_documents"][0]["filename"] = "different-name.pdf"
        self.assertEqual(
            [x["code"] for x in validate_workflow(left)],
            [x["code"] for x in validate_workflow(right)],
        )

    def test_missing_equipment_identity_gets_unique_internal_key_and_blocks_approval(self):
        extracted = {
            "filename": "generic.pdf", "sha256": "a" * 64, "content_version": "a" * 16,
            "size_bytes": 20, "page_count": 1,
            "pages": [{"page": 1, "text": "A generic maintenance objective is described."}],
            "text_characters": 42, "ocr_pages": [], "pages_without_text": [],
            "ocr_fallback_failed_pages": [],
        }
        response = {
            "machine_id": "", "machine_name": "Generic equipment",
            "maintenance_objective": "Inspect the equipment", "expected_final_state": "State confirmed by HSE",
            "components": [], "technical_facts": [], "inferences": [], "visual_observations": [],
            "unknowns": [], "contradictions": [], "phases": [], "clarifications_required": [],
        }
        first = _normalize_and_validate(response, extracted, "doc-a")
        second = _normalize_and_validate(response, extracted, "doc-b")
        self.assertNotEqual(first["machine_id"], second["machine_id"])
        self.assertTrue(first["machine_id"].startswith("DRAFT-"))
        self.assertFalse(first["equipment_identity_confirmed"])
        diagnostics = {item["code"] for item in first["validation_diagnostics"]}
        self.assertIn("EQUIPMENT_ID_UNCONFIRMED", diagnostics)
        self.assertTrue(any("identifiant unique" in item["question"] for item in first["clarifications_required"]))


if __name__ == "__main__":
    unittest.main()
