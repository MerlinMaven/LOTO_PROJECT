"""API endpoint tests for document generation routes."""

import io
import tempfile
import unittest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.database import init_db
from app.main import create_app
from app.services import document_generation_service as generation


class GenerationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.app = create_app()

    async def test_full_api_workflow(self):
        content = b"%PDF-api-workflow-test"
        with tempfile.TemporaryDirectory(prefix="smartloto-api-") as directory:
            previous_dir = generation.DOCUMENT_DIR
            generation.DOCUMENT_DIR = Path(directory)
            try:
                transport = ASGITransport(app=self.app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 1. Reject non-PDF
                    bad_resp = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("text.txt", io.BytesIO(b"not pdf"), "text/plain")},
                        headers={"X-User-Id": "api-user-1"},
                    )
                    self.assertEqual(bad_resp.status_code, 415)

                    # 2. Submit valid PDF -> 202 with job_id
                    resp = await client.post(
                        "/v1/generation/documents",
                        files={"file": ("manual.pdf", io.BytesIO(content), "application/pdf")},
                        headers={"X-User-Id": "api-user-1"},
                    )
                    self.assertEqual(resp.status_code, 202)
                    data = resp.json()
                    self.assertIn("job_id", data)
                    job_id = data["job_id"]
                    self.assertEqual(data["status"], "queued")
                    self.assertFalse(data["duplicate"])

                    # 3. Read generation job as owner -> 200
                    job_resp = await client.get(
                        f"/v1/generation/jobs/{job_id}",
                        headers={"X-User-Id": "api-user-1"},
                    )
                    self.assertEqual(job_resp.status_code, 200)
                    job_data = job_resp.json()
                    self.assertEqual(job_data["job_id"], job_id)
                    self.assertEqual(job_data["source_filename"], "manual.pdf")

                    # 4. Read generation job as different user -> 403 Forbidden
                    forbidden_resp = await client.get(
                        f"/v1/generation/jobs/{job_id}",
                        headers={"X-User-Id": "intruder-user"},
                    )
                    self.assertEqual(forbidden_resp.status_code, 403)

                    # 5. List jobs for owner -> includes job_id
                    list_resp = await client.get(
                        "/v1/generation/jobs",
                        headers={"X-User-Id": "api-user-1"},
                    )
                    self.assertEqual(list_resp.status_code, 200)
                    jobs = list_resp.json()
                    self.assertTrue(any(j["job_id"] == job_id for j in jobs))

                    # 6. List jobs for intruder -> empty
                    intruder_list = await client.get(
                        "/v1/generation/jobs",
                        headers={"X-User-Id": "intruder-user"},
                    )
                    self.assertEqual(intruder_list.status_code, 200)
                    self.assertFalse(any(j["job_id"] == job_id for j in intruder_list.json()))

                    # 7. Download document -> 200 FileResponse
                    doc_id = job_data["document_id"]
                    doc_resp = await client.get(f"/v1/generation/documents/{doc_id}")
                    self.assertEqual(doc_resp.status_code, 200)
                    self.assertEqual(doc_resp.content, content)
            finally:
                generation.DOCUMENT_DIR = previous_dir


if __name__ == "__main__":
    unittest.main()
