"""Tests for document generation, persistence, retries, and user isolation."""

import asyncio
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.models import DocumentGenerationJob
from app.services import document_generation_service as generation


class DocumentIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()

    def test_invalid_pdf_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            generation._extract_pdf(b"not a PDF", "invalid.pdf")
        self.assertEqual(error.exception.status_code, 415)

    async def test_duplicate_active_upload_reuses_job_id_without_second_run(self):
        content = b"%PDF-synthetic-duplicate-check"
        with tempfile.TemporaryDirectory(prefix="smartloto-ingestion-") as directory:
            previous_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                first = await generation.accept_pdf(
                    UploadFile(filename="dup.pdf", file=io.BytesIO(content)),
                    "synthetic-user-1"
                )
                second = await generation.accept_pdf(
                    UploadFile(filename="dup.pdf", file=io.BytesIO(content)),
                    "synthetic-user-1"
                )
                self.assertFalse(first["duplicate"])
                self.assertTrue(second["duplicate"])
                self.assertEqual(second["job_id"], first["job_id"])
            finally:
                generation.DOCUMENT_DIR = previous_dir

    async def test_user_isolation_prevent_cross_tenant_access(self):
        content = b"%PDF-synthetic-isolation-test"
        with tempfile.TemporaryDirectory(prefix="smartloto-isolation-") as directory:
            previous_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                created = await generation.accept_pdf(
                    UploadFile(filename="tenant_a.pdf", file=io.BytesIO(content)),
                    "user-tenant-a"
                )
                job_id = created["job_id"]
                # Owner can access
                job_a = await generation.get_job(job_id, "user-tenant-a")
                self.assertIsNotNone(job_a)
                self.assertEqual(job_a["job_id"], job_id)

                # Different user cannot access
                job_b = await generation.get_job(job_id, "user-tenant-b")
                self.assertIsNone(job_b)

                # Any owner check finds it
                any_owner_job = await generation.find_job_any_owner(job_id)
                self.assertIsNotNone(any_owner_job)
                self.assertEqual(any_owner_job.owner_id, "user-tenant-a")
            finally:
                generation.DOCUMENT_DIR = previous_dir

    async def test_retry_failed_job_uses_stored_pdf_without_reupload(self):
        content = b"%PDF-synthetic-retry-test"
        with tempfile.TemporaryDirectory(prefix="smartloto-retry-") as directory:
            previous_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                created = await generation.accept_pdf(
                    UploadFile(filename="retry.pdf", file=io.BytesIO(content)),
                    "user-retry-test"
                )
                job_id = created["job_id"]
                # Mark failed directly to simulate failure
                async with AsyncSessionLocal() as db:
                    job = await db.get(DocumentGenerationJob, job_id)
                    job.status = "failed"
                    job.error_message = "Simulation échec"
                    await db.commit()

                # Retry job
                retried = await generation.retry_job(job_id, "user-retry-test")
                self.assertFalse(retried["duplicate"])
                self.assertNotEqual(retried["job_id"], job_id)
                self.assertEqual(retried["status"], "queued")
                self.assertEqual(retried["source_filename"], "retry.pdf")

                # Cross-user retry is forbidden
                with self.assertRaises(HTTPException) as ctx:
                    await generation.retry_job(job_id, "different-user")
                self.assertEqual(ctx.exception.status_code, 403)
            finally:
                generation.DOCUMENT_DIR = previous_dir

    async def test_worker_restart_marks_running_jobs_interrupted(self):
        content = b"%PDF-synthetic-restart-test"
        with tempfile.TemporaryDirectory(prefix="smartloto-restart-") as directory:
            previous_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                created = await generation.accept_pdf(
                    UploadFile(filename="restart.pdf", file=io.BytesIO(content)),
                    "user-restart-test"
                )
                job_id = created["job_id"]
                # Set status to running
                async with AsyncSessionLocal() as db:
                    job = await db.get(DocumentGenerationJob, job_id)
                    job.status = "running"
                    job.stage = "analyzing"
                    await db.commit()

                # Simulate worker restart
                await generation.start_worker()
                await generation.stop_worker()

                # Verify job was marked failed with interruption message
                job_res = await generation.get_job(job_id, "user-restart-test")
                self.assertEqual(job_res["status"], "failed")
                self.assertTrue(job_res["can_retry"])
                self.assertIn("Le worker s’est arrêté", job_res["error"])
            finally:
                generation.DOCUMENT_DIR = previous_dir

    async def test_provider_failure_retries_then_fails_without_substitute_result(self):
        class Response:
            status_code = 503

            @staticmethod
            def json():
                return {"error": {"message": "synthetic provider outage"}}

        class Client:
            calls = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, *_args, **_kwargs):
                self.calls += 1
                return Response()

        client = Client()
        with patch.object(generation.httpx, "AsyncClient", return_value=client), patch.object(
            generation, "GEMINI_API_KEY", "test-only-placeholder"
        ), patch.object(generation.asyncio, "sleep", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Échec de l’analyse"):
                await generation._call_gemini(
                    b"synthetic pdf bytes",
                    {"pages": [{"page": 1, "text": "Synthetic input"}]},
                )
        self.assertEqual(client.calls, 3)

    async def test_provider_transient_read_timeout_is_retried(self):
        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

        class Client:
            calls = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise generation.httpx.ReadTimeout("temporary timeout")
                return Response()

        client = Client()
        with patch.object(generation.httpx, "AsyncClient", return_value=client), patch.object(
            generation, "GEMINI_API_KEY", "test-only-placeholder"
        ), patch.object(generation.asyncio, "sleep", return_value=None):
            result = await generation._call_gemini(
                b"synthetic pdf bytes", {"pages": [{"page": 1, "text": "Synthetic input"}]}
            )
        self.assertEqual(result, {})
        self.assertEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()
