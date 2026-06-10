import { describe, expect, it } from "vitest";
import { computeMetrics } from "../metrics";
import type { WorkflowDefinition } from "@/types/workflow";
import type { ProcedureVersionRead } from "@/types/procedure";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function goodWf(): WorkflowDefinition {
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
                validation: { method: "manual_confirmation" },
              },
            ],
          },
        ],
      },
    ],
    _generation_metadata: {
      overall_confidence: 0.9,
      yolo_metadata: {
        main_switch: {
          component_id: "main_switch",
          label: "Main Switch",
          component_type: "isolation_switch",
          candidate_detection_prompts: ["white rocker switch"],
          state_prompts: {},
          confidence_threshold_suggestion: 0.85,
          detection_difficulty: "medium",
          notes_for_reviewer: "",
        },
      },
      validation_warnings: [],
    },
  };
}

function makeVersion(
  overrides: Partial<ProcedureVersionRead> = {},
): ProcedureVersionRead {
  return {
    id: "ver_1",
    procedure_id: "proc_1",
    version_number: "1.0",
    status: "draft_pending_review",
    generation_source: "llm_text",
    llm_model_used: null,
    schema_version: "1",
    workflow_definition: goodWf(),
    validation_errors: null,
    created_by: "gen_pipeline",
    submitted_for_review_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    latest_approval: null,
    ...overrides,
  };
}

// ── Approval-ready path ───────────────────────────────────────────────────────

describe("computeMetrics — all-good draft", () => {
  it("is approval-ready with zero blockers", () => {
    const m = computeMetrics(goodWf(), makeVersion());
    expect(m.approvalReady).toBe(true);
    expect(m.blockers).toHaveLength(0);
  });

  it("reports correct step and component counts", () => {
    const m = computeMetrics(goodWf(), makeVersion());
    expect(m.stepCount).toBe(1);
    expect(m.componentCount).toBe(1);
  });

  it("reads overall_confidence from metadata", () => {
    const m = computeMetrics(goodWf(), makeVersion());
    expect(m.generationConfidence).toBe(0.9);
  });

  it("has zero pending fields", () => {
    const m = computeMetrics(goodWf(), makeVersion());
    expect(m.pendingFields).toHaveLength(0);
  });

  it("has 100% review completion", () => {
    const m = computeMetrics(goodWf(), makeVersion());
    expect(m.reviewCompletion).toBe(1);
  });
});

// ── Empty instruction ─────────────────────────────────────────────────────────

describe("computeMetrics — empty instruction", () => {
  it("adds a pending field for empty instruction", () => {
    const wf = goodWf();
    wf.phases[0].stages[0].steps[0].instruction = "";
    const m = computeMetrics(wf, makeVersion());
    expect(m.pendingFields.some((f) => f.reason === "empty instruction")).toBe(
      true,
    );
  });

  it("is not approval-ready", () => {
    const wf = goodWf();
    wf.phases[0].stages[0].steps[0].instruction = "   ";
    const m = computeMetrics(wf, makeVersion());
    expect(m.approvalReady).toBe(false);
  });
});

// ── No steps ──────────────────────────────────────────────────────────────────

describe("computeMetrics — no steps", () => {
  it("includes 'procedure has no steps' blocker", () => {
    const wf: WorkflowDefinition = {
      phases: [],
      _generation_metadata: { overall_confidence: 0.9 },
    };
    const m = computeMetrics(wf, makeVersion());
    expect(m.blockers).toContain("procedure has no steps");
    expect(m.approvalReady).toBe(false);
  });
});

// ── Validation errors ─────────────────────────────────────────────────────────

describe("computeMetrics — validation errors from version", () => {
  it("counts errors from version.validation_errors", () => {
    const m = computeMetrics(
      goodWf(),
      makeVersion({ validation_errors: ["phase order invalid", "missing step"] }),
    );
    expect(m.openValidationErrors).toBe(2);
    expect(m.approvalReady).toBe(false);
    expect(
      m.blockers.some((b) => b.includes("2 structural validation error")),
    ).toBe(true);
  });

  it("zero when validation_errors is null", () => {
    const m = computeMetrics(goodWf(), makeVersion({ validation_errors: null }));
    expect(m.openValidationErrors).toBe(0);
  });
});

// ── Low-confidence components ─────────────────────────────────────────────────

describe("computeMetrics — low confidence components", () => {
  it("counts components below 0.6 threshold", () => {
    const wf = goodWf();
    wf._generation_metadata!.yolo_metadata!["main_switch"]
      .confidence_threshold_suggestion = 0.45;
    const m = computeMetrics(wf, makeVersion());
    expect(m.lowConfidenceComponents).toBe(1);
  });

  it("does not count components at or above 0.6", () => {
    const wf = goodWf();
    wf._generation_metadata!.yolo_metadata!["main_switch"]
      .confidence_threshold_suggestion = 0.6;
    const m = computeMetrics(wf, makeVersion());
    expect(m.lowConfidenceComponents).toBe(0);
  });
});

// ── Vision step without YOLO prompts ─────────────────────────────────────────

describe("computeMetrics — vision step without YOLO prompts", () => {
  it("adds pending field for vision_detection step without yolo_candidate_prompts", () => {
    const wf = goodWf();
    wf.phases[0].stages[0].steps[0].validation = {
      method: "vision_detection",
      yolo_candidate_prompts: [],
    };
    const m = computeMetrics(wf, makeVersion());
    expect(
      m.pendingFields.some((f) =>
        f.reason.includes("vision step without YOLO prompts"),
      ),
    ).toBe(true);
  });

  it("does not flag vision step that has prompts", () => {
    const wf = goodWf();
    wf.phases[0].stages[0].steps[0].validation = {
      method: "vision_detection",
      yolo_candidate_prompts: ["white rocker switch"],
    };
    const m = computeMetrics(wf, makeVersion());
    expect(
      m.pendingFields.some((f) => f.reason.includes("YOLO")),
    ).toBe(false);
  });
});

// ── Risk warnings ─────────────────────────────────────────────────────────────

describe("computeMetrics — risk warnings", () => {
  it("surfaces generator validation_warnings from metadata", () => {
    const wf = goodWf();
    wf._generation_metadata!.validation_warnings = [
      { code: "LOW_CONF", message: "confidence below threshold" },
    ];
    const m = computeMetrics(wf, makeVersion());
    expect(m.riskWarnings).toHaveLength(1);
    expect(m.riskWarnings[0].code).toBe("LOW_CONF");
  });
});

// ── null version ──────────────────────────────────────────────────────────────

describe("computeMetrics — null version", () => {
  it("still works without a version (no validation errors counted)", () => {
    const m = computeMetrics(goodWf(), null);
    expect(m.openValidationErrors).toBe(0);
    expect(m.approvalReady).toBe(true);
  });
});
