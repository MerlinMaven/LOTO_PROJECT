// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApprovalWorkflow } from "@/components/review/ApprovalWorkflow";
import { useReviewStore } from "@/store/reviewStore";
import { useAuthStore } from "@/store/authStore";
import type { ProcedureVersionRead } from "@/types/procedure";

const mutations = vi.hoisted(() => ({ save: vi.fn(), approve: vi.fn(), publish: vi.fn() }));
vi.mock("@/hooks/useProcedures", () => ({
  useUpdateDraft: () => ({ mutateAsync: mutations.save, isPending: false }),
  useApproveProcedure: () => ({ mutateAsync: mutations.approve, isPending: false }),
  usePublishProcedure: () => ({ mutateAsync: mutations.publish, isPending: false }),
}));

const version = { id: "draft", version_number: "1", status: "draft_pending_review", created_by: "author",
  workflow_definition: { schema_version: "2.0", technical_facts: [{ fact_id: "f", citation_status: "unmatched" }] },
} as unknown as ProcedureVersionRead;

beforeEach(() => {
  vi.clearAllMocks();
  useReviewStore.getState().load(version);
  useAuthStore.getState().setReviewer("hse_reviewer@smartloto.io");
});
afterEach(cleanup);

function openAndSign() {
  render(<ApprovalWorkflow procedureId="machine" version={version} authorId="author" />);
  fireEvent.click(screen.getByRole("button", { name: "Approuver la procédure" }));
  expect((screen.getByLabelText(/Nom complet/) as HTMLInputElement).value).toBe("hse_reviewer@smartloto.io");
  expect((screen.getByRole("button", { name: "Approuver & Publier" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/Je confirme la revue HSE/));
}

describe("formal approval persistence", () => {
  it("saves locally verified citations before signing and publishes the returned revision", async () => {
    const pending = { ...version.workflow_definition, technical_facts: [{ fact_id: "f", citation_status: "manual_verified" }] };
    useReviewStore.getState().setDraft(pending);
    const order: string[] = [];
    mutations.save.mockImplementation(async () => { order.push("save"); return { ...version, id: "saved", workflow_definition: pending }; });
    mutations.approve.mockImplementation(async () => { order.push("approve"); return {}; });
    mutations.publish.mockImplementation(async () => { order.push("publish"); return {}; });
    openAndSign();
    fireEvent.click(screen.getByRole("button", { name: "Approuver & Publier" }));
    await waitFor(() => expect(order).toEqual(["save", "approve", "publish"]));
    expect(mutations.save.mock.calls[0][0].workflow_definition.technical_facts[0].citation_status).toBe("manual_verified");
    expect(mutations.approve).toHaveBeenCalledWith(expect.objectContaining({ versionId: "saved", payload: expect.objectContaining({
      version_id: "saved", signature: { name: "hse_reviewer@smartloto.io", accepted: true },
    }) }));
    expect(mutations.publish).toHaveBeenCalledWith("saved");
  });
  it("keeps pending changes and stops approval when saving fails", async () => {
    useReviewStore.getState().setDraft({ ...version.workflow_definition, title: "Pending" });
    mutations.save.mockRejectedValue(new Error("Save failed"));
    openAndSign();
    fireEvent.click(screen.getByRole("button", { name: "Approuver & Publier" }));
    await screen.findByText("Save failed");
    expect(mutations.approve).not.toHaveBeenCalled();
    expect(mutations.publish).not.toHaveBeenCalled();
    expect(useReviewStore.getState().isDirty()).toBe(true);
  });
});
