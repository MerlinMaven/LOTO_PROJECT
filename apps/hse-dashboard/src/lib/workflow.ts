/**
 * Pure, immutable helpers for reading and transforming a WorkflowDefinition.
 *
 * Kept framework-free so they are trivially unit-testable and reusable by the
 * Zustand store, the diff engine, and the metrics calculator.
 */

import type {
  GenerationMetadata,
  WorkflowDefinition,
  WorkflowPhase,
  WorkflowStep,
  YoloComponentMetadata,
} from "@/types/workflow";

export function deepClone<T>(value: T): T {
  // structuredClone is available in all evergreen browsers and jsdom >= 22.
  return structuredClone(value);
}

export const PHASE_LABELS: Record<string, string> = {
  preparation: "Préparation", consignation: "Consignation", maintenance: "Maintenance",
  restoration: "Déconsignation / remise en service",
};
export function phaseLabel(type: string): string {
  const key = type.toLowerCase();
  const aliases: Record<string, string> = { lockout: "consignation", isolation: "consignation",
    "accès": "maintenance", acces: "maintenance", intervention: "maintenance", deconsignation: "restoration" };
  return PHASE_LABELS[aliases[key] ?? key] ?? type;
}

/** Explicit HSE edit: preserve verification/guidance separately and never change the loaded original. */
export function moveStepToPhase(wf: WorkflowDefinition, stepId: string, target: string): WorkflowDefinition {
  const next = deepClone(wf);
  let moved: WorkflowStep | undefined;
  for (const phase of next.phases ?? []) for (const stage of phase.stages ?? []) {
    const index = stage.steps.findIndex(s => s.step_id === stepId);
    if (index >= 0) moved = stage.steps.splice(index, 1)[0];
  }
  if (!moved) return wf;
  moved.execution_phase = target;
  moved.guidance ??= { component_refs: moved.component_refs ?? [], observable_cues: moved.verification?.criteria ?? [] };
  if (target === "maintenance") moved.verification = { ...moved.verification,
    method: "human_confirmation", required_evidence: ["Attestation de l'opérateur"] };
  let phase = next.phases?.find(p => p.phase_type === target);
  if (!phase) {
    phase = { phase_id: `review-${target}`, phase_type: target, title: phaseLabel(target), sequence: 1, stages: [] };
    next.phases = [...(next.phases ?? []), phase];
  }
  if (!phase.stages.length) phase.stages.push({ stage_id: `${phase.phase_id}-actions`, title: phaseLabel(target), sequence: 1, steps: [] });
  phase.stages[0].steps.push(moved);
  next.phases = (next.phases ?? []).filter(p => p.stages.some(s => s.steps.length));
  const order = Object.keys(PHASE_LABELS);
  next.phases.sort((a,b) => (order.indexOf(a.phase_type)+1 || 99) - (order.indexOf(b.phase_type)+1 || 99));
  next.phases.forEach((p,i) => { p.sequence=i+1; p.stages.forEach(s => s.steps.forEach((a,j) => a.sequence=j+1)); });
  return next;
}

export function getMetadata(wf: WorkflowDefinition): GenerationMetadata {
  return wf._generation_metadata ?? {};
}

export function listComponents(wf: WorkflowDefinition): YoloComponentMetadata[] {
  const yolo = getMetadata(wf).yolo_metadata ?? {};
  return Object.values(yolo);
}

export function getComponent(
  wf: WorkflowDefinition,
  componentId: string,
): YoloComponentMetadata | undefined {
  return getMetadata(wf).yolo_metadata?.[componentId];
}

/** Flat list of every step, annotated with its phase/stage location. */
export interface FlatStep {
  phaseId: string;
  phaseType: string;
  stageId: string;
  step: WorkflowStep;
}

export function flattenSteps(wf: WorkflowDefinition): FlatStep[] {
  const out: FlatStep[] = [];
  for (const phase of wf.phases ?? []) {
    for (const stage of phase.stages ?? []) {
      for (const step of stage.steps ?? []) {
        out.push({
          phaseId: phase.phase_id,
          phaseType: String(phase.phase_type),
          stageId: stage.stage_id,
          step,
        });
      }
    }
  }
  return out;
}

export function countSteps(wf: WorkflowDefinition): number {
  return flattenSteps(wf).length;
}

// ── Immutable mutators ───────────────────────────────────────────────────────

/** Patch a component's vision metadata, returning a new WorkflowDefinition. */
export function patchComponent(
  wf: WorkflowDefinition,
  componentId: string,
  patch: Partial<YoloComponentMetadata>,
): WorkflowDefinition {
  const next = deepClone(wf);
  const meta = (next._generation_metadata ??= {});
  const yolo = (meta.yolo_metadata ??= {});
  const existing = yolo[componentId];
  if (existing) {
    yolo[componentId] = { ...existing, ...patch };
  }
  return next;
}

/** Patch a single step located by phase/stage/step id. */
export function patchStep(
  wf: WorkflowDefinition,
  phaseId: string,
  stageId: string,
  stepId: string,
  patch: Partial<WorkflowStep>,
): WorkflowDefinition {
  const next = deepClone(wf);
  for (const phase of next.phases) {
    if (phase.phase_id !== phaseId) continue;
    for (const stage of phase.stages) {
      if (stage.stage_id !== stageId) continue;
      stage.steps = stage.steps.map((s) =>
        s.step_id === stepId ? { ...s, ...patch } : s,
      );
    }
  }
  return next;
}

/**
 * Move a step up/down within its stage, re-numbering `sequence` to stay
 * contiguous. Returns a new WorkflowDefinition (no-op if already at the edge).
 */
export function moveStep(
  wf: WorkflowDefinition,
  phaseId: string,
  stageId: string,
  stepId: string,
  direction: "up" | "down",
): WorkflowDefinition {
  const next = deepClone(wf);
  for (const phase of next.phases) {
    if (phase.phase_id !== phaseId) continue;
    for (const stage of phase.stages) {
      if (stage.stage_id !== stageId) continue;
      const idx = stage.steps.findIndex((s) => s.step_id === stepId);
      if (idx === -1) continue;
      const swapWith = direction === "up" ? idx - 1 : idx + 1;
      if (swapWith < 0 || swapWith >= stage.steps.length) continue;
      [stage.steps[idx], stage.steps[swapWith]] = [
        stage.steps[swapWith],
        stage.steps[idx],
      ];
      stage.steps.forEach((s, i) => (s.sequence = i + 1));
    }
  }
  return next;
}

export function findPhase(
  wf: WorkflowDefinition,
  phaseId: string,
): WorkflowPhase | undefined {
  return wf.phases?.find((p) => p.phase_id === phaseId);
}
