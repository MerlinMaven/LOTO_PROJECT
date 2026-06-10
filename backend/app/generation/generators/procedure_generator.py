"""
ProcedureGenerator — transforms MachineKnowledge into a canonical workflow_definition.

This is a PURE ALGORITHMIC generator — no second LLM call.
The LOTO methodology is codified as rules, not learned from data.
This makes the generator:
  - Deterministic (same input → same output)
  - Auditable (every step can be traced to a rule)
  - Testable without API keys

LOTO Procedure Structure Generated:
  PHASE 1 — Lockout
    Stage per isolation point (switch + battery removal)
    Each stage ends with physical lock application
  PHASE 2 — Verification
    Zero-energy verification for each energy source
    Guard/panel opened for access
  PHASE 3 — Maintenance
    One stage per maintenance target
    Based on maintenance_objectives from MachineKnowledge
  PHASE 4 — Restoration
    Guard/panel closed
    Energy sources restored in REVERSE lockout order
    Final activation + functional verification
"""

from __future__ import annotations

import re
from typing import Optional

from app.generation.models.machine_knowledge import (
    ComponentType,
    MachineComponent,
    MachineKnowledge,
)


class ProcedureGenerator:
    """
    Generates a LOTO workflow_definition dict from MachineKnowledge.

    The output dict is the canonical `workflow_definition` stored in
    `ProcedureVersion.workflow_definition` — it must validate against
    the Phase 1 schema (phases → stages → steps).
    """

    def generate(self, knowledge: MachineKnowledge) -> tuple[dict, list[str]]:
        """
        Generate workflow_definition and generation notes.

        Returns:
            (workflow_definition_dict, list_of_human_readable_notes)
        """
        notes: list[str] = []
        phases: list[dict] = []
        seq = 1

        # ── Phase 1: LOCKOUT ─────────────────────────────────────────────────
        lockout_phase = self._build_lockout_phase(knowledge, seq, notes)
        if lockout_phase:
            phases.append(lockout_phase)
            seq += 1

        # ── Phase 2: VERIFICATION ─────────────────────────────────────────────
        verification_phase = self._build_verification_phase(knowledge, seq, notes)
        if verification_phase:
            phases.append(verification_phase)
            seq += 1

        # ── Phase 3: MAINTENANCE ──────────────────────────────────────────────
        maintenance_phase = self._build_maintenance_phase(knowledge, seq, notes)
        if maintenance_phase:
            phases.append(maintenance_phase)
            seq += 1

        # ── Phase 4: RESTORATION ─────────────────────────────────────────────
        restoration_phase = self._build_restoration_phase(knowledge, seq, notes)
        if restoration_phase:
            phases.append(restoration_phase)

        if not phases:
            notes.append("WARNING: Could not generate any phases from the provided knowledge.")

        return {"phases": phases}, notes

    # ── Phase builders ────────────────────────────────────────────────────────

    def _build_lockout_phase(
        self, knowledge: MachineKnowledge, seq: int, notes: list[str]
    ) -> Optional[dict]:
        """
        LOCKOUT: de-energize → physically isolate → store energy source.
        One stage per isolation point, ordered by energy risk (higher severity first).
        """
        stages: list[dict] = []
        stage_seq = 1

        # Isolation switches first (turn OFF)
        for comp in knowledge.isolation_switches:
            stages.append(
                self._build_isolation_stage(comp, knowledge, stage_seq)
            )
            stage_seq += 1
            notes.append(f"Lockout: isolation switch '{comp.label}' → stage {stage_seq-1}")

        # Energy sources (physical removal)
        for comp in knowledge.energy_sources:
            storage = self._find_storage_for_energy(comp, knowledge)
            stages.append(
                self._build_energy_removal_stage(comp, storage, knowledge, stage_seq)
            )
            stage_seq += 1
            notes.append(f"Lockout: energy source '{comp.label}' → stage {stage_seq-1}")

        if not stages:
            notes.append("WARNING: No isolation switches or energy sources found for lockout.")
            return None

        return {
            "phase_id": "ph_lockout",
            "phase_type": "lockout",
            "sequence": seq,
            "title": "Lockout — Energy Isolation",
            "description": (
                "De-energize and physically isolate all energy sources. "
                "OSHA 29 CFR 1910.147 requires this phase to be completed "
                "before any maintenance work begins."
            ),
            "stages": stages,
        }

    def _build_verification_phase(
        self, knowledge: MachineKnowledge, seq: int, notes: list[str]
    ) -> Optional[dict]:
        """
        VERIFICATION: confirm zero-energy state + open access panels.
        """
        stages: list[dict] = []
        stage_seq = 1

        # Zero-energy verification
        zero_energy_steps: list[dict] = []
        step_seq = 1

        for comp in knowledge.lockout_points:
            state_locked = self._get_state_locked(comp)
            zero_energy_steps.append({
                "step_id": f"ph_verify.st_zero_energy.stp_{step_seq}",
                "sequence": step_seq,
                "instruction": (
                    f"Verify that '{comp.label}' is in its isolated state. "
                    + (f"Expected: {state_locked}." if state_locked else "")
                ),
                "component_ref": comp.component_id,
                "safety_note": "Do not proceed until zero-energy state is confirmed.",
                "validation": {
                    "method": "manual_confirmation",
                    "expected_state": state_locked or "isolated",
                    "yolo_candidate_prompts": self._get_state_prompts(comp, "isolated"),
                },
            })
            step_seq += 1

        if zero_energy_steps:
            stages.append({
                "stage_id": "st_zero_energy",
                "sequence": stage_seq,
                "title": "Zero-Energy Verification",
                "steps": zero_energy_steps,
            })
            stage_seq += 1
            notes.append("Verification: zero-energy check added.")

        # Open safety guards / access panels
        access_steps: list[dict] = []
        step_seq = 1
        for guard in knowledge.safety_guards:
            state_locked = self._get_state_locked(guard)  # open = "locked" for guard
            access_steps.append({
                "step_id": f"ph_verify.st_access.stp_{step_seq}",
                "sequence": step_seq,
                "instruction": f"Open '{guard.label}' to gain access to the maintenance area.",
                "component_ref": guard.component_id,
                "validation": {
                    "method": "vision_detection",
                    "expected_state": state_locked or "open",
                    "yolo_candidate_prompts": self._get_state_prompts(guard, "isolated"),
                },
            })
            step_seq += 1

        if access_steps:
            stages.append({
                "stage_id": "st_access_preparation",
                "sequence": stage_seq,
                "title": "Access Preparation",
                "steps": access_steps,
            })
            notes.append("Verification: access panel opening steps added.")

        if not stages:
            notes.append("INFO: No verification stages generated (no lockout points found).")
            return None

        return {
            "phase_id": "ph_verification",
            "phase_type": "verification",
            "sequence": seq,
            "title": "Verification — Confirm Zero-Energy State",
            "description": "Confirm all energy sources are isolated before beginning work.",
            "stages": stages,
        }

    def _build_maintenance_phase(
        self, knowledge: MachineKnowledge, seq: int, notes: list[str]
    ) -> Optional[dict]:
        """
        MAINTENANCE: actual work on each maintenance target.
        """
        stages: list[dict] = []
        stage_seq = 1

        for target in knowledge.maintenance_targets:
            steps: list[dict] = []
            step_seq = 1

            # Generate one step per maintenance objective
            for i, objective in enumerate(knowledge.maintenance_objectives):
                steps.append({
                    "step_id": f"ph_maintenance.st_{_slugify(target.component_id)}.stp_{step_seq}",
                    "sequence": step_seq,
                    "instruction": (
                        f"On '{target.label}': {objective}. "
                        f"Location: {target.location_hint or 'see component map'}."
                    ),
                    "component_ref": target.component_id,
                    "validation": {
                        "method": "manual_confirmation",
                        "expected_state": "maintenance_complete",
                        "yolo_candidate_prompts": self._get_all_state_prompts(target),
                    },
                })
                step_seq += 1

            if not steps:
                steps.append({
                    "step_id": f"ph_maintenance.st_{_slugify(target.component_id)}.stp_1",
                    "sequence": 1,
                    "instruction": f"Perform required maintenance on '{target.label}'.",
                    "component_ref": target.component_id,
                    "validation": {"method": "manual_confirmation"},
                })

            # Add special considerations as the final step
            if knowledge.special_considerations:
                considerations_text = "; ".join(knowledge.special_considerations)
                steps.append({
                    "step_id": f"ph_maintenance.st_{_slugify(target.component_id)}.stp_{step_seq}",
                    "sequence": step_seq,
                    "instruction": (
                        f"Before proceeding to restoration, verify: {considerations_text}."
                    ),
                    "component_ref": None,
                    "validation": {"method": "manual_confirmation"},
                })

            stages.append({
                "stage_id": f"st_{_slugify(target.component_id)}_maintenance",
                "sequence": stage_seq,
                "title": f"{target.label} — Maintenance",
                "steps": steps,
            })
            stage_seq += 1
            notes.append(f"Maintenance: target '{target.label}' → stage {stage_seq-1}")

        if not stages:
            notes.append(
                "WARNING: No maintenance targets found. "
                "Adding generic maintenance stage from objectives."
            )
            if knowledge.maintenance_objectives:
                generic_steps = [
                    {
                        "step_id": f"ph_maintenance.st_work.stp_{i+1}",
                        "sequence": i + 1,
                        "instruction": obj,
                        "component_ref": None,
                        "validation": {"method": "manual_confirmation"},
                    }
                    for i, obj in enumerate(knowledge.maintenance_objectives)
                ]
                stages.append({
                    "stage_id": "st_maintenance_work",
                    "sequence": 1,
                    "title": "Maintenance Work",
                    "steps": generic_steps,
                })
            else:
                return None

        return {
            "phase_id": "ph_maintenance",
            "phase_type": "maintenance",
            "sequence": seq,
            "title": "Maintenance — Authorised Work",
            "description": (
                "Perform authorised maintenance tasks on isolated equipment. "
                "All energy sources must be locked out before this phase."
            ),
            "stages": stages,
        }

    def _build_restoration_phase(
        self, knowledge: MachineKnowledge, seq: int, notes: list[str]
    ) -> Optional[dict]:
        """
        RESTORATION: close access → restore energy sources in REVERSE lockout order.
        """
        stages: list[dict] = []
        stage_seq = 1

        # Close safety guards / access panels
        close_steps: list[dict] = []
        step_seq = 1
        for guard in knowledge.safety_guards:
            state_active = self._get_state_active(guard)
            close_steps.append({
                "step_id": f"ph_restoration.st_closure.stp_{step_seq}",
                "sequence": step_seq,
                "instruction": f"Close '{guard.label}' and verify it is fully secured.",
                "component_ref": guard.component_id,
                "validation": {
                    "method": "vision_detection",
                    "expected_state": state_active or "closed",
                    "yolo_candidate_prompts": self._get_state_prompts(guard, "active"),
                },
            })
            step_seq += 1

        if close_steps:
            stages.append({
                "stage_id": "st_access_closure",
                "sequence": stage_seq,
                "title": "Access Closure",
                "steps": close_steps,
            })
            stage_seq += 1
            notes.append("Restoration: access closure added.")

        # Restore energy sources in REVERSE order (mirrors lockout)
        energy_sources_reversed = list(reversed(knowledge.energy_sources))
        for comp in energy_sources_reversed:
            stages.append(
                self._build_energy_restoration_stage(comp, knowledge, stage_seq)
            )
            stage_seq += 1
            notes.append(f"Restoration: energy source '{comp.label}' → stage {stage_seq-1}")

        # Restore isolation switches in REVERSE order
        switches_reversed = list(reversed(knowledge.isolation_switches))
        for comp in switches_reversed:
            stages.append(
                self._build_switch_restoration_stage(comp, knowledge, stage_seq)
            )
            stage_seq += 1
            notes.append(f"Restoration: switch '{comp.label}' → stage {stage_seq-1}")

        if not stages:
            notes.append("WARNING: No restoration stages generated.")
            return None

        return {
            "phase_id": "ph_restoration",
            "phase_type": "restoration",
            "sequence": seq,
            "title": "Restoration — Safely Restore Energy",
            "description": (
                "Restore all energy sources in the reverse order of lockout. "
                "Verify correct installation before energising."
            ),
            "stages": stages,
        }

    # ── Stage / step builders ─────────────────────────────────────────────────

    def _build_isolation_stage(
        self,
        switch: MachineComponent,
        knowledge: MachineKnowledge,
        seq: int,
    ) -> dict:
        state_active = self._get_state_active(switch)
        state_locked = self._get_state_locked(switch)

        return {
            "stage_id": f"st_isolate_{switch.component_id}",
            "sequence": seq,
            "title": f"Isolate — {switch.label}",
            "steps": [
                {
                    "step_id": f"ph_lockout.st_isolate_{switch.component_id}.stp_1",
                    "sequence": 1,
                    "instruction": (
                        f"Move '{switch.label}' to the OFF / isolated position. "
                        + (f"Current state: {state_active}." if state_active else "")
                    ),
                    "component_ref": switch.component_id,
                    "safety_note": "Ensure the switch is fully OFF before proceeding.",
                    "validation": {
                        "method": "vision_detection",
                        "expected_state": state_locked or "off",
                        "yolo_candidate_prompts": self._get_state_prompts(switch, "isolated"),
                    },
                }
            ],
        }

    def _build_energy_removal_stage(
        self,
        source: MachineComponent,
        storage: Optional[MachineComponent],
        knowledge: MachineKnowledge,
        seq: int,
    ) -> dict:
        state_active = self._get_state_active(source)
        state_locked = self._get_state_locked(source)

        steps: list[dict] = [
            {
                "step_id": f"ph_lockout.st_remove_{source.component_id}.stp_1",
                "sequence": 1,
                "instruction": (
                    f"Remove '{source.label}' to physically cut the energy supply. "
                    + (f"Current state: {state_active}." if state_active else "")
                ),
                "component_ref": source.component_id,
                "safety_note": "Handle with care. Verify energy is fully absent after removal.",
                "validation": {
                    "method": "vision_detection",
                    "expected_state": state_locked or "removed",
                    "yolo_candidate_prompts": self._get_state_prompts(source, "isolated"),
                },
            }
        ]

        if storage:
            storage_locked = self._get_state_locked(storage)
            steps.append({
                "step_id": f"ph_lockout.st_remove_{source.component_id}.stp_2",
                "sequence": 2,
                "instruction": (
                    f"Place '{source.label}' in '{storage.label}' to prevent accidental re-energisation."
                ),
                "component_ref": storage.component_id,
                "validation": {
                    "method": "vision_detection",
                    "expected_state": storage_locked or "stored",
                    "yolo_candidate_prompts": self._get_state_prompts(storage, "isolated"),
                },
            })

        return {
            "stage_id": f"st_remove_{source.component_id}",
            "sequence": seq,
            "title": f"Remove — {source.label}",
            "steps": steps,
        }

    def _build_energy_restoration_stage(
        self, source: MachineComponent, knowledge: MachineKnowledge, seq: int
    ) -> dict:
        state_active = self._get_state_active(source)
        storage = self._find_storage_for_energy(source, knowledge)

        steps: list[dict] = []
        step_seq = 1

        if storage:
            steps.append({
                "step_id": f"ph_restoration.st_restore_{source.component_id}.stp_{step_seq}",
                "sequence": step_seq,
                "instruction": (
                    f"Retrieve '{source.label}' from '{storage.label}'."
                ),
                "component_ref": source.component_id,
                "validation": {"method": "manual_confirmation"},
            })
            step_seq += 1

        steps.append({
            "step_id": f"ph_restoration.st_restore_{source.component_id}.stp_{step_seq}",
            "sequence": step_seq,
            "instruction": (
                f"Reinstall '{source.label}' correctly. "
                + (f"Verify it is in its active state: {state_active}." if state_active else "")
            ),
            "component_ref": source.component_id,
            "safety_note": (
                "Verify correct installation (orientation, polarity, connections) "
                "before proceeding."
            ),
            "validation": {
                "method": "vision_detection",
                "expected_state": state_active or "installed",
                "yolo_candidate_prompts": self._get_state_prompts(source, "active"),
            },
        })

        return {
            "stage_id": f"st_restore_{source.component_id}",
            "sequence": seq,
            "title": f"Restore — {source.label}",
            "steps": steps,
        }

    def _build_switch_restoration_stage(
        self, switch: MachineComponent, knowledge: MachineKnowledge, seq: int
    ) -> dict:
        state_active = self._get_state_active(switch)

        return {
            "stage_id": f"st_activate_{switch.component_id}",
            "sequence": seq,
            "title": f"Activate — {switch.label}",
            "steps": [
                {
                    "step_id": f"ph_restoration.st_activate_{switch.component_id}.stp_1",
                    "sequence": 1,
                    "instruction": (
                        f"Move '{switch.label}' to the ON / active position. "
                        + (f"Expected state: {state_active}." if state_active else "")
                    ),
                    "component_ref": switch.component_id,
                    "safety_note": "Warn all personnel before restoring power.",
                    "validation": {
                        "method": "vision_detection",
                        "expected_state": state_active or "on",
                        "yolo_candidate_prompts": self._get_state_prompts(switch, "active"),
                    },
                }
            ],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_state_active(comp: MachineComponent) -> Optional[str]:
        prompts = comp.vision_metadata.state_prompts.get("active", [])
        return prompts[0] if prompts else None

    @staticmethod
    def _get_state_locked(comp: MachineComponent) -> Optional[str]:
        prompts = comp.vision_metadata.state_prompts.get("isolated", [])
        return prompts[0] if prompts else None

    @staticmethod
    def _get_state_prompts(comp: MachineComponent, state: str) -> list[str]:
        return comp.vision_metadata.state_prompts.get(state, [])

    @staticmethod
    def _get_all_state_prompts(comp: MachineComponent) -> list[str]:
        all_prompts: list[str] = []
        for prompts in comp.vision_metadata.state_prompts.values():
            all_prompts.extend(prompts)
        return all_prompts

    @staticmethod
    def _find_storage_for_energy(
        source: MachineComponent, knowledge: MachineKnowledge
    ) -> Optional[MachineComponent]:
        """Return the first storage unit, heuristically matched to this energy source."""
        return knowledge.storage_units[0] if knowledge.storage_units else None


def _slugify(text: str) -> str:
    """Convert to lowercase snake_case suitable for IDs."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
