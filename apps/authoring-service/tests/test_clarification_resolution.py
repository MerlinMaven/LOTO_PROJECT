"""Decision answers never become facts/criteria; publication remains immutable."""
import copy
from pathlib import Path
import tempfile
import unittest

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.models import ProcedureVersion
from app.schemas import ResolveClarificationPayload
from app.api.procedures import resolve_clarification
from app.services.procedure_service import update_procedure_draft, get_procedure_by_id
from app.services.workflow_validation import apply_clarification_impact, validate_workflow
from test_workflow_validation import synthetic_draft


class ClarificationResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_gibberish_and_complete_answers_do_not_rewrite_published_criteria(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory)/'test.db'}")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with sessions() as db:
                    wf = synthetic_draft()
                    wf["clarifications_required"] = [{"id": "multi-part", "question": "Which voltage and other stored energy sources?",
                        "status": "unresolved", "affected_step_ids": ["step-measure"], "related_component_ids": ["electric-feed"]}]
                    version = await update_procedure_draft(db, wf["machine_id"], wf, "test")
                    version.status = "published"
                    proc = await get_procedure_by_id(db, wf["machine_id"])
                    proc.status = "PUBLISHED"; proc.active_version_id = version.id
                    before = copy.deepcopy(version.workflow_definition)
                    await db.commit()
                    for answer in ["jkgvvazddu", "3 V"]:
                        result = await resolve_clarification(wf["machine_id"], ResolveClarificationPayload(
                            clarification_id="multi-part", answer=answer), "test-reviewer", db)
                        await db.commit()
                        updated = result.workflow_definition
                        self.assertEqual(updated["clarifications_required"][0]["status"], "unresolved")
                        self.assertEqual(updated["phases"], apply_clarification_impact(copy.deepcopy(before))["phases"])
                        self.assertEqual(updated["technical_facts"], before["technical_facts"])
                        self.assertNotEqual(result.id, version.id)
                    completed = await resolve_clarification(wf["machine_id"], ResolveClarificationPayload(
                        clarification_id="multi-part", answer="Complete documented decision",
                        rationale="Document review and inspection recorded", answer_complete=True,
                        affected_steps_reviewed=True), "reviewer", db)
                    await db.commit()
                    self.assertEqual(completed.workflow_definition["clarifications_required"][0]["status"], "resolved")
                    self.assertEqual(completed.workflow_definition["technical_facts"], before["technical_facts"])
                    for old_phase, new_phase in zip(before["phases"], completed.workflow_definition["phases"]):
                        for old_stage, new_stage in zip(old_phase["stages"], new_phase["stages"]):
                            for old_step, new_step in zip(old_stage["steps"], new_stage["steps"]):
                                self.assertEqual(old_step["verification"]["criteria"], new_step["verification"]["criteria"])
                    await db.refresh(version)
                    await db.refresh(proc)
                    self.assertEqual(version.workflow_definition, before)
                    self.assertEqual(proc.active_version_id, version.id)
            finally:
                await engine.dispose()

    def test_draft_save_cannot_clear_a_partial_resolution_or_polluted_criterion(self):
        wf = synthetic_draft()
        wf["clarifications_required"] = [{"id": "partial", "status": "resolved", "question": "Two-part question",
            "resolution": {"answer": "3 V"}, "affected_step_ids": ["step-measure"]}]
        step = wf["phases"][0]["stages"][0]["steps"][1]
        step["verification"]["criteria"].append("Critère validé : jkgvvazddu")
        apply_clarification_impact(wf)
        self.assertEqual(step["review_readiness"], "blocked")
        codes = {d["code"] for d in validate_workflow(wf)}
        self.assertIn("CLARIFICATION_REVIEW_INCOMPLETE", codes)
        self.assertIn("CLARIFICATION_COPIED_AS_CRITERION", codes)
