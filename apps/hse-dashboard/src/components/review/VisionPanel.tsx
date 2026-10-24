import { useState } from "react";
import { useReviewStore } from "@/store/reviewStore";
import type { WorkflowComponent } from "@/types/workflow";
import {
  ShieldAlert,
  AlertTriangle,
  HelpCircle,
  Plus,
  Trash2,
  CheckCircle2,
  Info,
  Camera,
  X,
} from "lucide-react";

interface VisionPanelProps {
  readOnly?: boolean;
}

const FEATURE_TYPE_LABELS: Record<string, { label: string; color: string; badge: string }> = {
  symbol: { label: "Symbole", color: "text-purple-700 bg-purple-50 border-purple-200", badge: "⊗ Symbole" },
  pictogram: { label: "Pictogramme", color: "text-amber-700 bg-amber-50 border-amber-200", badge: "🛡️ Pictogramme" },
  marking: { label: "Marquage", color: "text-blue-700 bg-blue-50 border-blue-200", badge: "🏷️ Marquage" },
  local_geometry: { label: "Géométrie locale", color: "text-emerald-700 bg-emerald-50 border-emerald-200", badge: "📐 Géométrie" },
  fixed_text: { label: "Texte fixe", color: "text-indigo-700 bg-indigo-50 border-indigo-200", badge: "🔤 Texte fixe" },
  color_pattern: { label: "Motif / Couleur", color: "text-rose-700 bg-rose-50 border-rose-200", badge: "🎨 Couleur" },
};

