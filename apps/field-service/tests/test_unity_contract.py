"""Contract-level tests for the JSON consumed by SmartLOTOClient.cs."""
import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException

import app.database as database
from app.api.interventions import start_intervention
from app.api.procedures import get_procedure, sanitize_procedure_for_unity
from app.database import LocalSQLiteClient
from app.models import StartIntervention


class UnityContractTests(unittest.TestCase):
    def test_local_schema_migration_preserves_existing_rows_and_adds_revision_pin(self):
        with tempfile.TemporaryDirectory(prefix="smartloto-migration-") as directory:
            path = Path(directory) / "existing.sqlite"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE procedures(machine_id TEXT PRIMARY KEY, machine_name TEXT NOT NULL, created_by_hse TEXT NOT NULL, status TEXT, workflow_stages TEXT NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP)")
            connection.execute("CREATE TABLE interventions(id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, operator_name TEXT NOT NULL, status TEXT, current_stage_id INT, logs TEXT, signature_url TEXT, pdf_report_url TEXT, started_at TIMESTAMP, completed_at TIMESTAMP)")
            connection.execute("INSERT INTO procedures(machine_id,machine_name,created_by_hse,status,workflow_stages) VALUES('KEEP-ME','Existing','test','DRAFT','{}')")
            connection.execute("INSERT INTO interventions(id,machine_id,operator_name,status) VALUES('existing-int','KEEP-ME','operator','COMPLETED')")
            connection.commit()
            connection.close()

            LocalSQLiteClient(str(path))
            connection = sqlite3.connect(path)
            self.assertEqual(connection.execute("SELECT machine_name FROM procedures WHERE machine_id='KEEP-ME'").fetchone()[0], "Existing")
            self.assertEqual(connection.execute("SELECT status FROM interventions WHERE id='existing-int'").fetchone()[0], "COMPLETED")
            self.assertIn("procedure_version_id", {row[1] for row in connection.execute("PRAGMA table_info(interventions)")})
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM procedures").fetchone()[0], 1)
            connection.close()

    def test_legacy_payload_matches_unity_fields_without_fabricated_pose(self):
        payload = sanitize_procedure_for_unity({
            "machine_id": "SYNTH-UNIT",
            "machine_name": "Synthetic unit",
            "status": "APPROVED",
            "workflow_stages": {
                "lockout": [{"stage_id": 1, "title": "Isolation", "actions": [{"action_id": "a1", "description": "Operator confirms isolation"}]}],
                "restoration": [],
            },
            "anchors": {"un-calibrated": {"pos_x": 0.1}},
        })
        self.assertEqual(set(payload), {"machine_id", "machine_name", "created_by_hse", "status", "procedure_version_id", "schema_version", "maintenance_objective", "workflow_json", "workflow_stages", "anchors"})
        self.assertEqual(payload["procedure_version_id"], "")
        self.assertEqual(set(payload["workflow_stages"]), {"lockout", "restoration"})
        action = payload["workflow_stages"]["lockout"][0]["actions"][0]
        self.assertEqual(set(action), {"action_id", "description", "vision_prompt", "completion_check", "spatial_guide"})
        self.assertIsNone(action["spatial_guide"])
        self.assertEqual(payload["anchors"], [])

    def test_canonical_v2_keeps_arbitrary_phases_methods_and_source_payload(self):
        canonical = {
            "schema_version": "2.0",
            "maintenance_objective": "Inspect synthetic assembly",
            "phases": [{"phase_id": "phase-test", "phase_type": "inspection", "sequence": 1, "title": "Inspection", "stages": [{"stage_id": "stage-test", "sequence": 1, "title": "Review", "steps": [{"step_id": "step-test", "sequence": 1, "instruction": "Operator checks condition", "basis": "reasoning_to_review", "verification": {"method": "human_confirmation", "criteria": ["Operator records result"], "required_evidence": ["Operator note"], "indeterminate_when": ["Condition unclear"]}}]}]}],
            "technical_facts": [{"fact_id": "fact-test", "qualification": "documented", "source_quote": "Synthetic quoted statement"}],
        }
        payload = sanitize_procedure_for_unity({"machine_id": "SYNTH", "workflow_stages": canonical})
        self.assertEqual(payload["workflow_stages"]["phases"][0]["phase_type"], "inspection")
        self.assertEqual(payload["workflow_stages"]["phases"][0]["stages"][0]["stage_code"], "stage-test")
        self.assertEqual(payload["workflow_stages"]["technical_facts"], canonical["technical_facts"])
        self.assertEqual(json.loads(payload["workflow_json"]), canonical)
        step = payload["workflow_stages"]["phases"][0]["stages"][0]["steps"][0]
        self.assertEqual(step["verification"]["method"], "human_confirmation")
        self.assertEqual(payload["anchors"], [])

    def test_missing_equipment_id_is_not_replaced_with_placeholder(self):
        with self.assertRaises(HTTPException) as context:
            sanitize_procedure_for_unity({"workflow_stages": {}})
        self.assertEqual(context.exception.status_code, 422)

    def test_intervention_starts_only_on_published_revision_and_stays_pinned(self):
        with tempfile.TemporaryDirectory(prefix="smartloto-field-test-") as directory:
            db_path = Path(directory) / "field.sqlite"
            client = LocalSQLiteClient(str(db_path))
            connection = sqlite3.connect(db_path)
            connection.execute("""CREATE TABLE procedure_versions (
                id TEXT PRIMARY KEY, procedure_id TEXT, version_number INTEGER,
                status TEXT, workflow_definition TEXT)""")
            workflow_one = {"lockout": [], "restoration": []}
            connection.execute(
                "INSERT INTO procedures(machine_id,machine_name,created_by_hse,status,workflow_stages) VALUES(?,?,?,?,?)",
                ("SYNTH-PIN", "Synthetic pinned equipment", "test-author", "PUBLISHED", json.dumps({"_active_version_id": "v1"})),
            )
            connection.executemany(
                "INSERT INTO procedure_versions(id,procedure_id,version_number,status,workflow_definition) VALUES(?,?,?,?,?)",
                [("v1", "SYNTH-PIN", 1, "published", json.dumps(workflow_one)),
                 ("v2", "SYNTH-PIN", 2, "draft_pending_review", json.dumps({"lockout": [], "restoration": [{"stage_id": 2, "title": "New revision", "actions": []}]}))],
            )
            connection.commit()
            connection.close()
            previous_db = database.db
            database.db = client
            try:
                started = asyncio.run(start_intervention(StartIntervention(
                    machine_id="SYNTH-PIN", operator_name="Synthetic operator"
                )))
                self.assertEqual(started["intervention"]["procedure_version_id"], "v1")

                connection = sqlite3.connect(db_path)
                connection.execute("UPDATE procedure_versions SET status='superseded' WHERE id='v1'")
                connection.execute("UPDATE procedure_versions SET status='published' WHERE id='v2'")
                connection.execute(
                    "UPDATE procedures SET workflow_stages=? WHERE machine_id=?",
                    (json.dumps({"_active_version_id": "v2"}), "SYNTH-PIN"),
                )
                connection.commit()
                connection.close()

                fetched = asyncio.run(get_procedure("SYNTH-PIN", version_id="v1"))
                self.assertEqual(fetched["procedure_version_id"], "v1")
                self.assertEqual(fetched["workflow_stages"]["lockout"], workflow_one["lockout"])
            finally:
                database.db = previous_db


if __name__ == "__main__":
    unittest.main()
