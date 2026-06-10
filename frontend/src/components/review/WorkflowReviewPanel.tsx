/**
 * Workflow review.
 *
 * Walks phases -> stages -> steps and lets the reviewer edit step order,
 * description (instruction), expected state, safety notes, warnings, rollback
 * instructions, and the validation method. Reordering re-numbers `sequence`
 * within the stage.
 */

import { useReviewStore } from "@/store/reviewStore";
import type { WorkflowDefinition } from "@/types/workflow";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { SelectField, TagListEditor, TextField } from "./fields";

const PHASE_BADGE: Record<string, string> = {
  lockout: "bg-amber-100 text-amber-800",
  tagout: "bg-amber-100 text-amber-800",
  verification: "bg-blue-100 text-blue-800",
  maintenance: "bg-violet-100 text-violet-800",
  restoration: "bg-green-100 text-green-800",
};

const VALIDATION_METHODS = [
  "vision_detection",
  "inverse_vision_absence",
  "manual_confirmation",
  "sensor_threshold",
].map((v) => ({ value: v, label: v.replace(/_/g, " ") }));

function findOriginalStep(
  original: WorkflowDefinition | null,
  stepId: string,
) {
  if (!original) return undefined;
  for (const ph of original.phases ?? [])
    for (const st of ph.stages ?? [])
      for (const s of st.steps ?? []) if (s.step_id === stepId) return s;
  return undefined;
}

export function WorkflowReviewPanel({ readOnly }: { readOnly: boolean }) {
  const draft = useReviewStore((s) => s.draft);
  const original = useReviewStore((s) => s.original);
  const patchStep = useReviewStore((s) => s.patchStep);
  const moveStep = useReviewStore((s) => s.moveStep);

  if (!draft) return null;
  if ((draft.phases?.length ?? 0) === 0) {
    return (
      <EmptyState
        title="No workflow phases"
        description="This draft contains no phases. It cannot be approved until it has at least a lockout and restoration phase."
      />
    );
  }

  return (
    <div className="space-y-6">
      {draft.phases.map((phase) => (
        <div key={phase.phase_id}>
          <div className="mb-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${
                PHASE_BADGE[String(phase.phase_type)] ?? "bg-steel-100 text-steel-700"
              }`}
            >
              {String(phase.phase_type)}
            </span>
            <h3 className="text-sm font-semibold text-steel-800">
              {phase.title}
            </h3>
          </div>

          <div className="space-y-4 border-l-2 border-steel-100 pl-4">
            {phase.stages.map((stage) => (
              <div key={stage.stage_id}>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel-500">
                  {stage.title}
                </h4>
                <div className="space-y-3">
                  {stage.steps.map((step, idx) => {
                    const o = findOriginalStep(original, step.step_id);
                    return (
                      <div key={step.step_id} className="surface p-3">
                        <div className="mb-2 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-steel-700 text-xs font-semibold text-white">
                              {step.sequence}
                            </span>
                            <code className="text-xs text-steel-400">
                              {step.step_id}
                            </code>
                          </div>
                          {!readOnly && (
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={idx === 0}
                                onClick={() =>
                                  moveStep(
                                    phase.phase_id,
                                    stage.stage_id,
                                    step.step_id,
                                    "up",
                                  )
                                }
                                aria-label="Move step up"
                              >
                                ↑
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={idx === stage.steps.length - 1}
                                onClick={() =>
                                  moveStep(
                                    phase.phase_id,
                                    stage.stage_id,
                                    step.step_id,
                                    "down",
                                  )
                                }
                                aria-label="Move step down"
                              >
                                ↓
                              </Button>
                            </div>
                          )}
                        </div>

                        <div className="space-y-3">
                          <TextField
                            label="Instruction"
                            value={step.instruction}
                            original={o?.instruction}
                            readOnly={readOnly}
                            multiline
                            onCommit={(instruction) =>
                              patchStep(
                                phase.phase_id,
                                stage.stage_id,
                                step.step_id,
                                { instruction },
                              )
                            }
                          />

                          <div className="grid gap-3 sm:grid-cols-2">
                            <SelectField
                              label="Validation method"
                              value={step.validation?.method ?? "manual_confirmation"}
                              original={o?.validation?.method}
                              options={VALIDATION_METHODS}
                              readOnly={readOnly}
                              onCommit={(method) =>
                                patchStep(
                                  phase.phase_id,
                                  stage.stage_id,
                                  step.step_id,
                                  {
                                    validation: {
                                      ...(step.validation ?? {}),
                                      method,
                                    },
                                  },
                                )
                              }
                            />
                            <TextField
                              label="Expected state"
                              value={step.validation?.expected_state ?? ""}
                              original={o?.validation?.expected_state ?? ""}
                              readOnly={readOnly}
                              onCommit={(expected_state) =>
                                patchStep(
                                  phase.phase_id,
                                  stage.stage_id,
                                  step.step_id,
                                  {
                                    validation: {
                                      ...(step.validation ?? { method: "manual_confirmation" }),
                                      expected_state,
                                    },
                                  },
                                )
                              }
                            />
                          </div>

                          <TextField
                            label="Safety note"
                            value={step.safety_note ?? ""}
                            original={o?.safety_note ?? ""}
                            readOnly={readOnly}
                            onCommit={(safety_note) =>
                              patchStep(
                                phase.phase_id,
                                stage.stage_id,
                                step.step_id,
                                { safety_note },
                              )
                            }
                          />

                          <TextField
                            label="Rollback / abort instruction"
                            value={step.rollback_instruction ?? ""}
                            original={o?.rollback_instruction ?? ""}
                            readOnly={readOnly}
                            multiline
                            hint="What to do if this step cannot be safely completed."
                            onCommit={(rollback_instruction) =>
                              patchStep(
                                phase.phase_id,
                                stage.stage_id,
                                step.step_id,
                                { rollback_instruction },
                              )
                            }
                          />

                          <TagListEditor
                            label="Warnings"
                            values={step.warnings ?? []}
                            original={o?.warnings ?? []}
                            readOnly={readOnly}
                            placeholder="e.g. residual stored energy possible"
                            onCommit={(warnings) =>
                              patchStep(
                                phase.phase_id,
                                stage.stage_id,
                                step.step_id,
                                { warnings },
                              )
                            }
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
