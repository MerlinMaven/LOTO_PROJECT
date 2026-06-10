import { describe, expect, it } from "vitest";
import { diffWorkflows } from "../diff";
import type { WorkflowDefinition } from "@/types/workflow";

// ── Fixture helpers ───────────────────────────────────────────────────────────

function baseWf(): WorkflowDefinition {
  return {
    phases: [
      {
        phase_id: "ph_1",
        phase_type: "lockout",
        sequence: 1,
        title: "Lockout",
        stages: [
          {
            stage_id: "st_1",
            sequence: 1,
            title: "Isolation",
            steps: [
              {
                step_id: "stp_1",
                sequence: 1,
                instruction: "Turn off main switch",
                safety_note: "Wear PPE",
                warnings: ["risk of arc flash"],
                validation: { method: "vision_detection" },
              },
            ],
          },
        ],
      },
    ],
    _generation_metadata: {
      yolo_metadata: {
        main_switch: {
          component_id: "main_switch",
          label: "Main Switch",
          component_type: "isolation_switch",
          candidate_detection_prompts: ["white rocker switch"],
          state_prompts: { active: ["switch ON"] },
          confidence_threshold_suggestion: 0.85,
          detection_difficulty: "medium",
          notes_for_reviewer: "",
        },
      },
    },
  };
}

// ── No changes ────────────────────────────────────────────────────────────────

describe("diffWorkflows — no changes", () => {
  it("returns empty array when original equals draft", () => {
    const wf = baseWf();
    expect(diffWorkflows(wf, structuredClone(wf))).toHaveLength(0);
  });
});

// ── Component changes ─────────────────────────────────────────────────────────

describe("diffWorkflows — component field changes", () => {
  it("detects a label modification", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft._generation_metadata!.yolo_metadata!["main_switch"].label = "E-Stop";
    const changes = diffWorkflows(orig, draft);
    const c = changes.find((x) => x.field === "label");
    expect(c).toBeDefined();
    expect(c?.kind).toBe("modified");
    expect(c?.before).toBe("Main Switch");
    expect(c?.after).toBe("E-Stop");
  });

  it("detects a component type change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft._generation_metadata!.yolo_metadata!["main_switch"].component_type =
      "energy_source";
    const changes = diffWorkflows(orig, draft);
    expect(changes.find((x) => x.field === "type")).toBeDefined();
  });

  it("detects a state prompt change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft._generation_metadata!.yolo_metadata!["main_switch"].state_prompts = {
      active: ["switch flipped up"],
    };
    const changes = diffWorkflows(orig, draft);
    expect(
      changes.find((x) => x.field === "state prompt · active"),
    ).toBeDefined();
  });

  it("detects a confidence threshold change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft._generation_metadata!.yolo_metadata![
      "main_switch"
    ].confidence_threshold_suggestion = 0.6;
    const changes = diffWorkflows(orig, draft);
    expect(changes.find((x) => x.field === "confidence threshold")).toBeDefined();
  });
});

// ── Step changes ──────────────────────────────────────────────────────────────

describe("diffWorkflows — step field changes", () => {
  it("detects an instruction change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft.phases[0].stages[0].steps[0].instruction = "De-energise breaker";
    const changes = diffWorkflows(orig, draft);
    const c = changes.find((x) => x.field === "instruction");
    expect(c?.kind).toBe("modified");
    expect(c?.before).toBe("Turn off main switch");
    expect(c?.after).toBe("De-energise breaker");
  });

  it("detects a safety note change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft.phases[0].stages[0].steps[0].safety_note = "Full face shield required";
    const changes = diffWorkflows(orig, draft);
    expect(changes.find((x) => x.field === "safety note")).toBeDefined();
  });

  it("detects a warnings list change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft.phases[0].stages[0].steps[0].warnings = ["arc flash", "stored energy"];
    const changes = diffWorkflows(orig, draft);
    expect(changes.find((x) => x.field === "warnings")).toBeDefined();
  });

  it("detects a validation method change", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft.phases[0].stages[0].steps[0].validation!.method =
      "manual_confirmation";
    const changes = diffWorkflows(orig, draft);
    expect(
      changes.find((x) => x.field === "validation method"),
    ).toBeDefined();
  });

  it("reports sequence change when step is reordered", () => {
    const orig = baseWf();
    // Add a second step so we can reorder
    orig.phases[0].stages[0].steps.push({
      step_id: "stp_2",
      sequence: 2,
      instruction: "Apply padlock",
    });
    const draft = structuredClone(orig);
    // Swap sequences
    draft.phases[0].stages[0].steps[0].sequence = 2;
    draft.phases[0].stages[0].steps[1].sequence = 1;
    const changes = diffWorkflows(orig, draft);
    expect(changes.some((x) => x.field === "sequence")).toBe(true);
  });
});

// ── Added / removed ───────────────────────────────────────────────────────────

describe("diffWorkflows — added / removed", () => {
  it("marks a removed step as 'removed'", () => {
    const orig = baseWf();
    orig.phases[0].stages[0].steps.push({
      step_id: "stp_2",
      sequence: 2,
      instruction: "Apply padlock",
    });
    const draft = structuredClone(orig);
    // Remove stp_2 from draft
    draft.phases[0].stages[0].steps = draft.phases[0].stages[0].steps.filter(
      (s) => s.step_id !== "stp_2",
    );
    const changes = diffWorkflows(orig, draft);
    const c = changes.find(
      (x) => x.scope.includes("stp_2") && x.kind === "removed",
    );
    expect(c).toBeDefined();
  });
});

// ── Scope grouping ────────────────────────────────────────────────────────────

describe("diffWorkflows — scope naming", () => {
  it("prefixes component changes with 'Component ·'", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft._generation_metadata!.yolo_metadata!["main_switch"].label = "New";
    const changes = diffWorkflows(orig, draft);
    expect(changes[0].scope).toMatch(/^Component ·/);
  });

  it("prefixes step changes with 'Step ·'", () => {
    const orig = baseWf();
    const draft = structuredClone(orig);
    draft.phases[0].stages[0].steps[0].instruction = "New instruction";
    const changes = diffWorkflows(orig, draft);
    expect(changes[0].scope).toMatch(/^Step ·/);
  });
});
