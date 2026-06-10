"""
ProcedureValidator — automatic consistency and safety checks.

Rules:
  ERROR — procedure must not be published if any ERROR exists.
  WARNING — publishable but HSE reviewer should inspect.
  INFO — informational, no action required.

Rule catalogue:
  E001  No phases defined
  E002  Lockout phase missing (OSHA mandatory)
  E003  Restoration phase missing (OSHA mandatory)
  E004  No steps anywhere in the procedure
  E005  Missing isolation step for an identified energy source
  E006  Empty instruction in a step
  E007  Duplicate step_id within the procedure
  E008  Unsafe ordering — maintenance before lockout
  E009  No energy sources identified in MachineKnowledge
  W001  No verification phase (strongly recommended)
  W002  Low confidence component (< 0.5) — may be misidentified
  W003  Physical action step with no YOLO validation prompts
  W004  No hazards documented — risk assessment may be incomplete
  W005  No special considerations — check if expected
  I001  Multiple energy sources — verify all are isolated
"""

from __future__ import annotations

from app.generation.models.generation_job import ValidationIssue, ValidationReport
from app.generation.models.machine_knowledge import MachineKnowledge


class ProcedureValidator:
    """
    Validates a generated (workflow_definition, MachineKnowledge) pair.

    Stateless — create once, call validate() multiple times.
    """

    def validate(
        self,
        workflow_definition: dict,
        knowledge: MachineKnowledge,
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        infos: list[ValidationIssue] = []

        phases: list[dict] = workflow_definition.get("phases", [])

        # ── Structural errors ────────────────────────────────────────────────
        self._check_phases_exist(phases, errors)
        self._check_mandatory_phases(phases, errors, warnings)
        self._check_steps_exist(phases, errors)
        self._check_empty_instructions(phases, errors)
        self._check_duplicate_step_ids(phases, errors)
        self._check_phase_ordering(phases, errors)

        # ── Domain completeness errors ────────────────────────────────────────
        self._check_energy_sources_have_lockout(phases, knowledge, errors)
        self._check_energy_sources_exist(knowledge, errors)

        # ── Warnings ─────────────────────────────────────────────────────────
        self._check_verification_phase(phases, warnings)
        self._check_component_confidence(knowledge, warnings)
        self._check_yolo_prompts(phases, warnings)
        self._check_hazards_documented(knowledge, warnings)
        self._check_special_considerations(knowledge, warnings)

        # ── Infos ─────────────────────────────────────────────────────────────
        if len(knowledge.energy_sources) + len(knowledge.isolation_switches) > 2:
            infos.append(ValidationIssue(
                code="I001",
                message=(
                    f"Multiple energy sources identified "
                    f"({len(knowledge.energy_sources)} sources + "
                    f"{len(knowledge.isolation_switches)} switches). "
                    "Verify all are covered by lockout stages."
                ),
                severity="info",
            ))

        return ValidationReport(
            is_publishable=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            infos=infos,
        )

    # ── Rule implementations ─────────────────────────────────────────────────

    @staticmethod
    def _check_phases_exist(phases: list, errors: list) -> None:
        if not phases:
            errors.append(ValidationIssue(
                code="E001",
                message="No phases defined in workflow_definition.",
                severity="error",
                field_path="workflow_definition.phases",
            ))

    @staticmethod
    def _check_mandatory_phases(phases: list, errors: list, warnings: list) -> None:
        phase_types = {p.get("phase_type") for p in phases}

        if "lockout" not in phase_types:
            errors.append(ValidationIssue(
                code="E002",
                message=(
                    "Lockout phase is missing. OSHA 29 CFR 1910.147 mandates "
                    "a lockout/tagout phase before any maintenance work."
                ),
                severity="error",
                field_path="workflow_definition.phases",
            ))

        if "restoration" not in phase_types:
            errors.append(ValidationIssue(
                code="E003",
                message=(
                    "Restoration phase is missing. Equipment must be safely "
                    "re-energised after maintenance."
                ),
                severity="error",
                field_path="workflow_definition.phases",
            ))

    @staticmethod
    def _check_steps_exist(phases: list, errors: list) -> None:
        total_steps = sum(
            len(stage.get("steps", []))
            for phase in phases
            for stage in phase.get("stages", [])
        )
        if total_steps == 0:
            errors.append(ValidationIssue(
                code="E004",
                message="Procedure has no steps. At least one step is required.",
                severity="error",
                field_path="workflow_definition.phases",
            ))

    @staticmethod
    def _check_empty_instructions(phases: list, errors: list) -> None:
        for phase in phases:
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    instruction = step.get("instruction", "").strip()
                    if not instruction:
                        errors.append(ValidationIssue(
                            code="E006",
                            message=f"Step '{step.get('step_id')}' has an empty instruction.",
                            severity="error",
                            field_path=f"phases.{phase.get('phase_id')}.{stage.get('stage_id')}.{step.get('step_id')}.instruction",
                        ))

    @staticmethod
    def _check_duplicate_step_ids(phases: list, errors: list) -> None:
        seen: set[str] = set()
        for phase in phases:
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    sid = step.get("step_id")
                    if sid in seen:
                        errors.append(ValidationIssue(
                            code="E007",
                            message=f"Duplicate step_id '{sid}' found in the procedure.",
                            severity="error",
                            field_path=f"step_id:{sid}",
                        ))
                    if sid:
                        seen.add(sid)

    @staticmethod
    def _check_phase_ordering(phases: list, errors: list) -> None:
        """Maintenance must come AFTER lockout (by sequence number)."""
        lockout_seq = None
        maintenance_seq = None
        for phase in phases:
            pt = phase.get("phase_type")
            seq = phase.get("sequence", 0)
            if pt == "lockout":
                lockout_seq = seq
            elif pt == "maintenance":
                maintenance_seq = seq

        if lockout_seq is not None and maintenance_seq is not None:
            if maintenance_seq < lockout_seq:
                errors.append(ValidationIssue(
                    code="E008",
                    message=(
                        "Unsafe phase ordering: maintenance (seq "
                        f"{maintenance_seq}) appears before lockout (seq {lockout_seq}). "
                        "Lockout MUST precede all maintenance work."
                    ),
                    severity="error",
                    field_path="workflow_definition.phases",
                ))

    @staticmethod
    def _check_energy_sources_have_lockout(
        phases: list, knowledge: MachineKnowledge, errors: list
    ) -> None:
        """Verify every energy source / isolation switch has a lockout step."""
        lockout_component_refs: set[str] = set()
        for phase in phases:
            if phase.get("phase_type") == "lockout":
                for stage in phase.get("stages", []):
                    for step in stage.get("steps", []):
                        ref = step.get("component_ref")
                        if ref:
                            lockout_component_refs.add(ref)

        for comp in knowledge.isolation_switches + knowledge.energy_sources:
            if comp.is_lockout_required and comp.component_id not in lockout_component_refs:
                errors.append(ValidationIssue(
                    code="E005",
                    message=(
                        f"Energy source / isolation switch '{comp.label}' "
                        f"(id='{comp.component_id}') has no corresponding lockout step."
                    ),
                    severity="error",
                    field_path=f"component:{comp.component_id}",
                ))

    @staticmethod
    def _check_energy_sources_exist(knowledge: MachineKnowledge, errors: list) -> None:
        if not knowledge.energy_sources and not knowledge.isolation_switches:
            errors.append(ValidationIssue(
                code="E009",
                message=(
                    "No energy sources or isolation switches identified. "
                    "At least one must be present for a valid LOTO procedure."
                ),
                severity="error",
                field_path="machine_knowledge.components",
            ))

    @staticmethod
    def _check_verification_phase(phases: list, warnings: list) -> None:
        phase_types = {p.get("phase_type") for p in phases}
        if "verification" not in phase_types:
            warnings.append(ValidationIssue(
                code="W001",
                message=(
                    "No verification phase found. OSHA strongly recommends "
                    "confirming zero-energy state before maintenance begins."
                ),
                severity="warning",
                field_path="workflow_definition.phases",
            ))

    @staticmethod
    def _check_component_confidence(knowledge: MachineKnowledge, warnings: list) -> None:
        for comp in knowledge.components:
            if comp.extraction_confidence < 0.5:
                warnings.append(ValidationIssue(
                    code="W002",
                    message=(
                        f"Component '{comp.label}' has low extraction confidence "
                        f"({comp.extraction_confidence:.0%}). "
                        "HSE reviewer should verify this component exists."
                    ),
                    severity="warning",
                    field_path=f"component:{comp.component_id}",
                ))

    @staticmethod
    def _check_yolo_prompts(phases: list, warnings: list) -> None:
        """Physical action steps should have YOLO validation prompts."""
        for phase in phases:
            for stage in phase.get("stages", []):
                for step in stage.get("steps", []):
                    validation = step.get("validation", {})
                    if (
                        validation.get("method") == "vision_detection"
                        and not validation.get("yolo_candidate_prompts")
                    ):
                        warnings.append(ValidationIssue(
                            code="W003",
                            message=(
                                f"Step '{step.get('step_id')}' uses vision_detection "
                                "but has no YOLO candidate prompts."
                            ),
                            severity="warning",
                            field_path=f"step:{step.get('step_id')}.validation",
                        ))

    @staticmethod
    def _check_hazards_documented(knowledge: MachineKnowledge, warnings: list) -> None:
        if not knowledge.hazards:
            warnings.append(ValidationIssue(
                code="W004",
                message=(
                    "No hazards documented. A risk assessment may be incomplete. "
                    "Review the source documentation."
                ),
                severity="warning",
                field_path="machine_knowledge.hazards",
            ))

    @staticmethod
    def _check_special_considerations(knowledge: MachineKnowledge, warnings: list) -> None:
        if not knowledge.special_considerations:
            warnings.append(ValidationIssue(
                code="W005",
                message=(
                    "No special considerations documented. "
                    "Verify there are no non-standard handling requirements."
                ),
                severity="warning",
                field_path="machine_knowledge.special_considerations",
            ))
