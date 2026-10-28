"""Closure preserves Unity payloads and persists both signature provenance and PDF."""
import asyncio
import base64
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer

import app.database as database
from app.api.interventions import close_intervention
from app.database import LocalSQLiteClient
from app.models import CloseIntervention
from app.services.pdf import generate_audit_report
from app.services.signatures import operator_signature


class ReportSignatureTests(unittest.TestCase):
    def test_signatures_are_side_by_side_and_long_audit_keeps_them_together(self):
        record, picture = operator_signature({'id': 'test', 'operator_name': 'JALIL'}, '2026-10-28T10:30:00+00:00', None)
        data = {'id': 'test', 'machine_id': 'demo', 'operator_name': 'JALIL', 'completed_at': record['signed_at'],
                'operator_signature': record, 'procedure_version_id': 'pinned',
                'hse_signature': {'name': 'HSE Reviewer', 'reviewer_id': 'hse_reviewer@smartloto.io',
                                  'role': 'Responsable HSE', 'signed_at': '2026-10-27T09:00:00+00:00', 'sha256': 'a' * 64},
                'logs': [{'timestamp': '2026-10-28T10:00:00', 'stage_id': 1, 'type': 'human_confirmation',
                          'action_description': f'Action {i}: confirmed'} for i in range(60)]}
        pdf = generate_audit_report(data, 'Synthetic machine', picture)
        text = extract_text(io.BytesIO(pdf))
        for expected in ['Signatures & Validation de Conformit', 'hse_reviewer@smartloto.io', 'JALIL', '28/10/2026', 'SHA-256']:
            self.assertIn(expected, text)
        pages = list(extract_pages(io.BytesIO(pdf)))
        last_text = [item for item in pages[-1] if isinstance(item, LTTextContainer)]
        left = next(item for item in last_text if 'Approbation Proc' in item.get_text())
        right = next(item for item in last_text if 'Exécution' in item.get_text())
        self.assertLess(left.x0, right.x0)
        self.assertAlmostEqual(left.y1, right.y1, delta=3)

    def test_closure_persists_signature_on_pinned_version_with_unchanged_response(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'field.sqlite'
            client = LocalSQLiteClient(str(path))
            connection = sqlite3.connect(path)
            connection.execute('CREATE TABLE audit_events(id TEXT, machine_id TEXT, event_type TEXT, payload TEXT)')
            connection.execute("INSERT INTO procedures(machine_id,machine_name,created_by_hse,workflow_stages) VALUES('demo','Synthetic','author','{}')")
            connection.execute("INSERT INTO interventions(id,machine_id,procedure_version_id,operator_name) VALUES('int','demo','pinned','JALIL')")
            for version, name in [('pinned', 'Correct HSE'), ('later-version', 'Wrong reviewer')]:
                payload = {'version_id': version, 'signature': {'name': name, 'signed_at': '2026-10-27T09:00:00+00:00', 'sha256': 'b' * 64}}
                connection.execute('INSERT INTO audit_events VALUES(?,?,?,?)', (version, 'demo', 'PROCEDURE_APPROVED', json.dumps(payload)))
            connection.commit()
            connection.close()
            uploads = {}

            def upload(content, path, content_type):
                uploads[path] = content
                return 'http://local/storage/' + path

            buffer = io.BytesIO()
            Image.new('RGB', (180, 65), 'white').save(buffer, 'PNG')
            for image_base64, expected_status in [(base64.b64encode(buffer.getvalue()).decode(), 'captured'), ('', 'generated')]:
                with patch.object(database, 'db', client), patch('app.api.interventions.storage_service.upload_file', side_effect=upload):
                    result = asyncio.run(close_intervention(CloseIntervention(intervention_id='int', signature_base64=image_base64)))
                self.assertEqual(set(result), {'status', 'message', 'pdf_report_url'})
                stored = client.table('interventions').select('*').eq('id', 'int').execute().data[0]
                self.assertEqual(stored['status'], 'COMPLETED')
                signature = next(log['signature'] for log in stored['logs'] if log['type'] == 'operator_signature')
                self.assertEqual(signature['name'], 'JALIL')
                self.assertEqual(signature['status'], expected_status)
                self.assertEqual(signature['signed_at'], stored['completed_at'])
                self.assertEqual(len(signature['sha256']), 64)
                pdf = next(content for path, content in uploads.items() if path.endswith('.pdf'))
                text = extract_text(io.BytesIO(pdf))
                self.assertIn('Correct HSE', text)
                self.assertNotIn('Wrong reviewer', text)
                self.assertEqual(sum(log['type'] == 'operator_signature' for log in stored['logs']), 1)

    def test_legacy_report_never_fabricates_hse_approval(self):
        pdf = generate_audit_report({'id': 'old', 'operator_name': 'Legacy'}, 'Demo', None)
        self.assertIn('Signature non disponible', extract_text(io.BytesIO(pdf)))
