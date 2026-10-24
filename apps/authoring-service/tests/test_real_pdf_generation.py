"""Test real PDF generation with Groq using the project's reference PDF."""

import asyncio
import io
import time
import unittest
from pathlib import Path

from fastapi import UploadFile

from app.config import DOCUMENT_GENERATION_PROVIDER, GROQ_API_KEY
from app.database import AsyncSessionLocal, init_db
from app.models import DocumentGenerationJob
from app.services import document_generation_service as generation


class RealPdfGenerationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()

    async def test_real_pdf_processing_with_groq(self):
        if not GROQ_API_KEY:
            self.skipTest("GROQ_API_KEY non configurée")

        pdf_path = Path("apps/authoring-service/data/reference/SmartLOTO_SL-POC-01_Dossier_Technique_Descriptif.pdf")
        if not pdf_path.is_file():
            # Fallback path if run from authoring-service dir
            pdf_path = Path("data/reference/SmartLOTO_SL-POC-01_Dossier_Technique_Descriptif.pdf")
        if not pdf_path.is_file():
            self.skipTest(f"Fichier PDF introuvable à {pdf_path}")

        pdf_bytes = pdf_path.read_bytes()
        print(f"\n[REAL TEST] Taille PDF: {len(pdf_bytes)} octets, Fournisseur: {DOCUMENT_GENERATION_PROVIDER}")

        t0 = time.time()
        # Démarre le worker
        await generation.start_worker()
        try:
            upload_file = UploadFile(filename=pdf_path.name, file=io.BytesIO(pdf_bytes))
            res = await generation.accept_pdf(upload_file, "real-test-engineer")
            job_id = res["job_id"]
            print(f"[REAL TEST] Tâche soumise : job_id={job_id}, status={res['status']}")

            # Attente de la fin du traitement avec timeout de 60s (Groq est très rapide)
            completed_job = None
            for _ in range(40):
                await asyncio.sleep(1.0)
                job = await generation.get_job(job_id, "real-test-engineer")
                if job and job["status"] in {"succeeded", "failed"}:
                    completed_job = job
                    break

            elapsed = round(time.time() - t0, 2)
            print(f"[REAL TEST] Temps total : {elapsed}s")
            self.assertIsNotNone(completed_job, "Le traitement a dépassé le délai")
            print(f"[REAL TEST] Statut final : {completed_job['status']}, étape : {completed_job['stage']}")
            if completed_job["status"] == "failed":
                print(f"[REAL TEST] Erreur : {completed_job.get('error')}")

            self.assertEqual(completed_job["status"], "succeeded")
            self.assertIsNotNone(completed_job["result"])
            print(f"[REAL TEST] Procédure créée : {completed_job['procedure_id']}, version: {completed_job['version_id']}")
            print(f"[REAL TEST] Timings : {completed_job['timings_ms']}")
        finally:
            await generation.stop_worker()


if __name__ == "__main__":
    unittest.main()
