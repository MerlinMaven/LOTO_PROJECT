"""
InterventionService — orchestrates the intervention lifecycle.

The intervention is the runtime execution of a procedure.

Key invariants enforced here:
1. Only ONE active intervention per machine at a time.
2. The procedure version is pinned at start — never changes mid-intervention.
3. Abort is always allowed (emergency stop); complete requires all steps done.
4. Every state change produces an AuditEvent.
5. Only PUBLISHED procedures can be loaded.
6. No LLM calls — runtime is fully deterministic.

Phase 5 validation path:  manual confirmation via ValidationEngine.
Phase 6 will swap in YOLOWorldDetectionStrategy without touching this class.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import (
    InterventionNotActiveError,
    InterventionStepsIncompleteError,
    MachineAlreadyInInterventionError,
    NoActiveVersionError,
    NotFoundError,
    StepAlreadyCompletedError,
)
from app.core.logging import get_logger
from app.domain.enums import (
    AuditEventType,
    InterventionStatus,
    StepStatus,
    ValidationMethod,
)
from app.domain.runtime_state_machine import (
    validate_intervention_transition,
    validate_step_transition,
)
from app.models.intervention import Intervention, InterventionStep
from app.repositories.intervention_repository import InterventionRepository
from app.repositories.procedure_repository import ProcedureRepository
from app.runtime.validation_engine import ValidationContext, ValidationEngine
from app.schemas.intervention import (
    CurrentStepContext,
    InterventionCreate,
    InterventionProgress,
    InterventionRead,
    InterventionStepRead,
    StepOverrideRequest,
    StepRejectRequest,
    StepValidationRequest,
)
from app.services.audit_service import AuditService
from app.services.ports.vision_service import VisionService

logger = get_logger(__name__)

_engine = ValidationEngine()


class InterventionService:
    def __init__(
        self,
        intervention_repo: InterventionRepository,
        procedure_repo: ProcedureRepository,
        audit_service: AuditService,
        vision_service: VisionService,
    ) -> None:
        self.repo = intervention_repo
        self.procedure_repo = procedure_repo
        self.audit = audit_service
        self.vision = vision_service   # Phase 6: injected YOLOWorldVisionService

    # ── Start ─────────────────────────────────────────────────────────────────

    async def start_intervention(
        self,
        data: InterventionCreate,
        *,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Start a new intervention on a machine.

        Checks:
        - Machine must have a published procedure (status = PUBLISHED).
        - No other active intervention on this machine.
        """
        procedure = await self.procedure_repo.get_by_machine_id(data.machine_id)
        if not procedure or not procedure.active_version_id:
            raise NoActiveVersionError(data.machine_id)

        active_version = await self.procedure_repo.get_published_version(procedure.id)
        if not active_version:
            raise NoActiveVersionError(data.machine_id)

        existing = await self.repo.get_active_for_machine(data.machine_id)
        if existing:
            raise MachineAlreadyInInterventionError(data.machine_id)

        first_step_ref = self._extract_first_step_ref(active_version.workflow_definition)

        intervention = Intervention(
            procedure_version_id=active_version.id,
            machine_id=data.machine_id,
            operator_name=data.operator_name,
            status=InterventionStatus.IN_PROGRESS,
            current_step_ref=first_step_ref,
            started_at=datetime.now(timezone.utc),
        )
        intervention = await self.repo.create(intervention)

        await self.audit.record_event(
            AuditEventType.INTERVENTION_STARTED,
            actor_id=data.operator_name,
            machine_id=data.machine_id,
            intervention_id=intervention.id,
            procedure_version_id=active_version.id,
            payload={
                "operator_name": data.operator_name,
                "procedure_version": active_version.version_number,
                "first_step_ref": first_step_ref,
            },
            ip_address=ip_address,
        )

        logger.info(
            "intervention_started",
            intervention_id=str(intervention.id),
            machine_id=str(data.machine_id),
            operator=data.operator_name,
        )

        return await self._get_read(intervention.id)

    # ── Pause / Resume ────────────────────────────────────────────────────────

    async def pause_intervention(
        self,
        intervention_id: UUID,
        reason: str | None = None,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """Temporarily suspend an in-progress intervention (e.g. shift change)."""
        intervention = await self._get_active_intervention(intervention_id)
        validate_intervention_transition(intervention.status, InterventionStatus.PAUSED)

        intervention.status = InterventionStatus.PAUSED

        await self.audit.record_event(
            AuditEventType.INTERVENTION_PAUSED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            procedure_version_id=intervention.procedure_version_id,
            payload={
                "reason": reason,
                "current_step_ref": intervention.current_step_ref,
            },
            ip_address=ip_address,
        )

        logger.info(
            "intervention_paused",
            intervention_id=str(intervention_id),
            reason=reason,
        )
        return await self._get_read(intervention_id)

    async def resume_intervention(
        self,
        intervention_id: UUID,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """Resume a paused intervention."""
        intervention = await self._get_active_intervention(intervention_id)
        validate_intervention_transition(intervention.status, InterventionStatus.IN_PROGRESS)

        intervention.status = InterventionStatus.IN_PROGRESS

        await self.audit.record_event(
            AuditEventType.INTERVENTION_RESUMED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            procedure_version_id=intervention.procedure_version_id,
            payload={"current_step_ref": intervention.current_step_ref},
            ip_address=ip_address,
        )

        logger.info("intervention_resumed", intervention_id=str(intervention_id))
        return await self._get_read(intervention_id)

    # ── Step navigation ───────────────────────────────────────────────────────

    async def enter_step(
        self,
        intervention_id: UUID,
        step_ref: str,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Mark a step as in-progress and set it as the current step.

        Creates an InterventionStep record on first entry; increments attempts
        if the step record already exists (operator retrying after a failed attempt).
        """
        intervention = await self._get_active_intervention(intervention_id)

        now = datetime.now(timezone.utc)
        step = await self.repo.get_step(intervention_id, step_ref)
        if step:
            validate_step_transition(step.status, StepStatus.IN_PROGRESS)
            step.status = StepStatus.IN_PROGRESS
            if not step.started_at:
                step.started_at = now
            step.attempts += 1
        else:
            step = InterventionStep(
                intervention_id=intervention_id,
                step_ref=step_ref,
                status=StepStatus.IN_PROGRESS,
                started_at=now,
                attempts=1,
            )
            await self.repo.add_step(step)

        intervention.current_step_ref = step_ref

        await self.audit.record_event(
            AuditEventType.STEP_ENTERED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            step_ref=step_ref,
            payload={"operator": actor_id or intervention.operator_name},
            ip_address=ip_address,
        )

        return await self._get_read(intervention_id)

    # ── Step validation ───────────────────────────────────────────────────────

    async def validate_step(
        self,
        intervention_id: UUID,
        step_ref: str,
        data: StepValidationRequest,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Validate a step via the ValidationEngine strategy pattern.

        In Phase 5, the only available strategy is ManualConfirmationStrategy.
        Vision/sensor stubs return requires_override=True — the caller should
        direct the operator to the /override endpoint for those step types.
        """
        intervention = await self._get_active_intervention(intervention_id)

        wf = intervention.procedure_version.workflow_definition
        step_data = self._find_workflow_step(wf, step_ref) or {}
        method = _engine.get_method_for_step(step_data)

        ctx = ValidationContext(
            step_ref=step_ref,
            step_data=step_data,
            operator_id=data.confirmed_by,
            notes=data.notes,
        )
        result = await _engine.validate(method, ctx)

        now = datetime.now(timezone.utc)
        step = await self.repo.get_step(intervention_id, step_ref)
        if step:
            validate_step_transition(step.status, StepStatus.VALIDATED)
            step.status = StepStatus.VALIDATED
            step.validation_method_used = ValidationMethod.MANUAL_OVERRIDE
            step.completed_at = now
        else:
            step = InterventionStep(
                intervention_id=intervention_id,
                step_ref=step_ref,
                status=StepStatus.VALIDATED,
                validation_method_used=ValidationMethod.MANUAL_OVERRIDE,
                started_at=now,
                completed_at=now,
                attempts=1,
            )
            await self.repo.add_step(step)

        # Advance current_step_ref to the next step automatically.
        next_ref = self._extract_next_step_ref(wf, step_ref)
        intervention.current_step_ref = next_ref

        await self.audit.record_event(
            AuditEventType.STEP_VALIDATED_MANUAL,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            step_ref=step_ref,
            payload={
                "confirmed_by": data.confirmed_by,
                "method": method,
                "notes": data.notes,
                "validation_success": result.success,
                "next_step_ref": next_ref,
            },
            ip_address=ip_address,
        )
        return await self._get_read(intervention_id)

    async def reject_step(
        self,
        intervention_id: UUID,
        step_ref: str,
        data: StepRejectRequest,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Mark a step as failed.

        The step can be retried via enter_step (FAILED → IN_PROGRESS is valid).
        Useful when the operator finds the machine in an unexpected state.
        """
        intervention = await self._get_active_intervention(intervention_id)
        now = datetime.now(timezone.utc)

        step = await self.repo.get_step(intervention_id, step_ref)
        if step:
            validate_step_transition(step.status, StepStatus.FAILED)
            step.status = StepStatus.FAILED
            step.override_reason = data.reason
            step.completed_at = now
        else:
            step = InterventionStep(
                intervention_id=intervention_id,
                step_ref=step_ref,
                status=StepStatus.FAILED,
                override_reason=data.reason,
                started_at=now,
                completed_at=now,
                attempts=1,
            )
            await self.repo.add_step(step)

        await self.audit.record_event(
            AuditEventType.STEP_REJECTED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            step_ref=step_ref,
            payload={"reason": data.reason},
            ip_address=ip_address,
        )
        return await self._get_read(intervention_id)

    # ── Manual Override ───────────────────────────────────────────────────────

    async def override_step(
        self,
        intervention_id: UUID,
        step_ref: str,
        data: StepOverrideRequest,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Manually validate a step with a documented override.

        Every override is recorded in the audit trail with the operator's reason,
        optional evidence URL, and an HSE review flag. Post-intervention, HSE
        must review all flagged overrides before the procedure can be re-published.

        In Phase 5, this is the fallback path for vision/sensor steps.
        In Phase 6, manual override becomes the exception path used only when
        automatic vision validation fails.
        """
        intervention = await self._get_active_intervention(intervention_id)
        now = datetime.now(timezone.utc)

        step = await self.repo.get_step(intervention_id, step_ref)
        if step:
            validate_step_transition(step.status, StepStatus.OVERRIDDEN)
            step.status = StepStatus.OVERRIDDEN
            step.override_reason = data.reason
            step.validation_method_used = ValidationMethod.MANUAL_OVERRIDE
            step.evidence_url = data.evidence_url
            step.completed_at = now
            step.attempts += 1
        else:
            step = InterventionStep(
                intervention_id=intervention_id,
                step_ref=step_ref,
                status=StepStatus.OVERRIDDEN,
                override_reason=data.reason,
                validation_method_used=ValidationMethod.MANUAL_OVERRIDE,
                evidence_url=data.evidence_url,
                started_at=now,
                completed_at=now,
                attempts=1,
            )
            await self.repo.add_step(step)

        # Advance current_step_ref after successful override.
        wf = intervention.procedure_version.workflow_definition
        next_ref = self._extract_next_step_ref(wf, step_ref)
        intervention.current_step_ref = next_ref

        await self.audit.record_event(
            AuditEventType.STEP_OVERRIDE_GRANTED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            step_ref=step_ref,
            payload={
                "reason": data.reason,
                "evidence_url": data.evidence_url,
                "photo_reference": data.photo_reference,
                "requires_hse_review": data.requires_hse_review,
                "next_step_ref": next_ref,
            },
            ip_address=ip_address,
        )
        return await self._get_read(intervention_id)

    # ── Complete / Abort ──────────────────────────────────────────────────────

    async def complete_intervention(
        self,
        intervention_id: UUID,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """
        Close a completed intervention.
        All steps must be validated or overridden before closing is allowed.
        """
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)

        if intervention.status.is_terminal:
            raise NotFoundError("Active Intervention", intervention_id)

        validate_intervention_transition(
            intervention.status, InterventionStatus.COMPLETED
        )

        incomplete = await self.repo.count_incomplete_steps(intervention_id)
        if incomplete > 0:
            raise InterventionStepsIncompleteError(intervention_id, incomplete)

        intervention.status = InterventionStatus.COMPLETED
        intervention.completed_at = datetime.now(timezone.utc)

        await self.audit.record_event(
            AuditEventType.INTERVENTION_COMPLETED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            procedure_version_id=intervention.procedure_version_id,
            payload={"total_steps": len(intervention.steps)},
            ip_address=ip_address,
        )

        logger.info("intervention_completed", intervention_id=str(intervention_id))
        return await self._get_read(intervention_id)

    async def abort_intervention(
        self,
        intervention_id: UUID,
        reason: str,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> InterventionRead:
        """Emergency abort. Always allowed on active interventions."""
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)

        if intervention.status.is_terminal:
            raise NotFoundError("Active Intervention", intervention_id)

        validate_intervention_transition(
            intervention.status, InterventionStatus.ABORTED
        )

        intervention.status = InterventionStatus.ABORTED
        intervention.aborted_at = datetime.now(timezone.utc)
        intervention.abort_reason = reason

        await self.audit.record_event(
            AuditEventType.INTERVENTION_ABORTED,
            actor_id=actor_id or intervention.operator_name,
            machine_id=intervention.machine_id,
            intervention_id=intervention_id,
            procedure_version_id=intervention.procedure_version_id,
            payload={"reason": reason},
            ip_address=ip_address,
        )

        logger.warning(
            "intervention_aborted",
            intervention_id=str(intervention_id),
            reason=reason,
        )
        return await self._get_read(intervention_id)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_intervention(self, intervention_id: UUID) -> InterventionRead:
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)
        return InterventionRead.model_validate(intervention)

    async def get_progress(self, intervention_id: UUID) -> InterventionProgress:
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)

        steps = intervention.steps
        total = len(steps)
        completed = sum(1 for s in steps if s.status == StepStatus.VALIDATED)
        overridden = sum(1 for s in steps if s.status == StepStatus.OVERRIDDEN)
        failed = sum(1 for s in steps if s.status == StepStatus.FAILED)
        pending = sum(1 for s in steps if s.status == StepStatus.PENDING)
        done = completed + overridden
        pct = (done / total * 100) if total > 0 else 0.0

        return InterventionProgress(
            intervention_id=intervention_id,
            total_steps=total,
            completed_steps=completed,
            overridden_steps=overridden,
            failed_steps=failed,
            pending_steps=pending,
            completion_percentage=round(pct, 1),
        )

    async def get_current_step(self, intervention_id: UUID) -> CurrentStepContext:
        """
        Return the full context for the step currently being executed.

        Provides the runtime client (Quest / mobile) with all information
        needed to render the step without parsing the workflow JSON client-side.
        """
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)

        wf = intervention.procedure_version.workflow_definition
        current_ref = intervention.current_step_ref
        flat = self._flatten_steps(wf)
        flat_refs = [r for r, _, _, _ in flat]
        total = len(flat)

        if not current_ref:
            return CurrentStepContext(
                intervention_id=intervention_id,
                intervention_status=intervention.status,
                current_step_ref=None,
                overall_step_number=None,
                total_steps_overall=total,
                step_instruction=None,
                step_validation_method=None,
                safety_note=None,
                warnings=[],
                rollback_instruction=None,
                phase_id=None,
                phase_type=None,
                phase_title=None,
                stage_id=None,
                stage_title=None,
                previous_step_ref=None,
                next_step_ref=None,
                step_record=None,
            )

        # Find current step position and adjacent refs.
        try:
            pos = flat_refs.index(current_ref)
        except ValueError:
            pos = -1

        prev_ref = flat_refs[pos - 1] if pos > 0 else None
        next_ref = flat_refs[pos + 1] if 0 <= pos < total - 1 else None

        # Extract step details from workflow_definition.
        step_data: dict = {}
        phase_id = phase_type = phase_title = stage_id = stage_title = None
        for ref, phase, stage, step in flat:
            if ref == current_ref:
                step_data = step
                phase_id = phase.get("phase_id")
                phase_type = phase.get("phase_type")
                phase_title = phase.get("title")
                stage_id = stage.get("stage_id")
                stage_title = stage.get("title")
                break

        # Look up the DB step record if it exists.
        step_record_obj = await self.repo.get_step(intervention_id, current_ref)
        step_record = (
            InterventionStepRead.model_validate(step_record_obj)
            if step_record_obj
            else None
        )

        return CurrentStepContext(
            intervention_id=intervention_id,
            intervention_status=intervention.status,
            current_step_ref=current_ref,
            overall_step_number=pos + 1 if pos >= 0 else None,
            total_steps_overall=total,
            step_instruction=step_data.get("instruction"),
            step_validation_method=_engine.get_method_for_step(step_data),
            safety_note=step_data.get("safety_note"),
            warnings=step_data.get("warnings", []),
            rollback_instruction=step_data.get("rollback_instruction"),
            phase_id=phase_id,
            phase_type=phase_type,
            phase_title=phase_title,
            stage_id=stage_id,
            stage_title=stage_title,
            previous_step_ref=prev_ref,
            next_step_ref=next_ref,
            step_record=step_record,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_read(self, intervention_id: UUID) -> InterventionRead:
        intervention = await self.repo.get_with_steps(intervention_id)
        return InterventionRead.model_validate(intervention)

    async def _get_active_intervention(
        self, intervention_id: UUID
    ) -> Intervention:
        """Load intervention and assert it is still active (not terminal)."""
        intervention = await self.repo.get_with_steps(intervention_id)
        if not intervention:
            raise NotFoundError("Intervention", intervention_id)
        if intervention.status.is_terminal:
            raise InterventionNotActiveError(intervention_id, str(intervention.status))
        return intervention

    @staticmethod
    def _flatten_steps(
        workflow: dict,
    ) -> list[tuple[str, dict, dict, dict]]:
        """
        Return a flat ordered list of (step_ref, phase, stage, step) tuples
        for every step in the workflow.
        """
        result = []
        for phase in workflow.get("phases", []):
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    ref = (
                        f"{phase['phase_id']}."
                        f"{stage['stage_id']}."
                        f"{step['step_id']}"
                    )
                    result.append((ref, phase, stage, step))
        return result

    @staticmethod
    def _extract_first_step_ref(workflow: dict) -> str | None:
        try:
            first_phase = workflow["phases"][0]
            first_stage = first_phase["stages"][0]
            first_step = first_stage["steps"][0]
            return (
                f"{first_phase['phase_id']}."
                f"{first_stage['stage_id']}."
                f"{first_step['step_id']}"
            )
        except (KeyError, IndexError):
            return None

    @classmethod
    def _extract_next_step_ref(
        cls, workflow: dict, current_ref: str
    ) -> str | None:
        flat = cls._flatten_steps(workflow)
        refs = [r for r, _, _, _ in flat]
        try:
            idx = refs.index(current_ref)
            if idx + 1 < len(refs):
                return refs[idx + 1]
        except ValueError:
            pass
        return None

    @classmethod
    def _extract_prev_step_ref(
        cls, workflow: dict, current_ref: str
    ) -> str | None:
        flat = cls._flatten_steps(workflow)
        refs = [r for r, _, _, _ in flat]
        try:
            idx = refs.index(current_ref)
            if idx > 0:
                return refs[idx - 1]
        except ValueError:
            pass
        return None

    @staticmethod
    def _find_workflow_step(workflow: dict, step_ref: str) -> dict | None:
        parts = step_ref.split(".")
        if len(parts) != 3:
            return None
        phase_id, stage_id, step_id = parts
        for phase in workflow.get("phases", []):
            if phase.get("phase_id") != phase_id:
                continue
            for stage in phase.get("stages", []):
                if stage.get("stage_id") != stage_id:
                    continue
                for step in stage.get("steps", []):
                    if step.get("step_id") == step_id:
                        return step
        return None
