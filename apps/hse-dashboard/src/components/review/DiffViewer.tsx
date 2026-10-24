import { useMemo } from "react";
import { clsx } from "clsx";
import { diffWorkflows, type FieldChange } from "@/lib/diff";
import { useReviewStore } from "@/store/reviewStore";
import { EmptyState } from "@/components/ui/EmptyState";

const KIND_STYLES: Record<string, string> = {
  added: "border-l-4 border-green-400 bg-green-50",
  removed: "border-l-4 border-red-400 bg-red-50",
  modified: "border-l-4 border-amber-400 bg-amber-50",
};

const KIND_CHIP: Record<string, string> = {
  added: "bg-green-100 text-green-700",
  removed: "bg-red-100 text-red-700",
  modified: "bg-amber-100 text-amber-700",
};

const KIND_LABEL: Record<string, string> = {
  added: "Ajouté",
  removed: "Supprimé",
  modified: "Modifié",
};

export function DiffViewer() {
  const original = useReviewStore((s) => s.original);
  const initialDraft = useReviewStore((s) => s.initialDraft);
  const draft = useReviewStore((s) => s.draft);

  const baseline = initialDraft || original;

  const changes = useMemo(() => {
    if (!baseline || !draft) return [];
    return diffWorkflows(baseline, draft);
  }, [baseline, draft]);

  if (!baseline || !draft) return null;

  if (changes.length === 0) {
    return (
      <EmptyState
        title="Aucune modification"
        description="Le brouillon de travail correspond à l'original généré. Modifiez des composants ou des étapes pour voir les écarts ici."
      />
    );
  }

  const grouped = new Map<string, FieldChange[]>();
  for (const c of changes) {
    const grp = grouped.get(c.scope) ?? [];
    grp.push(c);
    grouped.set(c.scope, grp);
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-steel-500">
        {changes.length} modification{changes.length > 1 ? "s" : ""} par rapport à l'original généré.
      </p>

      {Array.from(grouped.entries()).map(([scope, items]) => (
        <div key={scope} className="surface overflow-hidden">
          <div className="border-b border-steel-100 bg-steel-50 px-4 py-2">
            <span className="text-xs font-semibold text-steel-700">{scope}</span>
          </div>
          <div className="divide-y divide-steel-50">
            {items.map((change, i) => (
              <div
                key={i}
                className={clsx("px-4 py-3 text-xs", KIND_STYLES[change.kind])}
              >
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="font-semibold text-steel-700">
                    {change.field}
                  </span>
                  <span
                    className={clsx(
                      "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase",
                      KIND_CHIP[change.kind],
                    )}
                  >
                    {KIND_LABEL[change.kind]}
                  </span>
                </div>
                {change.kind !== "added" && change.before && (
                  <div className="mb-1">
                    <span className="mr-1 text-[10px] font-semibold uppercase text-red-500">
                      avant
                    </span>
                    <span className="text-steel-500 line-through">
                      {change.before}
                    </span>
                  </div>
                )}
                {change.kind !== "removed" && change.after && (
                  <div>
                    <span className="mr-1 text-[10px] font-semibold uppercase text-green-600">
                      après
                    </span>
                    <span className="text-steel-800">{change.after}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
