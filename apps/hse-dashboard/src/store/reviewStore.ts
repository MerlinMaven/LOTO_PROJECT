/**
 * Draft review editing store.
 *
 * Holds two copies of the workflow_definition for the procedure under review:
 *   - `original`: the generated draft as last loaded from the server (diff base)
 *   - `draft`:    the reviewer's working copy
 *
 * All edit surfaces (component / workflow / vision panels) mutate `draft`
 * through these actions. The DiffViewer compares `draft` against `original`,
 * and the Save action ships `draft` to PATCH /procedures/{id}/draft. After a
 * successful save the server response becomes the new `original`.
 */

import { create } from "zustand";
import type { ProcedureVersionRead } from "@/types/procedure";
import type { WorkflowDefinition, WorkflowStep, YoloComponentMetadata } from "@/types/workflow";
import {
  deepClone,
  moveStep as moveStepFn,
  patchComponent,
  patchStep,
} from "@/lib/workflow";

interface ReviewState {
  versionId: string | null;
  original: WorkflowDefinition | null;
  initialDraft: WorkflowDefinition | null;
  draft: WorkflowDefinition | null;

  /** Load a version into the editor (resets any unsaved edits). */
  load: (version: ProcedureVersionRead) => void;
  /** Replace the working draft wholesale. */
  setDraft: (wf: WorkflowDefinition) => void;
  /** Discard edits, reverting to the loaded original. */
  reset: () => void;
  /** Accept a freshly-saved server version as the new diff base. */
  commitSaved: (version: ProcedureVersionRead) => void;

  patchComponent: (componentId: string, patch: Partial<YoloComponentMetadata>) => void;
  patchStep: (
    phaseId: string,
    stageId: string,
    stepId: string,
    patch: Partial<WorkflowStep>,
  ) => void;
  moveStep: (
    phaseId: string,
    stageId: string,
    stepId: string,
    direction: "up" | "down",
  ) => void;

  isDirty: () => boolean;
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  versionId: null,
  original: null,
  initialDraft: null,
  draft: null,

  load: (version) =>
    set({
      versionId: version.id,
      original: deepClone(version.workflow_definition),
      initialDraft: deepClone(version.workflow_definition),
      draft: deepClone(version.workflow_definition),
    }),

  setDraft: (wf) => set({ draft: wf }),

  reset: () => {
    const { original } = get();
    set({ draft: original ? deepClone(original) : null });
  },

  commitSaved: (version) =>
    set((state) => ({
      versionId: version.id,
      original: deepClone(version.workflow_definition),
      initialDraft: state.initialDraft || deepClone(version.workflow_definition),
      draft: deepClone(version.workflow_definition),
    })),

  patchComponent: (componentId, patch) => {
    const { draft } = get();
    if (!draft) return;
    set({ draft: patchComponent(draft, componentId, patch) });
  },

  patchStep: (phaseId, stageId, stepId, patch) => {
    const { draft } = get();
    if (!draft) return;
    set({ draft: patchStep(draft, phaseId, stageId, stepId, patch) });
  },

  moveStep: (phaseId, stageId, stepId, direction) => {
    const { draft } = get();
    if (!draft) return;
    set({ draft: moveStepFn(draft, phaseId, stageId, stepId, direction) });
  },

  isDirty: () => {
    const { original, draft } = get();
    if (!original || !draft) return false;
    return JSON.stringify(original) !== JSON.stringify(draft);
  },
}));
