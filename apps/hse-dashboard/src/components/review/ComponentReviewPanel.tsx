/**
 * Component catalog review.
 *
 * Edits the identity + classification of each detected component:
 * label, type, safety classification (detection difficulty), candidate
 * detection prompts, suggested confidence threshold, and reviewer notes.
 *
 * State prompts and per-step validation strategy are edited in the
 * VisionPromptPanel to keep concerns separated.
 */

import { useReviewStore } from "@/store/reviewStore";
import { getComponent, listComponents } from "@/lib/workflow";
import type { WorkflowDefinition } from "@/types/workflow";
import { EmptyState } from "@/components/ui/EmptyState";
import { NumberField, SelectField, TagListEditor, TextField } from "./fields";

const COMPONENT_TYPES = [
  "energy_source",
  "isolation_switch",
  "lockout_point",
  "safety_guard",
  "access_panel",
  "maintenance_target",
  "safety_device",
  "storage_unit",
  "indicator",
  "sensor",
].map((v) => ({ value: v, label: v.replace(/_/g, " ") }));

const DIFFICULTY = ["easy", "medium", "hard"].map((v) => ({ value: v, label: v }));

export function ComponentReviewPanel({ readOnly }: { readOnly: boolean }) {
  const draft = useReviewStore((s) => s.draft);
  const original = useReviewStore((s) => s.original);
  const patchComponent = useReviewStore((s) => s.patchComponent);

  if (!draft) return null;
  const components = listComponents(draft);

  if (components.length === 0) {
    return (
      <EmptyState
        title="No component catalog"
        description="This draft has no embedded component metadata to review."
      />
    );
  }

  const orig = (id: string) => getComponent(original as WorkflowDefinition, id);

  return (
    <div className="space-y-4">
      {components.map((c) => {
        const o = orig(c.component_id);
        return (
          <div key={c.component_id} className="surface p-4">
            <div className="mb-3 flex items-center justify-between">
              <code className="rounded bg-steel-100 px-2 py-0.5 text-xs text-steel-600">
                {c.component_id}
              </code>
              <span className="text-xs text-steel-400">
                difficulty: {c.detection_difficulty}
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label="Component name"
                value={c.label}
                original={o?.label}
                readOnly={readOnly}
                onCommit={(label) => patchComponent(c.component_id, { label })}
              />
              <SelectField
                label="Component type"
                value={c.component_type}
                original={o?.component_type}
                options={COMPONENT_TYPES}
                readOnly={readOnly}
                onCommit={(component_type) =>
                  patchComponent(c.component_id, { component_type })
                }
              />
              <SelectField
                label="Safety classification (detection difficulty)"
                value={c.detection_difficulty}
                original={o?.detection_difficulty}
                options={DIFFICULTY}
                readOnly={readOnly}
                onCommit={(detection_difficulty) =>
                  patchComponent(c.component_id, { detection_difficulty })
                }
              />
              <NumberField
                label="Suggested confidence threshold"
                value={c.confidence_threshold_suggestion}
                original={o?.confidence_threshold_suggestion}
                readOnly={readOnly}
                onCommit={(confidence_threshold_suggestion) =>
                  patchComponent(c.component_id, {
                    confidence_threshold_suggestion,
                  })
                }
              />
            </div>

            <div className="mt-3">
              <TagListEditor
                label="Candidate detection prompts"
                values={c.candidate_detection_prompts}
                original={o?.candidate_detection_prompts}
                readOnly={readOnly}
                placeholder="e.g. red battery holder on front panel"
                onCommit={(candidate_detection_prompts) =>
                  patchComponent(c.component_id, { candidate_detection_prompts })
                }
              />
            </div>

            <div className="mt-3">
              <TextField
                label="Reviewer notes"
                value={c.notes_for_reviewer}
                original={o?.notes_for_reviewer}
                readOnly={readOnly}
                multiline
                onCommit={(notes_for_reviewer) =>
                  patchComponent(c.component_id, { notes_for_reviewer })
                }
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