const RELATIVE_WORDS_REGEX = /\b(en haut|en bas|à gauche|a gauche|à droite|a droite|au milieu|visible sur l'image)\b/i;

export function VisionPanel({ readOnly = false }: VisionPanelProps) {
  const draft = useReviewStore((s) => s.draft);
  const setDraft = useReviewStore((s) => s.setDraft);

  const [activeClarification, setActiveClarification] = useState<{ id: string; name: string; note: string } | null>(null);
  const [editingComponentId, setEditingComponentId] = useState<string | null>(null);

  // New signature / state draft forms
  const [newSigType, setNewSigType] = useState<string>("marking");
  const [newSigDesc, setNewSigDesc] = useState<string>("");
  const [newStateName, setNewStateName] = useState<string>("");
  const [newStateRule, setNewStateRule] = useState<string>("");

  if (!draft) return null;

  const components: WorkflowComponent[] = Array.isArray(draft.components)
    ? (draft.components as WorkflowComponent[])
    : [];

  const updateComponents = (updater: (prev: WorkflowComponent[]) => WorkflowComponent[]) => {
    const updated = updater(components);
    setDraft({ ...draft, components: updated });
  };

  const handleUpdateUnityClass = (componentId: string, unityClassId: string) => {
    updateComponents((prev) =>
      prev.map((c) => (c.component_id === componentId ? { ...c, unity_class_id: unityClassId } : c))
    );
  };

  const handleAddSignature = (componentId: string) => {
    if (!newSigDesc.trim()) return;
    updateComponents((prev) =>
      prev.map((c) => {
        if (c.component_id !== componentId) return c;
        const current = c.invariant_features ?? [];
        return {
          ...c,
          invariant_features: [
            ...current,
            { feature_type: newSigType, description: newSigDesc.trim() },
          ],
        };
      })
    );
    setNewSigDesc("");
  };

  const handleRemoveSignature = (componentId: string, sigIndex: number) => {
    updateComponents((prev) =>
      prev.map((c) => {
        if (c.component_id !== componentId) return c;
        const current = [...(c.invariant_features ?? [])];
        current.splice(sigIndex, 1);
        return { ...c, invariant_features: current };
      })
    );
  };

  const handleAddState = (componentId: string) => {
    if (!newStateName.trim() || !newStateRule.trim()) return;
    updateComponents((prev) =>
      prev.map((c) => {
        if (c.component_id !== componentId) return c;
        const current = c.verifiable_states ?? [];
        return {
          ...c,
          verifiable_states: [
            ...current,
            {
              state_name: newStateName.trim().toUpperCase(),
              physical_rule: newStateRule.trim(),
              supported_by_unity: false,
              requires_human_confirmation: true,
              candidate_prompt: c.unity_class_id || "candidate",
            },
          ],
        };
      })
    );
    setNewStateName("");
    setNewStateRule("");
  };

  const handleRemoveState = (componentId: string, stateIndex: number) => {
    updateComponents((prev) =>
      prev.map((c) => {
        if (c.component_id !== componentId) return c;
        const current = [...(c.verifiable_states ?? [])];
        current.splice(stateIndex, 1);
        return { ...c, verifiable_states: current };
      })
    );
  };

  const handleToggleUnitySupport = (componentId: string, stateIndex: number) => {
    updateComponents((prev) =>
      prev.map((c) => {
        if (c.component_id !== componentId) return c;
        const current = [...(c.verifiable_states ?? [])];
        const target = current[stateIndex];
        if (target) {
          current[stateIndex] = { ...target, supported_by_unity: !target.supported_by_unity };
        }
        return { ...c, verifiable_states: current };
      })
    );
  };

  return (
    <div className="space-y-4">
      {/* 1. Alerte de Sécurité & Contrat Unity */}
      <div className="flex items-start gap-3 rounded-[20px] border border-amber-200/80 bg-amber-50/70 p-4 text-xs text-amber-900 shadow-[0_4px_20px_-4px_rgba(245,158,11,0.06)]">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        <div className="space-y-1">
          <div className="font-semibold text-amber-950 flex items-center gap-2">
            <span>Principe de sécurité LOTO & Vision AR (Unity Quest)</span>
            <span className="rounded bg-amber-200/80 px-1.5 py-0.2 font-mono text-[10px] text-amber-900">
              Contrat strict
            </span>
          </div>
          <p className="leading-relaxed">
            Les signatures physiques (marquage, pictogramme, symbole ⊗, carré blanc) permettent à Unity d'identifier l'organe candidat.
            <strong> Un repère physique ne garantit pas sa détection sous tous les angles.</strong> L'absence de détection reste indéterminée et ne valide <em>jamais</em> automatiquement une étape : la confirmation opérateur demeure requise.
          </p>
        </div>
      </div>

      {/* 2. Matrice Éditable des Composants */}
      <div className="rounded-[20px] border border-slate-900/10 bg-white shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all overflow-hidden">
        <div className="border-b border-slate-900/10 bg-slate-900/[0.025] px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-slate-700" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Matrice Vision AR : Composant | Signature physique | Règle d’état | Classe Unity
            </h3>
          </div>
          <span className="text-[11px] font-medium text-slate-500">
            {components.length} composant{components.length > 1 ? "s" : ""} référencé{components.length > 1 ? "s" : ""}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-900/10 bg-slate-900/[0.025] text-[11px] font-bold uppercase tracking-wider text-slate-600">
                <th className="py-3 px-4 w-[22%]">Composant & Repère</th>
                <th className="py-3 px-4 w-[32%]">Signature physique (invariante)</th>
                <th className="py-3 px-4 w-[30%]">Règle d’état (Transition vérifiable)</th>
                <th className="py-3 px-4 w-[16%]">Classe Unity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {components.map((comp, idx) => {
                const compId = comp.component_id;
                const internalId = comp.internal_id || `C${String(idx + 1).padStart(2, "0")}`;
                const name = comp.component_name || comp.label || comp.canonical_name || `Composant ${internalId}`;
                const unityClass = comp.unity_class_id || "";
                const signatures = comp.invariant_features ?? [];
                const states = comp.verifiable_states ?? [];

                // Récupération dynamique des clarifications liées à ce composant
                const allClarifs = (draft.clarifications_required ?? []) as Array<Record<string, unknown>>;
                const compIdUpper = String(compId || "").toUpperCase();
                const internalIdUpper = String(internalId || "").toUpperCase();
                const relatedClarifs = allClarifs.filter((q) => {
                  const qComps = (Array.isArray(q.related_component_ids) ? (q.related_component_ids as string[]) : []).map((c) =>
                    String(c).toUpperCase()
                  );
                  return qComps.includes(compIdUpper) || qComps.includes(internalIdUpper);
                });

                const unresolvedClarifs = relatedClarifs.filter((q) => q.status !== "resolved");
                const resolvedClarifs = relatedClarifs.filter((q) => q.status === "resolved");

                const hasUnresolvedClarification = (Boolean(comp.clarification_needed) || relatedClarifs.length > 0) && unresolvedClarifs.length > 0;
                const isClarificationResolved = relatedClarifs.length > 0 && unresolvedClarifs.length === 0;

                const isEditing = editingComponentId === compId;

                return (
                  <tr
                    key={compId}
                    className={`transition-colors hover:bg-slate-50/70 ${hasUnresolvedClarification ? "bg-amber-50/20" : isClarificationResolved ? "bg-emerald-50/15" : ""}`}
                  >
                    {/* Colonne 1 : Composant */}
                    <td className="py-3.5 px-4 align-top space-y-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="inline-flex items-center justify-center rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-bold text-white font-mono shadow-2xs">
                          {internalId}
                        </span>
                        <span className="font-semibold text-slate-900 leading-tight">
                          {name}
                        </span>
                      </div>

                      {Boolean(comp.source_tag) && (
                        <div className="text-[10px] text-slate-500 font-mono">
                          Tag doc : <span className="text-slate-700 font-semibold">{comp.source_tag}</span>
                        </div>
                      )}

                      {/* Clarification Alert Badge */}
                      {hasUnresolvedClarification ? (
                        <button
                          type="button"
                          onClick={() =>
                            setActiveClarification({
                              id: compId,
                              name,
                              note: comp.clarification_note || String(unresolvedClarifs[0]?.question || "Donnée physique ou tolérance restant à clarifier sur cet organe."),
                            })
                          }
                          className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-medium text-amber-900 hover:bg-amber-100 transition shadow-2xs cursor-pointer"
                          title="Cliquer pour afficher la clarification HSE"
                        >
                          <HelpCircle className="h-3 w-3 text-amber-700" />
                          <span>À clarifier</span>
                        </button>
                      ) : isClarificationResolved ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-medium text-emerald-800 shadow-2xs"
                          title={`Clarification validée : ${resolvedClarifs.map((q) => (q.resolution as Record<string, unknown> | undefined)?.answer).filter(Boolean).join(" · ")}`}
                        >
                          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                          <span>Clarifié</span>
                        </span>
                      ) : null}
                    </td>

                    {/* Colonne 2 : Signatures physiques */}
                    <td className="py-3.5 px-4 align-top space-y-2">
                      <div className="space-y-1.5">
                        {signatures.map((sig, sigIdx) => {
                          const meta = FEATURE_TYPE_LABELS[sig.feature_type] || {
                            label: sig.feature_type,
                            color: "text-slate-700 bg-slate-100 border-slate-200",
                            badge: sig.feature_type,
                          };
                          const hasRelativeWarning = RELATIVE_WORDS_REGEX.test(sig.description);

                          return (
                            <div
                              key={sigIdx}
                              className="group relative flex items-start justify-between gap-2 rounded-xl border border-slate-200/70 bg-slate-50/50 p-2.5 transition-all hover:bg-white hover:shadow-xs"
                            >
                              <div className="space-y-1 min-w-0">
                                <span className={`inline-block text-[10px] font-semibold uppercase px-2.5 py-0.5 rounded-full border shadow-2xs ${meta.color}`}>
                                  {meta.badge}
                                </span>
                                <div className="text-[11px] text-slate-800 leading-snug break-words">
                                  {sig.description}
                                </div>
                                {hasRelativeWarning && (
                                  <div className="flex items-center gap-1 text-[10px] text-amber-700 font-medium pt-0.5">
                                    <AlertTriangle className="h-2.5 w-2.5 shrink-0" />
                                    <span>Terme relatif détecté ; privilégier un repère matériel invariant.</span>
                                  </div>
                                )}
                              </div>

                              {!readOnly && (
                                <button
                                  type="button"
                                  onClick={() => handleRemoveSignature(compId, sigIdx)}
                                  className="text-slate-400 hover:text-rose-600 transition p-0.5"
                                  title="Supprimer la signature"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </button>
                              )}
                            </div>
                          );
                        })}

                        {signatures.length === 0 && (
                          <span className="text-[11px] italic text-slate-400">
                            Aucune signature physique renseignée
                          </span>
                        )}
                      </div>

                      {/* Formulaire ajout signature */}
                      {!readOnly && isEditing && (
                        <div className="mt-2 rounded border border-dashed border-blue-300 bg-blue-50/50 p-2 space-y-1.5">
                          <div className="flex gap-1.5">
                            <select
                              value={newSigType}
                              onChange={(e) => setNewSigType(e.target.value)}
                              className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700"
                            >
                              <option value="symbol">Symbole (ex: ⊗)</option>
                              <option value="pictogram">Pictogramme (ex: cadenas)</option>
                              <option value="marking">Marquage (ex: ON/OFF)</option>
                              <option value="local_geometry">Géométrie locale</option>
                              <option value="fixed_text">Texte fixe</option>
                              <option value="color_pattern">Couleur / motif</option>
                            </select>
                            <input
                              type="text"
                              placeholder="Description physique (ex: Carré blanc solidaire)..."
                              value={newSigDesc}
                              onChange={(e) => setNewSigDesc(e.target.value)}
                              className="flex-1 rounded border border-slate-300 bg-white px-2 py-1 text-[11px]"
                            />
                            <button
                              type="button"
                              onClick={() => handleAddSignature(compId)}
                              className="rounded bg-blue-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-blue-700"
                            >
                              +
                            </button>
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Colonne 3 : Règles d'état */}
                    <td className="py-3.5 px-4 align-top space-y-2">
                      <div className="space-y-1.5">
                        {states.map((st, stIdx) => {
                          const isSupported = Boolean(st.supported_by_unity);

                          return (
                            <div
                              key={stIdx}
                              className="flex items-start justify-between gap-2 rounded-xl border border-slate-200/70 bg-slate-50/50 p-2.5 shadow-2xs transition-all hover:bg-white hover:shadow-xs"
                            >
                              <div className="space-y-1 min-w-0">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="font-mono text-[10px] font-bold text-slate-800 bg-white border border-slate-200 px-1.5 py-0.5 rounded-md shadow-2xs">
                                    {st.state_name}
                                  </span>
                                  {isSupported ? (
                                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[9px] text-emerald-800 font-semibold shadow-2xs">
                                      <CheckCircle2 className="h-2.5 w-2.5 text-emerald-600" />
                                      Auto Unity
                                    </span>
                                  ) : (
                                    <span
                                      className="inline-flex items-center gap-1 rounded-full bg-white border border-slate-200 px-2 py-0.5 text-[9px] text-slate-600 shadow-2xs"
                                      title="L'absence de détection est indéterminée ; validation humaine obligatoire"
                                    >
                                      <Info className="h-2.5 w-2.5 text-slate-400" />
                                      Candidat seul (confirmation requise)
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-700 leading-snug break-words">
                                  {st.physical_rule}
                                </div>
                              </div>

                              {!readOnly && (
                                <div className="flex items-center gap-1 shrink-0">
                                  <button
                                    type="button"
                                    onClick={() => handleToggleUnitySupport(compId, stIdx)}
                                    className="text-[10px] text-slate-400 hover:text-blue-600 transition"
                                    title="Basculer support automatique Unity"
                                  >
                                    ⚙️
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveState(compId, stIdx)}
                                    className="text-slate-400 hover:text-rose-600 transition p-0.5"
                                    title="Supprimer la règle d'état"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })}

                        {states.length === 0 && (
                          <span className="text-[11px] italic text-slate-400">
                            Aucune règle d'état configurée
                          </span>
                        )}
                      </div>

                      {/* Formulaire ajout règle d'état */}
                      {!readOnly && isEditing && (
                        <div className="mt-2 rounded-xl border border-dashed border-emerald-300 bg-emerald-50/40 p-2.5 space-y-1.5">
                          <div className="flex gap-1.5">
                            <input
                              type="text"
                              placeholder="État (ex: CLOSED)"
                              value={newStateName}
                              onChange={(e) => setNewStateName(e.target.value)}
                              className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-mono uppercase focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                            />
                            <input
                              type="text"
                              placeholder="Condition physique (ex: Alignement carré blanc avec cercle noir plein)..."
                              value={newStateRule}
                              onChange={(e) => setNewStateRule(e.target.value)}
                              className="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                            />
                            <button
                              type="button"
                              onClick={() => handleAddState(compId)}
                              className="rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-700 shadow-xs"
                            >
                              +
                            </button>
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Colonne 4 : Classe Unity */}
                    <td className="py-3.5 px-4 align-top space-y-2">
                      <div className="space-y-1">
                        <input
                          type="text"
                          value={unityClass}
                          disabled={readOnly}
                          onChange={(e) => handleUpdateUnityClass(compId, e.target.value)}
                          className="w-full font-mono text-xs bg-slate-900 text-blue-400 px-2.5 py-1.5 rounded-lg border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 shadow-xs transition-all disabled:opacity-75"
                          title="Classe zero-shot envoyée au modèle Unity / YOLO"
                        />
                        <div className="text-[10px] font-medium text-slate-400">
                          ID détecteur YOLO / AR
                        </div>
                      </div>

                      {!readOnly && (
                        <button
                          type="button"
                          onClick={() => setEditingComponentId(isEditing ? null : compId)}
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800 transition"
                        >
                          {isEditing ? (
                            <>
                              <X className="h-3 w-3" /> Terminer édition
                            </>
                          ) : (
                            <>
                              <Plus className="h-3 w-3" /> Ajouter signature/règle
                            </>
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Popover / Modal de Clarification HSE au clic */}
      {activeClarification && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl border border-slate-200 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <div className="flex items-center gap-2 text-amber-800 font-bold text-sm">
                <HelpCircle className="h-4 w-4 text-amber-600" />
                <span>Clarification HSE : {activeClarification.name}</span>
              </div>
              <button
                type="button"
                onClick={() => setActiveClarification(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed bg-amber-50/70 p-3 rounded-lg border border-amber-200/80">
              {activeClarification.note}
            </p>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setActiveClarification(null)}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900"
              >
                Compris
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { VisionPanel as VisionPromptPanel };
