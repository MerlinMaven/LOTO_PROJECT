"""
Intervention endpoints.

POST   /api/v1/interventions                            Start an intervention
GET    /api/v1/interventions/{id}                       Get intervention state
POST   /api/v1/interventions/{id}/pause                 Pause (shift-change)
POST   /api/v1/interventions/{id}/resume                Resume paused intervention
POST   /api/v1/interventions/{id}/complete              Close a completed intervention
POST   /api/v1/interventions/{id}/abort                 Emergency abort
GET    /api/v1/interventions/{id}/current-step          Step context for the active step
GET    /api/v1/interventions/{id}/progress              Step completion statistics
GET    /api/v1/interventions/{id}/audit                 Full audit trail
POST   /api/v1/interventions/{id}/steps/{ref}/enter     Mark step in-progress
POST   /api/v1/interventions/{id}/steps/{ref}/validate  Manual confirmation
POST   /api/v1/interventions/{id}/steps/{ref}/reject    Mark step failed
POST   /api/v1/interventions/{id}/steps/{ref}/override  Override with evidence
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.deps import AuditSvcDep, CurrentUserDep, InterventionSvcDep
from app.schemas.audit import AuditEventRead
from app.schemas.intervention import (
    CurrentStepContext,
    InterventionAbortRequest,
    InterventionCreate,
    InterventionPauseRequest,
    InterventionProgress,
    InterventionRead,
    StepOverrideRequest,
    StepRejectRequest,
    StepValidationRequest,
)

router = APIRouter()


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ── Lifecycle ─────────────────────────────────────────────────────────────────


@router.post("", response_model=InterventionRead, status_code=status.HTTP_201_CREATED)
async def start_intervention(
    body: InterventionCreate,
    request: Request,
    svc: InterventionSvcDep,
) -> InterventionRead:
    """
    Start a LOTO intervention on a machine.

    - Machine must have a published (active) procedure.
    - No other active intervention may be running on this machine.

    The procedure version is pinned at creation — publishing a new version
    while an intervention runs does NOT affect the ongoing session.
    """
    return await svc.start_intervention(body, ip_address=_ip(request))


@router.get("/{intervention_id}", response_model=InterventionRead)
async def get_intervention(
    intervention_id: UUID, svc: InterventionSvcDep
) -> InterventionRead:
    """Get the current state of an intervention including all step records."""
    return await svc.get_intervention(intervention_id)


@router.post("/{intervention_id}/pause", response_model=InterventionRead)
async def pause_intervention(
    intervention_id: UUID,
    body: InterventionPauseRequest,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Temporarily suspend an in-progress intervention.

    Typical use-case: end-of-shift handover or emergency stop while
    the operator deals with another issue. The step state is preserved.
    The intervention can be resumed by any authorised operator.
    """
    return await svc.pause_intervention(
        intervention_id,
        reason=body.reason,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post("/{intervention_id}/resume", response_model=InterventionRead)
async def resume_intervention(
    intervention_id: UUID,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """Resume a paused intervention. The current step is unchanged."""
    return await svc.resume_intervention(
        intervention_id,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post("/{intervention_id}/complete", response_model=InterventionRead)
async def complete_intervention(
    intervention_id: UUID,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Close a completed intervention.
    All steps must be validated or overridden before this is allowed.
    """
    return await svc.complete_intervention(
        intervention_id,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post("/{intervention_id}/abort", response_model=InterventionRead)
async def abort_intervention(
    intervention_id: UUID,
    body: InterventionAbortRequest,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """Emergency abort. Always allowed on active interventions."""
    return await svc.abort_intervention(
        intervention_id,
        body.reason,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


# ── Read ──────────────────────────────────────────────────────────────────────


@router.get("/{intervention_id}/current-step", response_model=CurrentStepContext)
async def get_current_step(
    intervention_id: UUID, svc: InterventionSvcDep
) -> CurrentStepContext:
    """
    Return all display data for the step currently being executed.

    The Quest / mobile client calls this to render the current step
    without having to parse the entire workflow_definition JSON.
    Includes: instruction, validation method, safety note, warnings,
    phase/stage context, and adjacent step refs for navigation.
    """
    return await svc.get_current_step(intervention_id)


@router.get("/{intervention_id}/progress", response_model=InterventionProgress)
async def get_progress(
    intervention_id: UUID, svc: InterventionSvcDep
) -> InterventionProgress:
    """Get step completion statistics for an intervention."""
    return await svc.get_progress(intervention_id)


@router.get("/{intervention_id}/audit", response_model=list[AuditEventRead])
async def get_intervention_audit(
    intervention_id: UUID, audit_svc: AuditSvcDep
) -> list[AuditEventRead]:
    """
    Get the full ordered audit trail for a single intervention.
    Used for OSHA 29 CFR 1910.147 traceability reports.
    """
    return await audit_svc.get_intervention_trail(intervention_id)


# ── Step actions ──────────────────────────────────────────────────────────────


@router.post(
    "/{intervention_id}/steps/{step_ref}/enter",
    response_model=InterventionRead,
)
async def enter_step(
    intervention_id: UUID,
    step_ref: str,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Mark a step as in-progress and set it as the current step.

    Call this when the operator begins working on the step.
    Creates the step record on first entry; retries increment the attempt counter.
    """
    return await svc.enter_step(
        intervention_id,
        step_ref,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post(
    "/{intervention_id}/steps/{step_ref}/validate",
    response_model=InterventionRead,
)
async def validate_step(
    intervention_id: UUID,
    step_ref: str,
    body: StepValidationRequest,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Validate a step using the manual confirmation strategy.

    Phase 5 only supports manual confirmation.
    Vision / sensor stubs return `requires_override=True` — direct the operator
    to the `/override` endpoint for those step types.
    The `confirmed_by` field must identify the confirming operator (4-eyes support).
    """
    return await svc.validate_step(
        intervention_id,
        step_ref,
        body,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post(
    "/{intervention_id}/steps/{step_ref}/reject",
    response_model=InterventionRead,
)
async def reject_step(
    intervention_id: UUID,
    step_ref: str,
    body: StepRejectRequest,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Mark a step as failed with a rejection reason.

    The step can be retried by calling `/enter` again (FAILED → IN_PROGRESS).
    Use this when the machine is in an unexpected state and the step cannot
    be performed safely.
    """
    return await svc.reject_step(
        intervention_id,
        step_ref,
        body,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )


@router.post(
    "/{intervention_id}/steps/{step_ref}/override",
    response_model=InterventionRead,
)
async def override_step(
    intervention_id: UUID,
    step_ref: str,
    body: StepOverrideRequest,
    request: Request,
    svc: InterventionSvcDep,
    user: CurrentUserDep,
) -> InterventionRead:
    """
    Manually validate a step with a documented override.

    Every override is flagged for post-intervention HSE review by default
    (`requires_hse_review=true`). HSE must review all flagged overrides before
    the procedure can be re-published.

    Phase 5: primary fallback for vision/sensor steps not yet available.
    Phase 6: exception path used only when automatic vision validation fails.
    """
    return await svc.override_step(
        intervention_id,
        step_ref,
        body,
        actor_id=user.identifier,
        ip_address=_ip(request),
    )
