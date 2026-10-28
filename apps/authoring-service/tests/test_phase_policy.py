import copy
import tempfile
from pathlib import Path
import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base
from app.models import ProcedureVersion
from app.services.phase_policy import normalize_draft_phases
from app.services.procedure_service import update_procedure_draft
from app.services.workflow_validation import validate_workflow
from test_workflow_validation import synthetic_draft


class PhasePolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_french_replacer_guard_means_restore_position_not_replace_component(self):
        from app.services.phase_policy import classify_step
        self.assertEqual(classify_step({"instruction": "Replacer le carter en position fermée."}, "restoration"), "restoration")
        self.assertEqual(classify_step({"instruction": "Replace the filter cartridge."}, "lockout"), "maintenance")
        self.assertEqual(classify_step({"instruction": "Déplacer le carter mobile pour dégager l'accès à la lampe."}, "consignation"), "maintenance")
        self.assertEqual(classify_step({"instruction": "Retirer la pile pour ouvrir le carter."}, "consignation"), "consignation")
        self.assertEqual(classify_step({"instruction": "Basculer l'interrupteur sur la position OFF"}, "preparation"), "consignation")
    def test_content_splits_mixed_phase_without_machine_or_step_identifiers(self):
        wf = synthetic_draft()
        steps = wf["phases"][0]["stages"][0]["steps"]
        steps[0]["instruction"] = "Retirer la source pour remplacer le filtre."
        steps[1]["instruction"] = "Remplacer la cartouche filtrante."
        steps[1]["verification"]["method"] = "visual_observation"
        wf["phases"][0]["phase_type"] = "ISOLATION"
        before = copy.deepcopy(wf)
        normalized = normalize_draft_phases(wf)
        self.assertEqual(wf, before)
        self.assertEqual([p["phase_type"] for p in normalized["phases"]], ["consignation", "maintenance"])
        maintenance = normalized["phases"][1]["stages"][0]["steps"][0]
        self.assertEqual(maintenance["verification"]["method"], "human_confirmation")
        self.assertEqual(maintenance["execution_phase"], "maintenance")
        self.assertTrue(maintenance["guidance"]["component_refs"])
        self.assertEqual(normalize_draft_phases(normalized), normalized)

    def test_human_work_does_not_require_artificial_camera_criteria(self):
        wf = synthetic_draft()
        step = wf["phases"][0]["stages"][0]["steps"][0]
        step["verification"] = {"method": "human_confirmation", "criteria": []}
        self.assertNotIn("VERIFICATION_CRITERIA_REQUIRED", {d["code"] for d in validate_workflow(wf) if d.get("entity_id") == step["step_id"]})

    async def test_save_reload_preserves_phase_validation_guidance_without_mutating_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = create_async_engine(f"sqlite+aiosqlite:///{Path(folder)/'test.db'}")
            async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
            try:
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with sessions() as db:
                    wf = synthetic_draft()
                    published = await update_procedure_draft(db, wf["machine_id"], wf, "test")
                    published.status = "published"; await db.commit()
                    original = copy.deepcopy(published.workflow_definition)
                    changed = copy.deepcopy(original)
                    step = changed["phases"][0]["stages"][0]["steps"][1]
                    step["instruction"] = "Remplacer le joint du filtre."
                    draft = await update_procedure_draft(db, wf["machine_id"], changed, "reviewer")
                    await db.commit(); draft_id = draft.id
                async with sessions() as db:
                    loaded = await db.get(ProcedureVersion, draft_id)
                    step = loaded.workflow_definition["phases"][-1]["stages"][0]["steps"][0]
                    self.assertEqual(step["execution_phase"], "maintenance")
                    self.assertEqual(step["verification"]["method"], "human_confirmation")
                    self.assertEqual(step["guidance"]["component_refs"], step["component_refs"])
                    old = await db.get(ProcedureVersion, published.id)
                    self.assertEqual(old.workflow_definition, original)
            finally: await engine.dispose()
