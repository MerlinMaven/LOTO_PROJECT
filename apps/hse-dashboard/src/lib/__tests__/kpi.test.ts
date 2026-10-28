import { describe, it, expect } from "vitest";
import { calculateConfidenceBreakdown, getBusinessBlockingCount } from "../kpi";

const workflow = () => ({
  components: [{ component_id: "C06", physical_signatures: [{ description: "Repere visible" }] }],
  phases: [{ stages: [{ steps: [{ step_id: "check", diagnostics: [] }] }] }],
  technical_facts: [{ citation_status: "unmatched" }, { citation_status: "inferred_absence" }],
  clarifications_required: [{ id: "q", status: "unresolved", resolution: {}, affected_steps_reviewed: false }],
  validation_diagnostics: [{ code: "CLARIFICATION_OPEN", severity: "blocking", entity_id: "q" }],
});

describe("confidence and shared publication blockers", () => {
  it("increases through resolution and citation review to exactly 100", () => {
    const wf = workflow();
    const before = calculateConfidenceBreakdown(wf)!;
    expect(before.score).toBe(86);
    expect(before.breakdown.blockingCount).toBe(1);
    Object.assign(wf.clarifications_required[0], { status: "resolved", affected_steps_reviewed: true,
      resolution: { answer: "Decision HSE", answer_complete: true } });
    const resolved = calculateConfidenceBreakdown(wf)!;
    expect(resolved.score).toBe(90);
    expect(getBusinessBlockingCount({ workflow_definition: wf })).toBe(0);
    wf.technical_facts[0].citation_status = "manual_verified";
    expect(calculateConfidenceBreakdown(wf)).toEqual({ score: 100, breakdown: {
      structureScore: 60, blockingScore: 20, citationScore: 20,
      blockingCount: 0, unmatchedCount: 0, totalFacts: 2,
    } });
  });
  it("does not clear partial answers, double count mirrored diagnostics or ignore real errors", () => {
    const wf = workflow();
    Object.assign(wf.clarifications_required[0], { status: "resolved", resolution: { answer: "Partial" } });
    const problem = { code: "VERIFICATION_CRITERIA_REQUIRED", entity_id: "check", severity: "blocking" };
    wf.validation_diagnostics.push(problem);
    (wf.phases[0].stages[0].steps[0].diagnostics as unknown[]).push(problem);
    expect(calculateConfidenceBreakdown(wf)!.breakdown.blockingCount).toBe(2);
  });
  it("counts source verification separately and invents no extracted structure", () => {
    expect(calculateConfidenceBreakdown({})!.breakdown.structureScore).toBe(0);
    const wf = workflow();
    wf.validation_diagnostics.push({ code: "FACT_CITATION_UNVERIFIED", severity: "blocking", entity_id: "fact" });
    wf.validation_diagnostics.push({ code: "OLD_ERROR", severity: "blocking", entity_id: "old", resolved: true } as never);
    expect(calculateConfidenceBreakdown(wf)!.breakdown.blockingCount).toBe(1);
    expect(calculateConfidenceBreakdown({ workflow_definition: wf })).toEqual(calculateConfidenceBreakdown(wf));
  });
});
