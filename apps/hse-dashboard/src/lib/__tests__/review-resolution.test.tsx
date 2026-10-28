// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DraftReview } from "@/pages/DraftReview";
import { ReviewMetricsPanel } from "@/components/review/ReviewMetricsPanel";
import { useReviewStore } from "@/store/reviewStore";
import type { ProcedureVersionRead } from "@/types/procedure";

const state = vi.hoisted(() => ({ procedure: {} as Record<string, unknown>, save: vi.fn(), resolve: vi.fn() }));
vi.mock("@/hooks/useProcedures", () => ({
  useProcedure: () => ({ data: state.procedure }),
  useUpdateDraft: () => ({ mutateAsync: state.save, isPending: false }),
  useResolveClarification: () => ({ mutateAsync: state.resolve, isPending: false }),
  useApproveProcedure: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePublishProcedure: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("@/components/review/WorkflowReviewPanel", () => ({ WorkflowReviewPanel: () => null }));

const fixture = (): ProcedureVersionRead => ({ id: "draft", version_number: "1", status: "draft_pending_review", created_by: "author",
  workflow_definition: { schema_version: "2.0", components: [{ component_id: "C06", invariant_features: [{ description: "Mark" }] }],
    phases: [{ phase_id: "phase", stages: [{ stage_id: "stage", steps: [{ step_id: "step", instruction: "Check", diagnostics: [] }] }] }],
    technical_facts: [{ fact_id: "fact", citation_status: "unmatched" }],
    clarifications_required: [{ id: "q", question: "Confirmer le verrou", status: "unresolved", related_component_ids: ["C06"],
      affected_step_ids: ["step"], resolution: { answer: "Verrou confirmé", rationale: "Inspection terrain" } }],
    validation_diagnostics: [{ code: "CLARIFICATION_OPEN", severity: "blocking", entity_id: "q" }],
  },
} as unknown as ProcedureVersionRead);

beforeEach(() => {
  vi.clearAllMocks();
  const version = fixture();
  state.procedure = { id: "machine", machine_id: "machine", title: "Test", review_version: version };
  useReviewStore.getState().load(version);
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

function renderReview() {
  render(<MemoryRouter initialEntries={["/procedures/machine"]}><Routes>
    <Route path="/procedures/:procedureId" element={<DraftReview />} />
  </Routes></MemoryRouter>);
  fireEvent.click(screen.getAllByRole("button", { name: /Publier \(1 point/ })[0]);
}

describe("central resolution and reactive metrics", () => {
  it("persists pending citations and sends complete confirmations, using prefilled answers", async () => {
    renderReview();
    const pending = { ...useReviewStore.getState().draft!, technical_facts: [{ fact_id: "fact", citation_status: "manual_verified" }] };
    act(() => useReviewStore.getState().setDraft(pending));
    const version = fixture();
    const order: string[] = [];
    state.save.mockImplementation(async () => { order.push("save"); return { ...version, workflow_definition: pending }; });
    state.resolve.mockImplementation(async () => {
      order.push("resolve");
      return { ...version, workflow_definition: { ...pending, clarifications_required: [{ ...pending.clarifications_required![0],
        status: "resolved", affected_steps_reviewed: true, resolution: { answer: "Verrou confirmé", answer_complete: true } }] } };
    });
    fireEvent.click(screen.getByRole("button", { name: "Appliquer globalement" }));
    await waitFor(() => expect(order).toEqual(["save", "resolve"]));
    expect(state.resolve).toHaveBeenCalledWith(expect.objectContaining({ answer: "Verrou confirmé", rationale: "Inspection terrain",
      answer_complete: true, affected_steps_reviewed: true }));
    await waitFor(() => expect(useReviewStore.getState().draft!.clarifications_required![0].status).toBe("resolved"));
    expect(useReviewStore.getState().isDirty()).toBe(false);
  });
  it("shows server failure and keeps the point unresolved", async () => {
    state.resolve.mockRejectedValue(new Error("Resolution failed"));
    renderReview();
    fireEvent.click(screen.getByRole("button", { name: "Appliquer globalement" }));
    await screen.findByText("Resolution failed");
    expect(useReviewStore.getState().draft!.clarifications_required![0].status).toBe("unresolved");
  });
  it("shows identical confidence in the ring, bar and publication badge", () => {
    const wf = fixture().workflow_definition;
    wf.technical_facts = [{ citation_status: "manual_verified" }];
    wf.clarifications_required = [];
    wf.validation_diagnostics = [];
    useReviewStore.getState().setDraft(wf);
    render(<ReviewMetricsPanel version={null} />);
    expect(screen.getAllByText("100%")).toHaveLength(2);
    expect(screen.getByText("Prêt pour publication — 0 point bloquant")).toBeTruthy();
    act(() => useReviewStore.getState().setDraft({ ...wf, clarifications_required: [{ id: "new", status: "unresolved" }] }));
    expect(screen.getAllByText("96%")).toHaveLength(2);
    expect(screen.getByText("Non prêt — 1 point bloquant")).toBeTruthy();
  });
});
