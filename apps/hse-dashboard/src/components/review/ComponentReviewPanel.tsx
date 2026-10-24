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

import { useState } from "react";
import { clsx } from "clsx";
import { Check, FileText, AlertCircle, ChevronDown, ChevronUp, ChevronRight } from "lucide-react";
import { useReviewStore } from "@/store/reviewStore";
import { getComponent, listComponents } from "@/lib/workflow";
import type { WorkflowComponent, WorkflowDefinition } from "@/types/workflow";
import { EmptyState } from "@/components/ui/EmptyState";
import { NumberField, SelectField, TagListEditor, TextField } from "./fields";

const COMPONENT_TYPES = [
  { value: "energy_source", label: "Source d'énergie" },
  { value: "isolation_switch", label: "Organe de coupure" },
  { value: "lockout_point", label: "Point de condamnation" },
  { value: "safety_guard", label: "Protection mécanique / Carter" },
  { value: "access_panel", label: "Trappe d'accès" },
  { value: "maintenance_target", label: "Cible de maintenance" },
  { value: "safety_device", label: "Dispositif de sécurité" },
  { value: "storage_unit", label: "Zone de stockage" },
  { value: "indicator", label: "Indicateur / Voyant" },
  { value: "sensor", label: "Capteur" },
];

const ROLE_LOTO_MAP: Record<string, string> = {
  energy_source: "SOURCE D'ÉNERGIE",
  source_energie: "SOURCE D'ÉNERGIE",
  isolation_switch: "ORGANE DE COUPURE",
  interrupteur: "ORGANE DE COUPURE",
  lockout_point: "POINT DE CONDAMNATION",
  safety_guard: "PROTECTION MÉCANIQUE / CARTER",
  protection_mecanique: "PROTECTION MÉCANIQUE / CARTER",
  access_panel: "TRAPPE D'ACCÈS",
  maintenance_target: "CIBLE D'INTERVENTION",
  cible_maintenance: "CIBLE D'INTERVENTION",
  safety_device: "DISPOSITIF DE SÉCURITÉ",
  storage_unit: "ZONE DE STOCKAGE",
  boite_stockage: "ZONE DE STOCKAGE",
  support_composant: "SUPPORT ÉQUIPEMENT",
  indicator: "INDICATEUR / VOYANT",
  repere_visuel: "REPÈRE VISUEL",
  sensor: "CAPTEUR",
};

const DIFFICULTY = [
  { value: "easy", label: "Facile" },
  { value: "medium", label: "Moyen" },
  { value: "hard", label: "Difficile" },
];
const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "Facile",
  medium: "Moyen",
  hard: "Difficile",
};

