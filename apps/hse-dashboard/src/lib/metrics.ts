/**
 * Review metrics — computed client-side from the working draft.
 *
 * These power the "Review Metrics" panel: generation confidence, review
 * completion, pending fields, approval readiness, and risk warnings.
 */

import type { ProcedureVersionRead } from "@/types/procedure";
import type { WorkflowDefinition } from "@/types/workflow";
import { countSteps, flattenSteps, getMetadata, listComponents } from "./workflow";

export interface ReviewMetrics {
  /** Mean extraction confidence reported by the generator (0..1). */
  generationConfidence: number | null;
  /** Number of low-confidence components (< 0.6) the reviewer should verify. */
  lowConfidenceComponents: number;
  componentCount: number;
  stepCount: number;
  /** Steps still missing reviewer-required fields (instruction / validation). */
  pendingFields: PendingField[];
  /** Open structural validation errors stored on the version. */
  openValidationErrors: number;
  /** Generator warnings carried in _generation_metadata. */
  riskWarnings: { code: string; message: string }[];
  /** 0..1 completion across the checklist below. */
  reviewCompletion: number;
  /** True when the draft is ready to recommend for approval. */
  approvalReady: boolean;
  blockers: string[];
}

export interface PendingField {
  stepId: string;
  reason: string;
}


export function computeMetrics(
  wf: WorkflowDefinition,
  version: ProcedureVersionRead | null,
): ReviewMetrics {
  const meta = getMetadata(wf);
  const components = listComponents(wf);
  const steps = flattenSteps(wf);

  const lowConfidenceComponents = components.filter(
    (c) => (c.confidence_threshold_suggestion ?? 0) < 0.6,
  ).length;

  const pendingFields: PendingField[] = [];
  for (const { step } of steps) {
    if (!step.instruction || !step.instruction.trim()) {
      pendingFields.push({ stepId: step.step_id, reason: "empty instruction" });
    }
    const verification = step.verification ?? step.validation;
    if (!verification?.method) {
      pendingFields.push({ stepId: step.step_id, reason: "missing verification method" });
    } else if (
      (verification.method === "vision_detection" || verification.method === "vision") &&
      (!(verification.yolo_candidate_prompts as unknown[] | undefined) || (verification.yolo_candidate_prompts as unknown[]).length === 0)
    ) {
      pendingFields.push({
        stepId: step.step_id,
        reason: "vision step without YOLO prompts",
      });
    }
  }

  const openValidationErrors = version?.validation_errors?.length ?? 0;
  const riskWarnings = meta.validation_warnings ?? [];

  // Completion checklist — equal-weighted booleans.
  const checklist: boolean[] = [
    steps.length > 0,
    pendingFields.length === 0,
    openValidationErrors === 0,
    components.length > 0,
    lowConfidenceComponents === 0,
  ];
  const reviewCompletion =
    checklist.filter(Boolean).length / checklist.length;

  const blockers: string[] = [];
  if (openValidationErrors > 0)
    blockers.push(`${openValidationErrors} structural validation error(s)`);
  if (pendingFields.length > 0)
    blockers.push(`${pendingFields.length} step field(s) incomplete`);
  if (steps.length === 0) blockers.push("procedure has no steps");

  return {
    generationConfidence: typeof meta.overall_confidence === "number" ? meta.overall_confidence : null,
    lowConfidenceComponents,
    componentCount: components.length,
    stepCount: countSteps(wf),
    pendingFields,
    openValidationErrors,
    riskWarnings,
    reviewCompletion,
    approvalReady: blockers.length === 0,
    blockers,
  };
}
