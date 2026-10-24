/**
 * Workflow diff engine.
 *
 * Compares the generated draft (`original`) against the reviewer's working copy
 * (`draft`) and produces a flat list of field-level changes for the DiffViewer.
 *
 * It walks the meaningful, reviewer-editable surfaces — components (vision
 * metadata) and workflow steps — rather than doing a blind JSON deep-diff, so
 * the output reads in domain terms ("Step stp_1 · instruction").
 */

import type { WorkflowDefinition } from "@/types/workflow";
import { flattenSteps, listComponents } from "./workflow";

export type ChangeKind = "added" | "removed" | "modified";

export interface FieldChange {
  /** Grouping path, e.g. "Component · main_switch" or "Step · stp_1". */
  scope: string;
  field: string;
  kind: ChangeKind;
  before: string;
  after: string;
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(asText).join(" · ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function compareField(
  scope: string,
  field: string,
  before: unknown,
  after: unknown,
  out: FieldChange[],
): void {
  const b = asText(before);
  const a = asText(after);
  if (b === a) return;
  out.push({
    scope,
    field,
    kind: !b ? "added" : !a ? "removed" : "modified",
    before: b,
    after: a,
  });
}

export function diffWorkflows(
  original: WorkflowDefinition,
  draft: WorkflowDefinition,
): FieldChange[] {
  const changes: FieldChange[] = [];

  // ── Clarifications HSE & Arbitrages ───────────────────────────────────────
  const origClarifs = new Map(
    ((original.clarifications_required ?? []) as Array<Record<string, unknown>>).map((q) => [
      String(q.id),
      q,
    ])
  );
  const draftClarifs = (draft.clarifications_required ?? []) as Array<Record<string, unknown>>;

  for (const q of draftClarifs) {
    const qId = String(q.id);
    const prev = origClarifs.get(qId);
    const relatedComps = Array.isArray(q.related_component_ids)
      ? (q.related_component_ids as string[]).filter(Boolean)
      : [];
    const compLabel = relatedComps.length > 0 ? ` [${relatedComps.join(" / ")}]` : "";
    const questionText = String(q.question || qId);
    const scope = `Clarification HSE${compLabel} · ${questionText.length > 60 ? questionText.slice(0, 60) + "…" : questionText}`;

    const res = (q.resolution && typeof q.resolution === "object" ? q.resolution : {}) as Record<string, unknown>;
    const prevRes = (prev?.resolution && typeof prev.resolution === "object" ? prev.resolution : {}) as Record<string, unknown>;

    if (q.status === "resolved") {
      const currentVal = `${res.answer || "Décision validée"}${res.rationale ? ` — Justification : ${res.rationale}` : ""}`;
      const prevVal = prev && prev.status === "resolved" && prevRes.answer
        ? `${prevRes.answer}${prevRes.rationale ? ` — Justification : ${prevRes.rationale}` : ""}`
        : "";

      if (!prev || prev.status !== "resolved") {
        changes.push({
          scope,
          field: "Décision technique HSE",
          kind: "added",
          before: "À clarifier (En attente d'arbitrage)",
          after: currentVal,
        });
      } else if (currentVal !== prevVal) {
        changes.push({
          scope,
          field: "Décision technique HSE modifiée",
          kind: "modified",
          before: prevVal,
          after: currentVal,
        });
      }
    }
  }

  // ── Components (vision metadata) ───────────────────────────────────────────
  const origComponents = new Map(
    listComponents(original).map((c) => [c.component_id, c]),
  );
  for (const comp of listComponents(draft)) {
    const prev = origComponents.get(comp.component_id);
    const scope = `Component · ${comp.label || comp.component_id}`;
    if (!prev) {
      changes.push({
        scope,
        field: "component",
        kind: "added",
        before: "",
        after: comp.label,
      });
      continue;
    }
    compareField(scope, "label", prev.label, comp.label, changes);
    compareField(scope, "type", prev.component_type, comp.component_type, changes);
    compareField(
      scope,
      "statut clarification",
      Boolean((prev as unknown as Record<string, unknown>).clarification_needed) ? "À clarifier" : "Conforme",
      Boolean((comp as unknown as Record<string, unknown>).clarification_needed) ? "À clarifier" : "Conforme",
      changes,
    );
    compareField(
      scope,
      "detection prompts",
      prev.candidate_detection_prompts,
      comp.candidate_detection_prompts,
      changes,
    );
    compareField(
      scope,
      "confidence threshold",
      prev.confidence_threshold_suggestion,
      comp.confidence_threshold_suggestion,
      changes,
    );
    // State prompts (active / isolated / ...)
    const states = new Set([
      ...Object.keys(prev.state_prompts ?? {}),
      ...Object.keys(comp.state_prompts ?? {}),
    ]);
    for (const st of states) {
      compareField(
        scope,
        `state prompt · ${st}`,
        prev.state_prompts?.[st],
        comp.state_prompts?.[st],
        changes,
      );
    }
  }

  // ── Workflow steps ─────────────────────────────────────────────────────────
  const origSteps = new Map(flattenSteps(original).map((s) => [s.step.step_id, s]));
  const draftSteps = flattenSteps(draft);
  for (const { step } of draftSteps) {
    const prev = origSteps.get(step.step_id);
    const scope = `Step · ${step.step_id}`;
    if (!prev) {
      changes.push({
        scope,
        field: "step",
        kind: "added",
        before: "",
        after: step.instruction,
      });
      continue;
    }
    compareField(scope, "sequence", prev.step.sequence, step.sequence, changes);
    compareField(scope, "instruction", prev.step.instruction, step.instruction, changes);
    compareField(
      scope,
      "critères de vérification",
      prev.step.verification?.criteria ?? prev.step.validation?.criteria,
      step.verification?.criteria ?? step.validation?.criteria,
      changes,
    );
    compareField(scope, "safety note", prev.step.safety_note, step.safety_note, changes);
    compareField(
      scope,
      "rollback",
      prev.step.rollback_instruction,
      step.rollback_instruction,
      changes,
    );
    compareField(scope, "warnings", prev.step.warnings, step.warnings, changes);
    compareField(
      scope,
      "validation method",
      prev.step.verification?.method ?? prev.step.validation?.method,
      step.verification?.method ?? step.validation?.method,
      changes,
    );
    compareField(
      scope,
      "expected state",
      prev.step.validation?.expected_state,
      step.validation?.expected_state,
      changes,
    );
    compareField(
      scope,
      "yolo prompts",
      prev.step.validation?.yolo_candidate_prompts,
      step.validation?.yolo_candidate_prompts,
      changes,
    );
  }

  // Removed steps
  const draftIds = new Set(draftSteps.map((s) => s.step.step_id));
  for (const [id, { step }] of origSteps) {
    if (!draftIds.has(id)) {
      changes.push({
        scope: `Step · ${id}`,
        field: "step",
        kind: "removed",
        before: step.instruction,
        after: "",
      });
    }
  }

  return changes;
}