export function ComponentReviewPanel({ readOnly }: { readOnly: boolean }) {
  const draft = useReviewStore((s) => s.draft);
  const original = useReviewStore((s) => s.original);
  const patchComponent = useReviewStore((s) => s.patchComponent);
  const setDraft = useReviewStore((s) => s.setDraft);

  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [factsOpen, setFactsOpen] = useState(false);
  const [factFilter, setFactFilter] = useState<"all" | "verified" | "absence" | "unmatched">("all");

  if (!draft) return null;
  const components = listComponents(draft);
  const canonical = Array.isArray(draft.components) ? (draft.components as WorkflowComponent[]) : [];
  const canonicalOriginal = Array.isArray(original?.components) ? (original.components as WorkflowComponent[]) : [];
  const facts = Array.isArray(draft.technical_facts) ? (draft.technical_facts as Record<string, unknown>[]) : [];
  const originalFacts = Array.isArray(original?.technical_facts) ? (original.technical_facts as Record<string, unknown>[]) : [];

  const updateCanonical = (id: string, patch: Partial<WorkflowComponent>) => {
    setDraft({
      ...draft,
      components: canonical.map((component) => String(component.component_id) === id ? { ...component, ...patch } : component),
    });
  };
  const updateFact = (id: string, patch: Record<string, unknown>) => {
    setDraft({ ...draft, technical_facts: facts.map((fact) => String(fact.fact_id) === id ? { ...fact, ...patch } : fact) });
  };

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const allExpanded = canonical.length > 0 && canonical.every((c) => expandedIds[String(c.component_id)]);
  const toggleAll = () => {
    if (allExpanded) {
      setExpandedIds({});
    } else {
      const all: Record<string, boolean> = {};
      canonical.forEach((c) => { all[String(c.component_id)] = true; });
      setExpandedIds(all);
    }
  };

  if (canonical.length > 0 || facts.length > 0) {
    return (
      <div className="space-y-6">
        {canonical.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2 border-b border-slate-200/80 pb-2">
              <h3 className="text-sm font-semibold text-slate-800">
                Catalogue des composants ({canonical.length})
              </h3>
              <button
                type="button"
                onClick={toggleAll}
                className="text-xs font-semibold text-blue-700 hover:text-blue-900 transition"
              >
                {allExpanded ? "Tout replier" : "Tout déplier"}
              </button>
            </div>

            <div className="space-y-2.5">
              {canonical.map((component, index) => {
                const id = String(component.component_id || index);
                const before = canonicalOriginal.find((item) => String(item.component_id) === id);
                const systemId = `SL-CMP-${String(index + 1).padStart(2, "0")}`;
                const rawType = String(component.component_type || "").toLowerCase();
                const roleLabel =
                  ROLE_LOTO_MAP[rawType] ??
                  (component.component_type
                    ? String(component.component_type).toUpperCase().replace(/_/g, " ")
                    : "ÉQUIPEMENT");
                const docRef = String(component.internal_id || `C${String(index + 1).padStart(2, "0")}`);
                const sourceTagDisplay =
                  component.source_tag && !/^C0[1-7]$/.test(String(component.source_tag))
                    ? String(component.source_tag)
                    : rawType === "isolation_switch" || rawType === "interrupteur"
                      ? "Marquage ON/OFF (Doc: C01)"
                      : rawType === "energy_source" || rawType === "source_energie"
                        ? "Non marqué sur équipement (Doc: C02)"
                        : rawType === "storage_unit" || rawType === "boite_stockage"
                          ? "Marquage Safe Box & Cadenas (Doc: C04)"
                          : rawType === "safety_guard" || rawType === "protection_mecanique"
                            ? "Carré blanc solidaire (Doc: C05)"
                            : rawType === "maintenance_target" || rawType === "cible_maintenance"
                              ? "Symbole cercle croix ⊗ (Doc: C06)"
                              : `Non marqué directement (Réf. doc : ${docRef})`;

                const isExpanded = !!expandedIds[id];
                const relCount = Array.isArray(component.relations) ? component.relations.length : 0;

                return (
                  <div key={id} className="rounded-[20px] border border-slate-900/10 bg-white p-5 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all">
                    {/* Header compact (1 ligne) */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-lg bg-blue-600 px-2.5 py-0.5 text-xs font-mono font-bold text-white shadow-xs" title="Identifiant Système Universel SmartLOTO">
                          {systemId}
                        </span>
                        <span className="font-semibold text-sm text-slate-900">
                          {String(component.label || component.canonical_name || "Composant")}
                        </span>
                        <span className="rounded-full bg-indigo-50 border border-indigo-200/80 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 shadow-2xs" title="Rôle LOTO normalisé">
                          {roleLabel}
                        </span>
                        <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-xs font-mono text-slate-600 shadow-2xs" title="Repère documentaire source">
                          Réf. doc : {docRef}
                        </span>
                        {relCount > 0 && (
                          <span className="rounded-full bg-slate-50 border border-slate-200/70 px-2.5 py-0.5 text-[11px] text-slate-500 shadow-2xs">
                            {relCount} relation{relCount > 1 ? "s" : ""}
                          </span>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleExpand(id)}
                        className="inline-flex items-center gap-1 rounded-xl bg-slate-50 border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 transition cursor-pointer"
                      >
                        {isExpanded ? (
                          <><span>Replier</span><ChevronUp className="h-3.5 w-3.5" /></>
                        ) : (
                          <><span>Modifier ▾</span></>
                        )}
                      </button>
                    </div>

                    {/* Formulaire complet déplié (Grille 3 colonnes) */}
                    {isExpanded && (
                      <div className="mt-3.5 pt-3.5 border-t border-slate-100 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <TextField
                            label="Nom fonctionnel du composant"
                            value={String(component.label || component.canonical_name || "")}
                            original={String(before?.label || before?.canonical_name || "")}
                            readOnly={readOnly}
                            onCommit={(label) => updateCanonical(id, { label, canonical_name: label })}
                          />
                          <TextField
                            label="Repère industriel (source tag)"
                            value={String(component.source_tag || sourceTagDisplay)}
                            original={String(before?.source_tag || "")}
                            readOnly={readOnly}
                            onCommit={(source_tag) => updateCanonical(id, { source_tag })}
                          />
                          <TextField
                            label="Type"
                            value={String(component.component_type || "")}
                            original={String(before?.component_type || "")}
                            readOnly={readOnly}
                            onCommit={(component_type) => updateCanonical(id, { component_type })}
                          />
                        </div>
                        <TextField
                          label="Description documentaire"
                          value={String(component.description || "")}
                          original={String(before?.description || "")}
                          readOnly={readOnly}
                          multiline
                          rows={3}
                          onCommit={(description) => updateCanonical(id, { description })}
                        />
                        <TagListEditor
                          label="Relations documentées"
                          values={Array.isArray(component.relations) ? component.relations.map(String) : []}
                          original={Array.isArray(before?.relations) ? before.relations.map(String) : []}
                          readOnly={readOnly}
                          placeholder="Relation explicitement documentée"
                          onCommit={(relations) => updateCanonical(id, { relations })}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {facts.length > 0 && (() => {
          const verifiedCount = facts.filter(
            (f) => f.citation_status === "verified" || f.citation_status === "manual_verified"
          ).length;
          const absenceCount = facts.filter(
            (f) => f.citation_status === "inferred_absence"
          ).length;
          const unmatchedCount = facts.filter(
            (f) => f.citation_status === "unmatched"
          ).length;

          const filteredFacts = facts.filter((f) => {
            if (factFilter === "verified") return f.citation_status === "verified" || f.citation_status === "manual_verified";
            if (factFilter === "absence") return f.citation_status === "inferred_absence";
            if (factFilter === "unmatched") return f.citation_status === "unmatched";
            return true;
          });

          return (
            <section className="rounded-[20px] border border-slate-200/60 bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.04)] space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setFactsOpen((prev) => !prev)}
                    className="flex items-center gap-2 text-sm font-bold text-slate-800 hover:text-blue-700 transition cursor-pointer"
                  >
                    {factsOpen ? <ChevronDown className="h-4 w-4 text-slate-600" /> : <ChevronRight className="h-4 w-4 text-slate-600" />}
                    <span>Faits et citations du document ({facts.length})</span>
                  </button>
                </div>

                {/* Filtres interactifs par pilules */}
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <button
                    type="button"
                    onClick={() => { setFactFilter("all"); setFactsOpen(true); }}
                    className={clsx(
                      "px-2.5 py-1 rounded-full font-medium transition cursor-pointer",
                      factFilter === "all"
                        ? "bg-slate-800 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                    )}
                  >
                    Tout ({facts.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => { setFactFilter("verified"); setFactsOpen(true); }}
                    className={clsx(
                      "inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-medium transition cursor-pointer",
                      factFilter === "verified"
                        ? "bg-emerald-700 text-white shadow-xs"
                        : "bg-emerald-50 border border-emerald-200 text-emerald-800 hover:bg-emerald-100"
                    )}
                  >
                    <Check className="h-3 w-3" />
                    {verifiedCount} vérifiée{verifiedCount > 1 ? "s" : ""}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setFactFilter("absence"); setFactsOpen(true); }}
                    className={clsx(
                      "inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-medium transition cursor-pointer",
                      factFilter === "absence"
                        ? "bg-slate-700 text-white shadow-xs"
                        : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-100"
                    )}
                  >
                    <FileText className="h-3 w-3 text-slate-500" />
                    {absenceCount} constat{absenceCount > 1 ? "s" : ""}
                  </button>
                  {unmatchedCount > 0 && (
                    <button
                      type="button"
                      onClick={() => { setFactFilter("unmatched"); setFactsOpen(true); }}
                      className={clsx(
                        "inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-semibold transition cursor-pointer",
                        factFilter === "unmatched"
                          ? "bg-amber-600 text-white shadow-xs"
                          : "bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100"
                      )}
                    >
                      <AlertCircle className="h-3 w-3 text-amber-600" />
                      {unmatchedCount} à vérifier
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setFactsOpen((prev) => !prev)}
                    className="ml-2 text-xs font-semibold text-blue-700 hover:underline"
                  >
                    {factsOpen ? "Masquer" : "Afficher les citations ▾"}
                  </button>
                </div>
              </div>

              {factsOpen && (
                <div className="space-y-3 pt-2">
                  {filteredFacts.map((fact, index) => {
                const id = String(fact.fact_id || index);
                const before = originalFacts.find((item) => String(item.fact_id) === id);
                const citationReview = (fact.citation_review && typeof fact.citation_review === "object"
                  ? fact.citation_review
                  : {}) as Record<string, unknown>;

                const isManuallyVerified = fact.citation_status === "manual_verified";
                const isLlmVerified = fact.citation_status === "verified";
                const isAbsence = fact.citation_status === "inferred_absence";
                const isVerified = isManuallyVerified || isLlmVerified;

                return (
                  <div
                    key={id}
                    className={clsx(
                      "rounded-lg border transition-all duration-200 shadow-sm",
                      isVerified
                        ? "border-emerald-200/80 bg-emerald-50/20 p-3 space-y-2"
                        : isAbsence
                          ? "border-slate-200 bg-slate-50/50 p-3 space-y-2"
                          : "border-amber-300 bg-amber-50/30 p-4 space-y-3"
                    )}
                  >
                    {/* Top Bar: ID + Status Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <code className="rounded bg-slate-100 px-2 py-0.5 text-xs font-mono font-medium text-slate-700">
                          {id}
                        </code>
                        {(isVerified || isAbsence) && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span
                              className={clsx(
                                "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold border",
                                isAbsence
                                  ? "bg-slate-100 text-slate-700 border-slate-300"
                                  : "bg-blue-50 text-blue-700 border-blue-200"
                              )}
                            >
                              {isAbsence
                                ? "Constat d'absence"
                                : String(fact.qualification || "").toLowerCase() === "documented"
                                  ? "Documenté"
                                  : String(fact.qualification || "").toLowerCase() === "inferred"
                                    ? "Déduit"
                                    : String(fact.qualification || "").toLowerCase() === "unknown"
                                      ? "Constat d'absence"
                                      : "Documenté"}
                            </span>
                            <span className="text-xs font-semibold text-slate-900">{String(fact.value || "")}</span>
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {isManuallyVerified ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 shadow-sm">
                            <Check className="h-3 w-3 text-emerald-600" />
                            Vérifiée manuellement (HSE)
                          </span>
                        ) : isLlmVerified ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 shadow-sm">
                            <Check className="h-3 w-3 text-emerald-600" />
                            Citation vérifiée (IA)
                          </span>
                        ) : isAbsence ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-300 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                            <FileText className="h-3 w-3 text-slate-500" />
                            Constat d'absence documentaire
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 border border-amber-300 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                            <AlertCircle className="h-3 w-3 text-amber-600" />
                            Citation : à vérifier dans le PDF
                          </span>
                        )}

                        {!readOnly && (isVerified || isAbsence) && (
                          <button
                            type="button"
                            onClick={() =>
                              updateFact(id, {
                                citation_status: "unmatched",
                                citation_review: {},
                              })
                            }
                            className="text-[11px] text-slate-400 hover:text-slate-700 transition-colors underline"
                            title="Modifier cette affirmation ou sa citation"
                          >
                            Modifier
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Content display based on status */}
                    {isVerified ? (
                      fact.source_quote ? (
                        <p className="text-xs text-slate-600 italic bg-white/80 rounded px-2.5 py-1.5 border border-slate-200/60 line-clamp-2">
                          « {String(fact.source_quote)} »
                        </p>
                      ) : null
                    ) : isAbsence ? (
                      <p className="text-[11px] text-slate-500 italic bg-white/60 rounded px-2.5 py-1 border border-slate-200/50">
                        Information non mentionnée dans le dossier technique source (absence constatée).
                      </p>
                    ) : (
                      /* Detailed form when unmatched / unverified */
                      <>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <TextField
                            label="Qualification"
                            value={String(fact.qualification || "unknown")}
                            original={String(before?.qualification || "")}
                            readOnly={readOnly}
                            onCommit={(qualification) => updateFact(id, { qualification })}
                          />
                          <TextField
                            label="Valeur ou affirmation"
                            value={String(fact.value || "")}
                            original={String(before?.value || "")}
                            readOnly={readOnly}
                            multiline
                            onCommit={(value) => updateFact(id, { value })}
                          />
                        </div>

                        <TextField
                          label="Citation à contrôler dans le PDF"
                          value={String(fact.source_quote || "")}
                          original={String(before?.source_quote || "")}
                          readOnly={readOnly}
                          multiline
                          onCommit={(source_quote) =>
                            updateFact(id, {
                              source_quote,
                              citation_status: "unmatched",
                              citation_review: {},
                            })
                          }
                        />

                        {/* One-Click Validation Checkbox */}
                        {!readOnly && (
                          <label className="flex items-center gap-2.5 rounded-md border border-amber-300 bg-amber-50/90 p-2.5 text-xs font-medium text-amber-900 cursor-pointer hover:bg-amber-100 transition-colors">
                            <input
                              type="checkbox"
                              checked={false}
                              onChange={(event) => {
                                if (event.target.checked) {
                                  updateFact(id, {
                                    citation_status: "manual_verified",
                                    citation_review: {
                                      ...citationReview,
                                      verified_at: new Date().toISOString(),
                                      verified_method: "one_click_review",
                                    },
                                  });
                                }
                              }}
                              className="h-4 w-4 rounded border-amber-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                            />
                            <span>J’ai vérifié cette citation dans le PDF source.</span>
                          </label>
                        )}

                        {fact.verification_note ? (
                          <p className="text-xs text-amber-800">{String(fact.verification_note)}</p>
                        ) : null}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      );
    })()}
  </div>
);
}

  if (components.length === 0) {
    return (
      <EmptyState
        title="Aucun composant structuré"
        description="Le document n'a pas fourni de catalogue de composants exploitable."
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
                Difficulté de détection : {DIFFICULTY_LABELS[c.detection_difficulty] ?? c.detection_difficulty}
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label="Nom du composant"
                value={c.label}
                original={o?.label}
                readOnly={readOnly}
                onCommit={(label) => patchComponent(c.component_id, { label })}
              />
              <SelectField
                label="Type de composant"
                value={c.component_type}
                original={o?.component_type}
                options={COMPONENT_TYPES}
                readOnly={readOnly}
                onCommit={(component_type) =>
                  patchComponent(c.component_id, { component_type })
                }
              />
              <SelectField
                label="Difficulté de détection proposée"
                value={c.detection_difficulty}
                original={o?.detection_difficulty}
                options={DIFFICULTY}
                readOnly={readOnly}
                onCommit={(detection_difficulty) =>
                  patchComponent(c.component_id, { detection_difficulty })
                }
              />
              <NumberField
                label="Seuil indicatif de détection"
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
                label="Suggestions de détection (non validées)"
                values={c.candidate_detection_prompts}
                original={o?.candidate_detection_prompts}
                readOnly={readOnly}
                placeholder="Description candidate, à valider par essais"
                onCommit={(candidate_detection_prompts) =>
                  patchComponent(c.component_id, { candidate_detection_prompts })
                }
              />
            </div>

            <div className="mt-3">
              <TextField
                label="Notes de revue"
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
