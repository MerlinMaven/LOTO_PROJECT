"""Isolated persistence and exact-revision lifecycle tests (synthetic data only)."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AuditEvent, Procedure, ProcedureVersion
from app.services.procedure_service import (
    approve_procedure_version,
    publish_procedure,
    restore_published_revision_pointers,
    update_procedure_draft,
)


class ProcedureLifecycleTests(unittest.TestCase):
    def test_migration_recovers_only_audited_publication_and_preserves_content(self):
        async def scenario():
            with tempfile.TemporaryDirectory(prefix="smartloto-migration-") as directory:
                engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory) / 'isolated.sqlite'}")
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                try:
                    async with sessions() as db:
                        procedure = Procedure(machine_id="SYNTH-MIGRATION", machine_name="Synthetic equipment", status="APPROVED", workflow_stages={"legacy": "keep"})
                        version = ProcedureVersion(procedure_id="SYNTH-MIGRATION", version_number=3, status="published", workflow_definition={"schema_version": "1.0", "lockout": [], "restoration": []}, created_by="test")
                        db.add_all([procedure, version])
                        await db.flush()
                        db.add(AuditEvent(event_type="PROCEDURE_PUBLISHED", actor_id="test-publisher", machine_id="SYNTH-MIGRATION", procedure_id="SYNTH-MIGRATION", payload={"version_id": version.id}))
                        await db.commit()
                        repaired = await restore_published_revision_pointers(db)
                        await db.commit()
                        self.assertEqual(repaired, 1)
                        self.assertEqual(procedure.status, "PUBLISHED")
                        self.assertEqual(procedure.active_version_id, version.id)
                        self.assertEqual(procedure.workflow_stages["schema_version"], "1.0")
                        self.assertNotIn("legacy", procedure.workflow_stages)
                finally:
                    await engine.dispose()

        asyncio.run(scenario())

    def test_approval_and_publication_pin_exact_revision_and_keep_history(self):
        async def scenario():
            with tempfile.TemporaryDirectory(prefix="smartloto-lifecycle-") as directory:
                db_path = Path(directory) / "isolated.sqlite"
                engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                try:
                    async with sessions() as db:
                        workflow = {
                            "schema_version": "1.0",
                            "machine_id": "SYNTH-LIFECYCLE-A",
                            "machine_name": "Synthetic lifecycle equipment",
                            "lockout": [], "restoration": [],
                        }
                        first = await update_procedure_draft(
                            db, workflow["machine_id"], workflow, "test-author"
                        )
                        await db.commit()
                        with self.assertRaisesRegex(ValueError, "approuv"):
                            await publish_procedure(
                                db, workflow["machine_id"], first.id, "test-publisher"
                            )

                        approval = await approve_procedure_version(
                            db, workflow["machine_id"], first.id,
                            "test-reviewer", "approved", "Synthetic test decision",
                        )
                        await db.commit()
                        self.assertEqual(approval.version_id, first.id)

                        procedure, published = await publish_procedure(
                            db, workflow["machine_id"], first.id, "test-publisher"
                        )
                        await db.commit()
                        active_version_id = procedure.active_version_id
                        self.assertEqual(procedure.status, "PUBLISHED")
                        self.assertEqual(active_version_id, first.id)
                        self.assertEqual(published.status, "published")

                        next_draft = dict(workflow, maintenance_objective="A later synthetic objective")
                        second = await update_procedure_draft(
                            db, workflow["machine_id"], next_draft, "test-author"
                        )
                        await db.commit()
                        stored_first = await db.get(ProcedureVersion, first.id)
                        self.assertEqual(stored_first.status, "published")
                        self.assertEqual(stored_first.workflow_definition, workflow)
                        self.assertEqual(procedure.active_version_id, active_version_id)
                        self.assertEqual(second.status, "draft_pending_review")

                        events = (await db.execute(select(AuditEvent).order_by(AuditEvent.created_at))).scalars().all()
                        approval_event = next(e for e in events if e.event_type == "PROCEDURE_APPROVED")
                        publication_event = next(e for e in events if e.event_type == "PROCEDURE_PUBLISHED")
                        self.assertEqual(approval_event.payload["version_id"], first.id)
                        self.assertEqual(approval_event.actor_id, "test-reviewer")
                        self.assertEqual(publication_event.payload["version_id"], first.id)
                        self.assertEqual(publication_event.actor_id, "test-publisher")
                finally:
                    await engine.dispose()

        asyncio.run(scenario())

    def test_approval_targets_requested_version_and_refuses_another_equipment(self):
        async def scenario():
            with tempfile.TemporaryDirectory(prefix="smartloto-lifecycle-") as directory:
                engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory) / 'isolated.sqlite'}")
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                try:
                    async with sessions() as db:
                        workflow = {"schema_version": "1.0", "machine_id": "SYNTH-A", "lockout": [], "restoration": []}
                        first = await update_procedure_draft(db, "SYNTH-A", workflow, "author")
                        second = await update_procedure_draft(db, "SYNTH-A", workflow, "author")
                        first.status = "rejected"
                        await db.commit()
                        with self.assertRaisesRegex(ValueError, "attente"):
                            await approve_procedure_version(db, "SYNTH-A", first.id, "reviewer", "approved")
                        with self.assertRaisesRegex(ValueError, "introuvable"):
                            await approve_procedure_version(db, "SYNTH-B", second.id, "reviewer", "approved")
                finally:
                    await engine.dispose()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
