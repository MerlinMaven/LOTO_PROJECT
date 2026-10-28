// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { moveStepToPhase, phaseLabel } from "../workflow";
import { useReviewStore } from "@/store/reviewStore";
import { WorkflowReviewPanel } from "@/components/review/WorkflowReviewPanel";
import type { WorkflowDefinition } from "@/types/workflow";

const workflow = (): WorkflowDefinition => ({ schema_version: "2.0", phases: [{ phase_id: "p", phase_type: "consignation",
  sequence: 1, title: "Consignation", stages: [{ stage_id: "s", title: "Actions", sequence: 1, steps: [
    { step_id: "arbitrary-filter", sequence: 1, instruction: "Remplacer le filtre", component_refs: ["filter"],
      verification: { method: "visual_observation", criteria: ["Repère du filtre lisible"] } }
  ] }] }] });

describe("phase editing and human confirmation", () => {
  it("preserves separate fields through edit, save acceptance and reload", () => {
    const original = workflow(); const changed = moveStepToPhase(original, "arbitrary-filter", "maintenance");
    expect(original.phases?.[0].phase_type).toBe("consignation");
    const serialized = JSON.parse(JSON.stringify(changed));
    useReviewStore.getState().setDraft(serialized);
    const read = useReviewStore.getState().draft!.phases![0].stages[0].steps[0];
    expect(read.execution_phase).toBe("maintenance"); expect(read.verification?.method).toBe("human_confirmation");
    expect(read.guidance?.observable_cues).toEqual(["Repère du filtre lisible"]);
    expect(phaseLabel("RESTORATION")).toBe("Déconsignation / remise en service");
  });
  it("renders French phases and a normal human method without requiring camera criteria", () => {
    useReviewStore.getState().setDraft(moveStepToPhase(workflow(), "arbitrary-filter", "maintenance"));
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><WorkflowReviewPanel readOnly={false} /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByText(/aucune photo, IA ou dérogation requise/)).toBeTruthy();
    expect(screen.getByText(/Critères de réalisation/)).toBeTruthy();
    expect(screen.getByText("1. Maintenance")).toBeTruthy(); cleanup();
  });
});
