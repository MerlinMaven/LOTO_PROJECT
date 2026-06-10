/**
 * Vision prompt review — the critical safety surface.
 *
 * For each component the HSE reviewer inspects and may REPLACE:
 *   - suggested object labels (component label / type)
 *   - candidate YOLO-World detection prompts
 *   - per-state prompts (active / isolated / ...)
 *   - the suggested confidence threshold and detection difficulty
 *
 * Everything here is a SUGGESTION generated upstream — no inference has run.
 * Nothing is trusted until the reviewer approves it.
 */

import { useReviewStore } from "@/store/reviewStore";
import { getComponent, listComponents } from "@/lib/workflow";
import type { WorkflowDefinition } from "@/types/workflow";
import { EmptyState } from "@/components/ui/EmptyState";
import { NumberField, TagListEditor } from "./fields";

export function VisionPromptPanel({ readOnly }: { readOnly: boolean }) {
  const draft = useReviewStore((s) => s.draft);
  const original = useReviewStore((s) => s.original);
  const patchComponent = useReviewStore((s) => s.patchComponent);

  if (!draft) return null;
  const components = listComponents(draft);

  if (components.length === 0) {
    return (
      <EmptyState
        title="No vision prompts"
        description="This draft has no component vision metadata to review."
      />
    );
  }

  const orig = (id: string) => getComponent(original as WorkflowDefinition, id);

  const setStatePrompt = (
    componentId: string,
    state: string,
    prompts: string[],
    current: Record<string, string[]>,
  ) => {
    patchComponent(componentId, {
      state_prompts: { ...current, [state]: prompts },
    });
  };

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-2 text-xs text-blue-800">
        <strong>Critical review.</strong> These prompts are auto-suggested for
        zero-shot detection. No YOLO inference has run. Replace anything that
        does not precisely describe what the camera will see before approval.
      </div>

      {components.map((c) => {
        const o = orig(c.component_id);
        const states = Array.from(
          new Set([
            "active",
            "isolated",
            ...Object.keys(c.state_prompts ?? {}),
          ]),
        );
        return (
          <div key={c.component_id} className="surface p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-steel-800">
                  {c.label}
                </div>
                <code className="text-xs text-steel-400">{c.component_id}</code>
              </div>
              <span className="rounded bg-steel-100 px-2 py-0.5 text-xs text-steel-600">
                {c.component_type}
              </span>
            </div>

            <div className="mb-3">
              <TagListEditor
                label="Suggested object labels / detection prompts"
                values={c.candidate_detection_prompts}
                original={o?.candidate_detection_prompts}
                readOnly={readOnly}
                placeholder="e.g. white rocker switch on front panel"
                onCommit={(candidate_detection_prompts) =>
                  patchComponent(c.component_id, { candidate_detection_prompts })
                }
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {states.map((state) => (
                <TagListEditor
                  key={state}
                  label={`State prompts · ${state}`}
                  values={c.state_prompts?.[state] ?? []}
                  original={o?.state_prompts?.[state] ?? []}
                  readOnly={readOnly}
                  placeholder={`how "${state}" looks to the camera`}
                  onCommit={(prompts) =>
                    setStatePrompt(
                      c.component_id,
                      state,
                      prompts,
                      c.state_prompts ?? {},
                    )
                  }
                />
              ))}
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
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
              <div className="flex items-end">
                <p className="text-xs text-steel-500">
                  {c.notes_for_reviewer || "No reviewer notes."}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
