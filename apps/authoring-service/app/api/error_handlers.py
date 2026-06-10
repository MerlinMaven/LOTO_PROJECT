"""
Global exception handlers.

Maps domain exceptions → HTTP status codes and the standard ErrorResponse body.
All error responses follow the same shape:
    { "error": { "code": "...", "message": "...", "details": {...} } }

Business exceptions never leak stack traces to the client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ApprovedProcedureImmutableError,
    ConflictError,
    InterventionNotActiveError,
    InterventionStepsIncompleteError,
    InvalidStatusTransitionError,
    MachineAlreadyHasProcedureError,
    MachineAlreadyInInterventionError,
    NoActiveVersionError,
    NotFoundError,
    ProcedureNotApprovableError,
    ProcedureNotPublishableError,
    SelfApprovalForbiddenError,
    SmartLOTOError,
    StepAlreadyCompletedError,
    WorkflowValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def _error_response(code: str, message: str, details: dict, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI application."""

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _error_response("NOT_FOUND", exc.message, exc.details, status.HTTP_404_NOT_FOUND)

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _error_response("CONFLICT", exc.message, exc.details, status.HTTP_409_CONFLICT)

    @app.exception_handler(MachineAlreadyHasProcedureError)
    async def handle_machine_has_procedure(
        request: Request, exc: MachineAlreadyHasProcedureError
    ) -> JSONResponse:
        return _error_response(
            "MACHINE_ALREADY_HAS_PROCEDURE", exc.message, exc.details, status.HTTP_409_CONFLICT
        )

    @app.exception_handler(MachineAlreadyInInterventionError)
    async def handle_active_intervention(
        request: Request, exc: MachineAlreadyInInterventionError
    ) -> JSONResponse:
        return _error_response(
            "MACHINE_ALREADY_IN_INTERVENTION",
            exc.message,
            exc.details,
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(InvalidStatusTransitionError)
    async def handle_invalid_transition(
        request: Request, exc: InvalidStatusTransitionError
    ) -> JSONResponse:
        return _error_response(
            "INVALID_STATUS_TRANSITION",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(ApprovedProcedureImmutableError)
    async def handle_immutable(
        request: Request, exc: ApprovedProcedureImmutableError
    ) -> JSONResponse:
        return _error_response(
            "APPROVED_PROCEDURE_IMMUTABLE",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(SelfApprovalForbiddenError)
    async def handle_self_approval(
        request: Request, exc: SelfApprovalForbiddenError
    ) -> JSONResponse:
        return _error_response(
            "SELF_APPROVAL_FORBIDDEN", exc.message, exc.details, status.HTTP_403_FORBIDDEN
        )

    @app.exception_handler(ProcedureNotApprovableError)
    async def handle_not_approvable(
        request: Request, exc: ProcedureNotApprovableError
    ) -> JSONResponse:
        return _error_response(
            "PROCEDURE_NOT_APPROVABLE",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(ProcedureNotPublishableError)
    async def handle_not_publishable(
        request: Request, exc: ProcedureNotPublishableError
    ) -> JSONResponse:
        return _error_response(
            "PROCEDURE_NOT_PUBLISHABLE",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(WorkflowValidationError)
    async def handle_workflow_validation(
        request: Request, exc: WorkflowValidationError
    ) -> JSONResponse:
        return _error_response(
            "WORKFLOW_VALIDATION_ERROR",
            exc.message,
            exc.details,
            status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(NoActiveVersionError)
    async def handle_no_active_version(
        request: Request, exc: NoActiveVersionError
    ) -> JSONResponse:
        return _error_response(
            "NO_ACTIVE_VERSION", exc.message, exc.details, status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(InterventionStepsIncompleteError)
    async def handle_steps_incomplete(
        request: Request, exc: InterventionStepsIncompleteError
    ) -> JSONResponse:
        return _error_response(
            "INTERVENTION_STEPS_INCOMPLETE",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(InterventionNotActiveError)
    async def handle_intervention_not_active(
        request: Request, exc: InterventionNotActiveError
    ) -> JSONResponse:
        return _error_response(
            "INTERVENTION_NOT_ACTIVE",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(StepAlreadyCompletedError)
    async def handle_step_already_completed(
        request: Request, exc: StepAlreadyCompletedError
    ) -> JSONResponse:
        return _error_response(
            "STEP_ALREADY_COMPLETED",
            exc.message,
            exc.details,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(SmartLOTOError)
    async def handle_generic_domain_error(
        request: Request, exc: SmartLOTOError
    ) -> JSONResponse:
        logger.warning("unhandled_domain_error", error=str(exc))
        return _error_response(
            "DOMAIN_ERROR", exc.message, exc.details, status.HTTP_400_BAD_REQUEST
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_error", error=str(exc))
        return _error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            {},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
