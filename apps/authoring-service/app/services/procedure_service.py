"""
ProcedureService — orchestrates the full procedure lifecycle.

Responsibilities:
  1. Create draft procedures (Procedure envelope + first ProcedureVersion)
  2. Validate workflow_definition against the canonical schema
  3. Enforce the state machine via domain/state_machine.py
  4. Enforce the 4-eyes approval rule
  5. Enforce immutability of approved/published/archived versions
  6. Atomically publish a version (set active_version_id, archive previous)
  7. Emit audit events for every critical state change

This service does NOT interact with any AI system.
LLM-generated workflows arrive as pre-built dicts from the caller.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import (
    ApprovedProcedureImmutableError,
    MachineAlreadyHasProcedureError,
    NotFoundError,
    ProcedureNotApprovableError,
    ProcedureNotPublishableError,
    SelfApprovalForbiddenError,
)
from app.core.logging import get_logger
from app.domain.enums import AuditEventType, ApprovalDecision, ProcedureStatus
from app.domain.state_machine import validate_transition, validate_workflow_definition
from app.models.procedure import Procedure, ProcedureApproval, ProcedureVersion
from app.repositories.procedure_repository import ProcedureRepository
from app.schemas.common import PaginatedResponse
from app.schemas.procedure import (
    ApprovalCreate,
    ApprovalRead,
    DraftUpdate,
    ProcedureCreate,
    ProcedureListItem,
    ProcedurePublishResponse,
    ProcedureRead,
    ProcedureVersionRead,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class ProcedureService:
    def __init__(
        self,
        procedure_repo: ProcedureRepository,
        audit_service: AuditService,
    ) -> None:
        self.repo = procedure_repo
        self.audit = audit_service

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_draft(
        self,
        data: ProcedureCreate,
        *,
        actor_id: str | None = None,
        ip_address: str | None = None,
    ) -> ProcedureRead:
        """
        Creates a Procedure envelope and its first ProcedureVersion atomically.

        If the machine already has a procedure, raises MachineAlreadyHasProcedureError.
        The caller should use create_new_version() to add a new draft to an
        existing procedure.
        """
        existing = await self.repo.get_by_machine_id(data.machine_id)
        if existing:
            raise MachineAlreadyHasProcedureError(data.machine_id)

        # Validate canonical JSON schema (structural validation only)
        errors = validate_workflow_definition(data.workflow_definition)

        procedure = Procedure(
            machine_id=data.machine_id,
            title=data.title,
            created_by=data.created_by,
        )
        procedure = await self.repo.create(procedure)

        version = ProcedureVersion(
            procedure_id=procedure.id,
            version_number="1.0.0",
            status=ProcedureStatus.DRAFT_PENDING_REVIEW,
            generation_source=data.generation_source,
            llm_model_used=data.llm_model_used,
            workflow_definition=data.workflow_definition,
            validation_errors=errors if errors else None,
            created_by=data.created_by,
        )
        version = await self.repo.create_version(version)

        await self.audit.record_event(
            AuditEventType.PROCEDURE_DRAFT_CREATED,
            actor_id=actor_id or data.created_by,
            machine_id=data.machine_id,
            procedure_version_id=version.id,
            payload={
                "procedure_id": str(procedure.id),
                "version_number": version.version_number,
                "has_validation_errors": bool(errors),
                "validation_error_count": len(errors),
            },
            ip_address=ip_address,
        )

        if errors:
            logger.warning(
                "procedure_draft_created_with_schema_errors",
                procedure_id=str(procedure.id),
                error_count=len(errors),
            )
        else:
            logger.info("procedure_draft_created", procedure_id=str(procedure.id))

        procedure = await self.repo.get_with_versions(procedure.id)
        return ProcedureRead.model_validate(procedure)

    # ── Approve ───────────────────────────────────────────────────────────────

    async def approve_procedure(
        self,
        procedure_id: UUID,
        approval_data: ApprovalCreate,
        *,
        ip_address: str | None = None,
    ) -> ApprovalRead:
        """
        Approve or reject the current draft version.

        Enforces:
        - 4-eyes rule: approver ≠ version author
        - State machine: draft_pending_review → approved
        - Immutability: approved versions cannot be re-approved
        """
        procedure = await self.repo.get_with_versions(procedure_id)
        if not procedure:
            raise NotFoundError("Procedure", procedure_id)

        version = await self.repo.get_current_draft_version(procedure_id)
        if not version:
            raise ProcedureNotApprovableError("no_draft_version")

        # 4-eyes rule
        if version.created_by == approval_data.approved_by:
            raise SelfApprovalForbiddenError(approval_data.approved_by)

        if approval_data.decision == ApprovalDecision.APPROVED:
            # State machine transition: draft_pending_review → approved
            validate_transition(version.status, ProcedureStatus.APPROVED)
            version.status = ProcedureStatus.APPROVED
            version.submitted_for_review_at = datetime.now(timezone.utc)
            event_type = AuditEventType.PROCEDURE_APPROVED
        else:
            # Rejection: version returns to draft (reset status) or stays rejected
            # Design choice: rejected versions stay as-is, a new draft must be created
            version.status = ProcedureStatus.DRAFT_PENDING_REVIEW
            event_type = AuditEventType.PROCEDURE_REJECTED

        approval = ProcedureApproval(
            version_id=version.id,
            approved_by=approval_data.approved_by,
            decision=approval_data.decision,
            notes=approval_data.notes,
        )
        approval = await self.repo.create_approval(approval)

        await self.audit.record_event(
            event_type,
            actor_id=approval_data.approved_by,
            machine_id=procedure.machine_id,
            procedure_version_id=version.id,
            payload={
                "decision": approval_data.decision,
                "notes": approval_data.notes,
                "version_number": version.version_number,
            },
            ip_address=ip_address,
        )

        logger.info(
            "procedure_approval_recorded",
            procedure_id=str(procedure_id),
            version_id=str(version.id),
            decision=approval_data.decision,
            approver=approval_data.approved_by,
        )
        return ApprovalRead.model_validate(approval)

    # ── Publish ───────────────────────────────────────────────────────────────

    async def publish_procedure(
        self,
        procedure_id: UUID,
        *,
        actor_id: str = "system",
        ip_address: str | None = None,
    ) -> ProcedurePublishResponse:
        """
        Publish the currently approved version.

        Atomically:
        1. Transitions the approved version → published
        2. Archives the previously published version (if any)
        3. Sets Procedure.active_version_id to the new version

        Only ONE published version per procedure at any time.
        Ongoing interventions referencing the old version are NOT affected
        (they hold a FK to procedure_version_id, not to procedure.active_version_id).
        """
        procedure = await self.repo.get_with_versions(procedure_id)
        if not procedure:
            raise NotFoundError("Procedure", procedure_id)

        version = await self.repo.get_approved_version(procedure_id)
        if not version:
            raise ProcedureNotPublishableError("no_approved_version")

        # State machine: approved → published
        validate_transition(version.status, ProcedureStatus.PUBLISHED)

        # Archive currently published version if present
        deprecated_version_id: UUID | None = None
        old_version = await self.repo.get_published_version(procedure_id)
        if old_version and old_version.id != version.id:
            validate_transition(old_version.status, ProcedureStatus.ARCHIVED)
            old_version.status = ProcedureStatus.ARCHIVED
            deprecated_version_id = old_version.id
            await self.audit.record_event(
                AuditEventType.PROCEDURE_ARCHIVED,
                actor_id=actor_id,
                machine_id=procedure.machine_id,
                procedure_version_id=old_version.id,
                payload={"superseded_by": str(version.id)},
            )

        version.status = ProcedureStatus.PUBLISHED
        procedure.active_version_id = version.id
        now = datetime.now(timezone.utc)

        await self.audit.record_event(
            AuditEventType.PROCEDURE_PUBLISHED,
            actor_id=actor_id,
            machine_id=procedure.machine_id,
            procedure_version_id=version.id,
            payload={
                "version_number": version.version_number,
                "deprecated_version_id": str(deprecated_version_id) if deprecated_version_id else None,
            },
            ip_address=ip_address,
        )

        logger.info(
            "procedure_published",
            procedure_id=str(procedure_id),
            version_id=str(version.id),
            version_number=version.version_number,
        )

        return ProcedurePublishResponse(
            procedure_id=procedure_id,
            published_version_id=version.id,
            deprecated_version_id=deprecated_version_id,
            published_at=now,
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_procedure(self, procedure_id: UUID) -> ProcedureRead:
        procedure = await self.repo.get_with_versions(procedure_id)
        if not procedure:
            raise NotFoundError("Procedure", procedure_id)
        return ProcedureRead.model_validate(procedure)

    async def get_active_version_for_machine(
        self, machine_id: UUID
    ) -> ProcedureVersionRead:
        """
        Returns the published procedure version for a machine.
        Used by the Quest client before starting an intervention.
        """
        procedure = await self.repo.get_by_machine_id(machine_id)
        if not procedure:
            raise NotFoundError("Procedure", machine_id)

        version = await self.repo.get_published_version(procedure.id)
        if not version:
            from app.core.exceptions import NoActiveVersionError
            raise NoActiveVersionError(machine_id)

        return ProcedureVersionRead.model_validate(version)

    # ── List (HSE Dashboard) ────────────────────────────────────────────────────

    async def list_procedures(
        self,
        *,
        status: ProcedureStatus | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[ProcedureListItem]:
        """
        List procedures for the HSE dashboard home.

        Each procedure is reduced to a ProcedureListItem whose `current_status`
        is the status of its most recent version. Optional `status` filters on
        that derived value; `search` matches the title (case-insensitive).

        Filtering/derivation happen in Python because the display status is a
        property of the latest version, not a column. The procedure population
        in a single tenant is modest, so this is acceptable and keeps the query
        simple.
        """
        procedures = await self.repo.list_all_with_versions(search=search)

        items: list[ProcedureListItem] = []
        for proc in procedures:
            item = self._to_list_item(proc)
            if item is None:
                continue  # procedure with no versions — skip defensively
            if status is not None and item.current_status != status:
                continue
            items.append(item)

        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start : start + page_size]

        return PaginatedResponse[ProcedureListItem](
            data=page_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def _to_list_item(procedure: Procedure) -> ProcedureListItem | None:
        """Reduce a Procedure + its versions to a dashboard list row."""
        versions = procedure.versions
        if not versions:
            return None

        # versions are ordered created_at DESC at the ORM level
        latest = versions[0]
        has_published = any(v.status == ProcedureStatus.PUBLISHED for v in versions)

        meta = (latest.workflow_definition or {}).get("_generation_metadata", {})
        confidence = meta.get("overall_confidence")

        return ProcedureListItem(
            id=procedure.id,
            machine_id=procedure.machine_id,
            title=procedure.title,
            created_by=procedure.created_by,
            current_status=latest.status,
            current_version_id=latest.id,
            current_version_number=latest.version_number,
            generation_source=latest.generation_source,
            overall_confidence=confidence,
            open_validation_errors=len(latest.validation_errors or []),
            has_published_version=has_published,
            created_at=procedure.created_at,
            updated_at=procedure.updated_at,
        )

    # ── Edit draft (HSE Dashboard) ──────────────────────────────────────────────

    async def update_draft(
        self,
        procedure_id: UUID,
        data: DraftUpdate,
        *,
        ip_address: str | None = None,
    ) -> ProcedureVersionRead:
        """
        Replace the workflow_definition of the current draft version.

        This is the single write path behind every edit surface in the review
        screens (component edits, workflow step edits, vision prompt edits) —
        they all mutate the one workflow_definition document.

        Enforces:
        - The procedure exists.
        - A draft_pending_review version exists.
        - The draft is mutable (ApprovedProcedureImmutableError otherwise).
        - Re-runs structural schema validation and stores the result.
        """
        procedure = await self.repo.get_with_versions(procedure_id)
        if not procedure:
            raise NotFoundError("Procedure", procedure_id)

        version = await self.repo.get_current_draft_version(procedure_id)
        if not version:
            raise NotFoundError("Draft version for procedure", procedure_id)

        if version.status.is_immutable:
            raise ApprovedProcedureImmutableError(version.id, str(version.status))

        errors = validate_workflow_definition(data.workflow_definition)

        version.workflow_definition = data.workflow_definition
        version.validation_errors = errors if errors else None
        version = await self.repo.update_version(version)

        await self.audit.record_event(
            AuditEventType.PROCEDURE_DRAFT_UPDATED,
            actor_id=data.edited_by,
            machine_id=procedure.machine_id,
            procedure_version_id=version.id,
            payload={
                "version_number": version.version_number,
                "edit_summary": data.edit_summary,
                "has_validation_errors": bool(errors),
                "validation_error_count": len(errors),
            },
            ip_address=ip_address,
        )

        logger.info(
            "procedure_draft_updated",
            procedure_id=str(procedure_id),
            version_id=str(version.id),
            editor=data.edited_by,
            error_count=len(errors),
        )
        return ProcedureVersionRead.model_validate(version)
