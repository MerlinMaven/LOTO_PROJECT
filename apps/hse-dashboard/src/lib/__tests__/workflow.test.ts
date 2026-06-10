import { describe, expect, it } from "vitest";
import {
  countSteps,
  deepClone,
  flattenSteps,
  getComponent,
  getMetadata,
  listComponents,
  moveStep,
  patchComponent,
  patchStep,
} from "../workflow";
import type { WorkflowDefinition } from "@/types/workflow";

// ── Fixture ──────────────────────────────────────────────────────────────────

function makeWf(overrides: Partial<WorkflowDefinition> = {}): WorkflowDefinition {
  return {
    phases: [
      {
        phase_id: "ph_lockout",
        phase_type: "lockout",
        sequence: 1,
        title: "Lockout",
        stages: [
          {
            stage_id: "st_isolation",
            sequence: 1,
            title: "Energy isolation",
            steps: [
              {
                step_id: "stp_1",
                sequence: 1,
                instruction: "Turn off main switch",
                validation: { method: "vision_detection" },
              },
              {
                step_id: "stp_2",
                sequence: 2,
                instruction: "Apply padlock",
                validation: { method: "manual_confirmation" },
              },
            ],
          },
        ],
      },
      {
        phase_id: "ph_restoration",
        phase_type: "restoration",
        sequence: 2,
        title: "Restoration",
        stages: [
          {
            stage_id: "st_restore",
            sequence: 1,
            title: "Restore energy",
            steps: [
              {
                step_id: "stp_3",
                sequence: 1,
                instruction: "Remove padlock",
                validation: { method: "manual_confirmation" },
              },
            ],
          },
        ],
      },
    ],
    _generation_metadata: {
      overall_confidence: 0.88,
      yolo_metadata: {
        main_switch: {
          component_id: "main_switch",
          label: "Main Switch",
          component_type: "isolation_switch",
          candidate_detection_prompts: ["white rocker switch"],
          state_prompts: {
            active: ["switch in ON position"],
            isolated: ["switch in OFF position"],
          },
          confidence_threshold_suggestion: 0.85,
          detection_difficulty: "medium",
          notes_for_reviewer: "",
        },
        padlock: {
          component_id: "padlock",
          label: "Safety Padlock",
          component_type: "lockout_point",
          candidate_detection_prompts: ["red safety padlock"],
          state_prompts: { attached: ["padlock on hasp"] },
          confidence_threshold_suggestion: 0.75,
          detection_difficulty: "easy",
          notes_for_reviewer: "Verify colour matches site standard",
        },
      },
    },
    ...overrides,
  };
}

// ── deepClone ────────────────────────────────────────────────────────────────

describe("deepClone", () => {
  it("returns a value equal to the input", () => {
    const wf = makeWf();
    const cloned = deepClone(wf);
    expect(cloned).toEqual(wf);
  });

  it("returns a distinct object (no shared references)", () => {
    const wf = makeWf();
    const cloned = deepClone(wf);
    expect(cloned).not.toBe(wf);
    expect(cloned.phases[0]).not.toBe(wf.phases[0]);
  });
});

// ── getMetadata ──────────────────────────────────────────────────────────────

describe("getMetadata", () => {
  it("returns the embedded metadata block", () => {
    const wf = makeWf();
    expect(getMetadata(wf).overall_confidence).toBe(0.88);
  });

  it("returns empty object when metadata is absent", () => {
    const wf: WorkflowDefinition = { phases: [] };
    expect(getMetadata(wf)).toEqual({});
  });
});

// ── listComponents ────────────────────────────────────────────────────────────

describe("listComponents", () => {
  it("returns all YOLO components", () => {
    const wf = makeWf();
    const comps = listComponents(wf);
    expect(comps).toHaveLength(2);
    const ids = comps.map((c) => c.component_id);
    expect(ids).toContain("main_switch");
    expect(ids).toContain("padlock");
  });

  it("returns empty array when no yolo_metadata", () => {
    const wf: WorkflowDefinition = { phases: [] };
    expect(listComponents(wf)).toEqual([]);
  });
});

// ── getComponent ─────────────────────────────────────────────────────────────

describe("getComponent", () => {
  it("returns the component by id", () => {
    const wf = makeWf();
    const comp = getComponent(wf, "main_switch");
    expect(comp?.label).toBe("Main Switch");
  });

  it("returns undefined for unknown id", () => {
    const wf = makeWf();
    expect(getComponent(wf, "nonexistent")).toBeUndefined();
  });
});

// ── flattenSteps / countSteps ────────────────────────────────────────────────

