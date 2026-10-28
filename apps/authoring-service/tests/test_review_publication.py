"""Regression: actual dashboard save, resolve, sign and publish routes on isolated DB."""
import copy
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.api.procedures import update_draft, resolve_clarification, approve_procedure, publish_procedure, get_procedure, list_procedures
from app.schemas import DraftUpdatePayload, ResolveClarificationPayload, ApprovalCreatePayload
from app.services.confidence import confidence_breakdown
from test_workflow_validation import synthetic_draft


class ReviewPublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_citations_resolved_decision_and_signed_exact_revision_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory) / 'review.sqlite'}")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with sessions() as db:
                    wf = synthetic_draft()
                    wf['visual_observations'] = [{'observation_id': 'obs', 'description': 'Visible mark', 'component_refs': ['electric-feed']}]
                    wf['technical_facts'][0]['citation_status'] = 'unmatched'
                    wf['technical_facts'][1]['citation_status'] = 'inferred_absence'
                    wf['clarifications_required'] = [{'id': 'q', 'question': 'Confirm installed feed', 'status': 'unresolved',
                        'affected_step_ids': ['step-isolate'], 'related_component_ids': ['electric-feed']}]
                    saved = await update_draft(wf['machine_id'], DraftUpdatePayload(workflow_definition=wf), 'author', db)
                    await db.commit()
                    initial = confidence_breakdown(saved.workflow_definition)['score']
                    wf = copy.deepcopy(saved.workflow_definition)
                    before_criteria = copy.deepcopy(wf['phases'][0]['stages'][0]['steps'][0]['verification']['criteria'])
                    wf['technical_facts'][0].update(citation_status='manual_verified', citation_review={'verified_method': 'one_click_review'})
                    saved = await update_draft(wf['machine_id'], DraftUpdatePayload(workflow_definition=wf), 'reviewer', db)
                    resolved = await resolve_clarification(wf['machine_id'], ResolveClarificationPayload(
                        clarification_id='q', answer='Feed confirmed during review', rationale='Equipment record checked',
                        answer_complete=True, affected_steps_reviewed=True), 'reviewer', db)
                    await db.commit()
                    current = resolved.workflow_definition
                    self.assertGreater(confidence_breakdown(current)['score'], initial)
                    self.assertEqual(confidence_breakdown(current)['score'], 100)
                    self.assertIn('Feed confirmed', current['components'][0]['notes_for_reviewer'])
                    step = current['phases'][0]['stages'][0]['steps'][0]
                    self.assertIn('Feed confirmed', step['notes_for_reviewer'])
                    self.assertEqual(step['verification']['criteria'], before_criteria)
                    self.assertEqual(step['blocking_clarification_ids'], [])
                    self.assertEqual(current['technical_facts'][0]['citation_review']['reviewed_by'], 'reviewer')
                    before_approval = copy.deepcopy(current)
                    approval = await approve_procedure(wf['machine_id'], resolved.id, ApprovalCreatePayload(
                        version_id=resolved.id, decision='approved', approved_by='reviewer',
                        signature={'name': 'HSE Reviewer', 'accepted': True}), 'reviewer', db)
                    self.assertEqual(approval.signature['name'], 'HSE Reviewer')
                    self.assertEqual(len(approval.signature['sha256']), 64)
                    published = await publish_procedure(wf['machine_id'], resolved.id, 'reviewer', db)
                    await db.commit()
                    self.assertEqual(published.published_version_id, resolved.id)
                    detail = await get_procedure(wf['machine_id'], db)
                    self.assertEqual(detail.active_version.latest_approval.signature, approval.signature)
                    self.assertEqual(detail.active_version.workflow_definition, before_approval)
                    listing = await list_procedures(db=db)
                    self.assertEqual(listing.data[0].overall_confidence, 1)
                    self.assertEqual(listing.data[0].open_validation_errors, 0)
            finally:
                await engine.dispose()


class ConfidenceTests(unittest.TestCase):
    def test_three_pillar_parity_with_frontend_and_monotonic_resolution(self):
        wf = {
            'components': [{'physical_signatures': [{'description': 'Mark'}]}],
            'phases': [{'stages': [{'steps': [{'step_id': 'check'}]}]}],
            'technical_facts': [{'citation_status': 'unmatched'}, {'citation_status': 'inferred_absence'}],
            'clarifications_required': [{'id': 'q', 'status': 'unresolved'}],
            'validation_diagnostics': [{'code': 'CLARIFICATION_OPEN', 'severity': 'blocking', 'entity_id': 'q'}],
        }
        self.assertEqual(confidence_breakdown(wf)['score'], 86)
        wf['clarifications_required'][0].update(status='resolved', affected_steps_reviewed=True,
                                               resolution={'answer': 'Decision', 'answer_complete': True})
        self.assertEqual(confidence_breakdown(wf)['score'], 90)
        wf['technical_facts'][0]['citation_status'] = 'manual_verified'
        self.assertEqual(confidence_breakdown(wf), {'score': 100, 'breakdown': {
            'structureScore': 60, 'blockingScore': 20, 'citationScore': 20,
            'blockingCount': 0, 'unmatchedCount': 0, 'totalFacts': 2}})

    def test_partial_answers_and_stale_diagnostics(self):
        wf = synthetic_draft()
        wf['clarifications_required'] = [{'id': 'q', 'status': 'resolved', 'resolution': {'answer': 'Partial'}}]
        wf['validation_diagnostics'] = [{'code': 'CLARIFICATION_OPEN', 'severity': 'blocking', 'entity_id': 'q'}]
        self.assertEqual(confidence_breakdown(wf)['breakdown']['blockingCount'], 1)
        wf['clarifications_required'][0].update(affected_steps_reviewed=True, resolution={'answer': 'Complete', 'answer_complete': True})
        self.assertEqual(confidence_breakdown(wf)['breakdown']['blockingCount'], 0)
        problem = {'code': 'MISSING_CRITERION', 'severity': 'blocking', 'entity_id': 'step-isolate'}
        wf['validation_diagnostics'].append(problem)
        wf['phases'][0]['stages'][0]['steps'][0]['diagnostics'] = [problem]
        self.assertEqual(confidence_breakdown(wf)['breakdown']['blockingCount'], 1)
