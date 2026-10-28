import type { ProcedureListItem } from "@/types/procedure";

type Item = Record<string, unknown>;
export interface ConfidenceBreakdown {
  score: number;
  breakdown: {
    structureScore: number;
    blockingScore: number;
    citationScore: number;
    blockingCount: number;
    unmatchedCount: number;
    totalFacts: number;
  };
}
const records = (value: unknown): Item[] => Array.isArray(value) ? value.filter(
  (item): item is Item => !!item && typeof item === "object"
) : [];
function steps(workflow: Item): Item[] {
  return records(workflow.phases).flatMap((p) => records(p.stages).flatMap((s) => records(s.steps)));
}
export function isClarificationResolved(question: Item): boolean {
  const resolution = (question.resolution ?? {}) as Item;
  return question.status === "resolved" && Boolean(String(resolution.answer ?? "").trim()) &&
    resolution.answer_complete === true && question.affected_steps_reviewed === true;
}
/** The same deduplicated business issues power every counter and the HSE pillar. */
export function getBusinessBlockers(workflow: Item): Item[] {
  const questions = records(workflow.clarifications_required);
  const issues = new Map<string, Item>();
  questions.filter((q) => !isClarificationResolved(q)).forEach((q, index) => {
    issues.set(`clarification:${q.id ?? index}`, { ...q, message: q.question });
  });
  const diagnostics: Item[] = [...records(workflow.validation_diagnostics),
    ...steps(workflow).flatMap((step) => records(step.diagnostics).map((d) => ({ entity_id: step.step_id, ...d })))];
  diagnostics.forEach((d) => {
    const code = String(d.code ?? "").toLowerCase();
    const category = String(d.category ?? "").toLowerCase();
    const severity = String(d.severity ?? "").toLowerCase();
    if (d.resolved || !["blocking", "error"].includes(severity) || category === "source_integrity" ||
        code.includes("fact_citation") || code === "verification_method_unsupported_by_operator_client") return;
    if (["clarification_open", "clarification_resolution_incomplete", "clarification_review_incomplete"].includes(code) &&
        questions.some((q) => String(q.id) === String(d.entity_id))) return;
    const key = `${code}:${d.entity_id ?? ""}:${code ? "" : d.message ?? ""}`;
    issues.set(key, d);
  });
  return [...issues.values()];
}
export function getBusinessBlockingCount(
  item: ProcedureListItem | { workflow_definition?: Item | null; open_validation_errors?: number }
): number {
  return item.workflow_definition ? getBusinessBlockers(item.workflow_definition).length : item.open_validation_errors ?? 0;
}
/** Shared with authoring-service confidence.py: extraction 60, HSE 20, sources 20. */
export function calculateConfidenceBreakdown(workflowOrItem?: Item | null): ConfidenceBreakdown | null {
  if (!workflowOrItem) return null;
  const wf = (workflowOrItem.workflow_definition && typeof workflowOrItem.workflow_definition === "object"
    ? workflowOrItem.workflow_definition : workflowOrItem) as Item;
  const components = records(wf.components);
  const hasVisuals = records(wf.visual_observations).length > 0 || components.some((c) =>
    records(c.invariant_features).length > 0 || records(c.physical_signatures).length > 0);
  const structureScore = (components.length > 0 ? 20 : 0) + (steps(wf).length > 0 ? 20 : 0) + (hasVisuals ? 20 : 0);
  const blockingCount = getBusinessBlockers(wf).length;
  const blockingScore = Math.max(0, 20 - blockingCount * 4);
  const facts = records(wf.technical_facts);
  const verifiedStatuses = new Set(["verified", "manual_verified", "inferred_absence", "typography_normalized"]);
  const unmatchedCount = facts.filter((f) => !verifiedStatuses.has(String(f.citation_status))).length;
  const citationScore = facts.length ? Math.round(20 * (facts.length - unmatchedCount) / facts.length) : 20;
  return { score: structureScore + blockingScore + citationScore,
    breakdown: { structureScore, blockingScore, citationScore, blockingCount, unmatchedCount, totalFacts: facts.length } };
}
export function calculateConfidenceScore(workflow?: Item | null): number | null {
  const result = calculateConfidenceBreakdown(workflow);
  return result ? result.score / 100 : null;
}