describe("flattenSteps", () => {
  it("lists all steps with phase/stage annotations", () => {
    const wf = makeWf();
    const flat = flattenSteps(wf);
    expect(flat).toHaveLength(3);
    expect(flat[0].step.step_id).toBe("stp_1");
    expect(flat[0].phaseId).toBe("ph_lockout");
    expect(flat[0].stageId).toBe("st_isolation");
    expect(flat[2].step.step_id).toBe("stp_3");
    expect(flat[2].phaseId).toBe("ph_restoration");
  });

  it("returns empty for a workflow with no phases", () => {
    const wf: WorkflowDefinition = { phases: [] };
    expect(flattenSteps(wf)).toEqual([]);
  });
});

describe("countSteps", () => {
  it("counts the total steps across all phases", () => {
    expect(countSteps(makeWf())).toBe(3);
  });
});

// ── patchComponent ────────────────────────────────────────────────────────────

describe("patchComponent", () => {
  it("updates the target component field", () => {
    const wf = makeWf();
    const next = patchComponent(wf, "main_switch", { label: "Emergency Stop" });
    expect(getComponent(next, "main_switch")?.label).toBe("Emergency Stop");
  });

  it("does not mutate the original", () => {
    const wf = makeWf();
    patchComponent(wf, "main_switch", { label: "Emergency Stop" });
    expect(getComponent(wf, "main_switch")?.label).toBe("Main Switch");
  });

  it("leaves other components unchanged", () => {
    const wf = makeWf();
    const next = patchComponent(wf, "main_switch", { label: "X" });
    expect(getComponent(next, "padlock")?.label).toBe("Safety Padlock");
  });

  it("is a no-op for unknown component id", () => {
    const wf = makeWf();
    const next = patchComponent(wf, "unknown", { label: "X" });
    expect(listComponents(next)).toHaveLength(2);
  });
});

// ── patchStep ─────────────────────────────────────────────────────────────────

describe("patchStep", () => {
  it("updates the target step's instruction", () => {
    const wf = makeWf();
    const next = patchStep(
      wf,
      "ph_lockout",
      "st_isolation",
      "stp_1",
      { instruction: "De-energise main breaker" },
    );
    const step = flattenSteps(next).find((s) => s.step.step_id === "stp_1")?.step;
    expect(step?.instruction).toBe("De-energise main breaker");
  });

  it("does not mutate the original", () => {
    const wf = makeWf();
    patchStep(wf, "ph_lockout", "st_isolation", "stp_1", {
      instruction: "changed",
    });
    const orig = flattenSteps(wf).find((s) => s.step.step_id === "stp_1")?.step;
    expect(orig?.instruction).toBe("Turn off main switch");
  });

  it("leaves sibling steps unchanged", () => {
    const wf = makeWf();
    const next = patchStep(
      wf,
      "ph_lockout",
      "st_isolation",
      "stp_1",
      { instruction: "X" },
    );
    const stp2 = flattenSteps(next).find((s) => s.step.step_id === "stp_2")?.step;
    expect(stp2?.instruction).toBe("Apply padlock");
  });
});

// ── moveStep ──────────────────────────────────────────────────────────────────

describe("moveStep", () => {
  it("swaps the target step with the one above (up)", () => {
    const wf = makeWf();
    const next = moveStep(wf, "ph_lockout", "st_isolation", "stp_2", "up");
    const steps = flattenSteps(next)
      .filter((s) => s.stageId === "st_isolation")
      .map((s) => s.step);
    expect(steps[0].step_id).toBe("stp_2");
    expect(steps[1].step_id).toBe("stp_1");
  });

  it("re-numbers sequences after swap", () => {
    const wf = makeWf();
    const next = moveStep(wf, "ph_lockout", "st_isolation", "stp_2", "up");
    const steps = flattenSteps(next)
      .filter((s) => s.stageId === "st_isolation")
      .map((s) => s.step);
    expect(steps[0].sequence).toBe(1);
    expect(steps[1].sequence).toBe(2);
  });

  it("is a no-op when already at the top (up)", () => {
    const wf = makeWf();
    const next = moveStep(wf, "ph_lockout", "st_isolation", "stp_1", "up");
    const steps = flattenSteps(next)
      .filter((s) => s.stageId === "st_isolation")
      .map((s) => s.step.step_id);
    expect(steps).toEqual(["stp_1", "stp_2"]);
  });

  it("is a no-op when already at the bottom (down)", () => {
    const wf = makeWf();
    const next = moveStep(wf, "ph_lockout", "st_isolation", "stp_2", "down");
    const steps = flattenSteps(next)
      .filter((s) => s.stageId === "st_isolation")
      .map((s) => s.step.step_id);
    expect(steps).toEqual(["stp_1", "stp_2"]);
  });

  it("does not mutate the original", () => {
    const wf = makeWf();
    moveStep(wf, "ph_lockout", "st_isolation", "stp_2", "up");
    const ids = flattenSteps(wf)
      .filter((s) => s.stageId === "st_isolation")
      .map((s) => s.step.step_id);
    expect(ids).toEqual(["stp_1", "stp_2"]);
  });
});
