"""
End-to-End simulation tests covering the 10 explicit criteria from the user prompt:
1. Launch generation, navigate away and back: same job retrievable.
2. Page refresh: tracking restored without re-submitting.
3. Tab close and reopen: job/result retrievable.
4. Completion while tab is closed: draft accessible upon return.
5. Double-click or duplicate submit: idempotency prevents duplicate run.
6. Simulated provider timeout: clean transition to 'failed' with actionable message and retry capability.
7. Temporary network disconnect: reconnects and queries without re-triggering generation.
8. Worker restart: running task marked interrupted, never abandoned indefinitely.
9. Tenant isolation: User B cannot access User A's jobs.
10. Absence of model / provider names in public job messages and responses.
"""

import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

from app.database import AsyncSessionLocal, init_db
from app.main import create_app
from app.models import DocumentGenerationJob
from app.services import document_generation_service as generation


class EndToEndScenarioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.app = create_app()

    async def test_scenarios_1_to_5_lifecycle_idempotency_and_recovery(self):
        """Covers:
        1. Navigate away & return -> same job retrieved from backend.
        2. Refresh page -> status fetched from /v1/generation/jobs without re-upload.
        3. Closed tab -> task continues independently.
        4. Completion while offline/unmounted -> result draft available.
        5. Double-click -> duplicate submit returns duplicate: true and same job_id.
        """
        import uuid
        uid = uuid.uuid4().hex[:8]
        content = f"%PDF-e2e-simulation-content-{uid}".encode("ascii")
        user_id = f"engineer-{uid}"
        with tempfile.TemporaryDirectory(prefix="smartloto-e2e-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                transport = ASGITransport(app=self.app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 5. First submission
                    res1 = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("guide.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": user_id, "X-Idempotency-Key": f"click-{uid}"},
                    )
                    self.assertEqual(res1.status_code, 202)
                    data1 = res1.json()
                    job_id = data1["job_id"]
                    self.assertFalse(data1["duplicate"])

                    # 5. Immediate duplicate click / submission with same file or idempotency key
                    res2 = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("guide.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": user_id, "X-Idempotency-Key": f"click-{uid}"},
                    )
                    self.assertEqual(res2.status_code, 202)
                    data2 = res2.json()
                    self.assertTrue(data2["duplicate"])
                    self.assertEqual(data2["job_id"], job_id)

                    # 1 & 2. "Leaving page / refreshing": frontend just calls GET /v1/generation/jobs
                    list_res = await client.get("/v1/generation/jobs", headers={"X-User-Id": user_id})
                    self.assertEqual(list_res.status_code, 200)
                    jobs = list_res.json()
                    found = next((j for j in jobs if j["job_id"] == job_id), None)
                    self.assertIsNotNone(found)
                    self.assertEqual(found["status"], "queued")

                    # 3 & 4. Simulating backend completion while user is away
                    async with AsyncSessionLocal() as db:
                        job = await db.get(DocumentGenerationJob, job_id)
                        job.status = "succeeded"
                        job.stage = "succeeded"
                        job.result = {
                            "job_id": job_id,
                            "procedure_id": "PUMP-99",
                            "workflow_definition": {"machine_id": "PUMP-99", "machine_name": "Pompe A"},
                        }
                        await db.commit()

                    # User reopens page / tab:
                    reopen_res = await client.get(f"/v1/generation/jobs/{job_id}", headers={"X-User-Id": user_id})
                    self.assertEqual(reopen_res.status_code, 200)
                    reopen_data = reopen_res.json()
                    self.assertEqual(reopen_data["status"], "succeeded")
                    self.assertIsNotNone(reopen_data["result"])
                    self.assertEqual(reopen_data["result"]["procedure_id"], "PUMP-99")
            finally:
                generation.DOCUMENT_DIR = prev_dir

    async def test_scenario_6_simulated_provider_timeout(self):
        """Simulate provider timeout: job exits running state and gives usable error message and retry."""
        content = b"%PDF-timeout-simulation"
        with tempfile.TemporaryDirectory(prefix="smartloto-timeout-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                created = await generation.accept_pdf(
                    generation.UploadFile(filename="timeout.pdf", file=io.BytesIO(content)),
                    "timeout-user"
                )
                job_id = created["job_id"]

                # Simulate timeout exception in worker
                await generation._mark_failed(job_id, asyncio.TimeoutError("timeout exceeded"))

                job = await generation.get_job(job_id, "timeout-user")
                self.assertEqual(job["status"], "failed")
                self.assertEqual(job["stage"], "failed")
                self.assertTrue(job["can_retry"])
                self.assertIn("délai maximal", job["error"])
            finally:
                generation.DOCUMENT_DIR = prev_dir

    async def test_scenario_7_network_disconnect_simulation(self):
        """Simulate browser dropping connection: server task state stays valid and reconnects seamlessly."""
        content = b"%PDF-network-drop-simulation"
        with tempfile.TemporaryDirectory(prefix="smartloto-net-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                transport = ASGITransport(app=self.app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    res = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("net.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": "net-user"},
                    )
                    job_id = res.json()["job_id"]

                    # Suppose client experiences network errors (no calls for a while).
                    # Server state is undisturbed.
                    # Reconnect:
                    check = await client.get(f"/v1/generation/jobs/{job_id}", headers={"X-User-Id": "net-user"})
                    self.assertEqual(check.status_code, 200)
                    self.assertEqual(check.json()["job_id"], job_id)
            finally:
                generation.DOCUMENT_DIR = prev_dir

    async def test_scenario_8_worker_restart_during_task(self):
        """Running task is marked interrupted with clear message, never left running forever."""
        content = b"%PDF-restart-scenario"
        with tempfile.TemporaryDirectory(prefix="smartloto-restart-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                created = await generation.accept_pdf(
                    generation.UploadFile(filename="restart.pdf", file=io.BytesIO(content)),
                    "restart-user"
                )
                job_id = created["job_id"]
                # Claim job into running
                await generation._claim_job(job_id)

                # Worker restarts
                await generation.start_worker()
                await generation.stop_worker()

                # Status must be failed with clear message
                job = await generation.get_job(job_id, "restart-user")
                self.assertEqual(job["status"], "failed")
                self.assertTrue(job["can_retry"])
                self.assertIn("Le worker s’est arrêté", job["error"])
            finally:
                generation.DOCUMENT_DIR = prev_dir

    async def test_scenario_9_tenant_isolation(self):
        """Tasks of User A cannot be accessed or retried by User B."""
        content = b"%PDF-isolation-scenario"
        with tempfile.TemporaryDirectory(prefix="smartloto-iso-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                transport = ASGITransport(app=self.app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    res = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("private.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": "alice@company.com"},
                    )
                    job_id = res.json()["job_id"]

                    # Bob attempts to get job -> 403 Forbidden
                    bob_res = await client.get(
                        f"/v1/generation/jobs/{job_id}",
                        headers={"X-User-Id": "bob@company.com"},
                    )
                    self.assertEqual(bob_res.status_code, 403)

                    # Bob attempts to retry job -> 403 Forbidden
                    bob_retry = await client.post(
                        f"/v1/generation/jobs/{job_id}/retry",
                        headers={"X-User-Id": "bob@company.com"},
                    )
                    self.assertEqual(bob_retry.status_code, 403)
            finally:
                generation.DOCUMENT_DIR = prev_dir

    async def test_scenario_10_absence_of_model_name_in_public_interface(self):
        """Verify that provider and model names (Gemini, Groq, gemini-3.8-flash, etc.) do not leak in public messages."""
        content = b"%PDF-leak-check"
        with tempfile.TemporaryDirectory(prefix="smartloto-leak-") as directory:
            prev_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                transport = ASGITransport(app=self.app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    res = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("check.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": "user-leak-check"},
                    )
                    job_data = res.json()

                    # Check public fields
                    for field in ("message", "stage", "status"):
                        val = str(job_data.get(field) or "").lower()
                        for forbidden in ("gemini", "groq", "flash", "modèle serveur", "analyse réelle"):
                            self.assertNotIn(forbidden, val)

                    # Simulate error
                    job_id = job_data["job_id"]
                    await generation._mark_failed(job_id, RuntimeError("Internal error with Groq model qwen3.8-27b"))
                    failed_res = await client.get(f"/v1/generation/jobs/{job_id}", headers={"X-User-Id": "user-leak-check"})
                    err_msg = failed_res.json().get("error", "").lower()
                    self.assertNotIn("groq", err_msg)
                    self.assertNotIn("gemini", err_msg)
            finally:
                generation.DOCUMENT_DIR = prev_dir


if __name__ == "__main__":
    unittest.main()
