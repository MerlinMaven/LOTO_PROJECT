/**
 * SmartLOTO - WorkflowReviewPanel (Lead UX & Full-Stack Refactor)
 *
 * Espace unique de revue centré sur le métier HSE :
 * 1. Cadrage épuré de l'intervention (Objectif, État final)
 * 2. Questions globales isolées en tête (aucune répétition sur les étapes)
 * 3. Affichage direct des phases et actions LOTO
 * 4. Badges contextuels locaux (Rouge = blocage, Orange = à examiner)
 * 5. Panneau de résolution contextuel sous chaque étape au clic
 * 6. Édition in-line fluide (instruction, méthode canonique, critères)
 * 7. Consignes avancées (sécurité, repli) accessibles sur demande.
 */

import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { clsx } from "clsx";
import { useReviewStore } from "@/store/reviewStore";
import { useResolveClarification } from "@/hooks/useProcedures";
import type { WorkflowDefinition } from "@/types/workflow";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { SelectField, TagListEditor, TextField } from "./fields";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  HelpCircle,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { env } from "@/config/env";
import { phaseLabel, PHASE_LABELS, moveStepToPhase } from "@/lib/workflow";

const VALIDATION_METHODS = [
  { value: "visual_observation", label: "Observation visuelle (caméra / repère)" },
  { value: "human_confirmation", label: "Confirmation humaine (contrôle physique)" },
  { value: "measurement", label: "Mesure instrumentale (VAT, manomètre, multimètre)" },
  { value: "sensor_signal", label: "Signal capteur (automate / télémesure)" },
  { value: "combined_evidence", label: "Preuves combinées" },
  { value: "not_defined", label: "À définir" },
];

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
  const setDraft = useReviewStore((s) => s.setDraft);

  const { procedureId } = useParams<{ procedureId: string }>();
  const resolveMutation = useResolveClarification(procedureId ?? "");
  const [resolutionError, setResolutionError] = useState("");
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  // États locaux de déploiement d'accordéons
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});
  const [openIssuesStep, setOpenIssuesStep] = useState<Record<string, boolean>>({});

  // Numérotation globale continue des actions (ex: A-01 -> 1, A-02 -> 2, etc.)
  const stepOrderMap = useMemo(() => {
    const map = new Map<string, number>();
    if (!draft?.phases) return map;
    let count = 1;
    draft.phases.forEach((ph) => {
      ph.stages?.forEach((st) => {
        st.steps?.forEach((sp) => {
          const match = String(sp.step_id || "").match(/[A-Za-z]+-0*(\d+)/);
          const num = match ? parseInt(match[1], 10) : count;
          map.set(sp.step_id, num);
          count++;
        });
      });
    });
    return map;
  }, [draft?.phases]);

  if (!draft) return null;

  const toggleDetails = (stepId: string) => {
    setExpandedDetails((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const toggleIssues = (stepId: string) => {
    setOpenIssuesStep((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const updateClarification = (questionId: string, patch: Record<string, unknown>) => {
    const questions = Array.isArray(draft.clarifications_required)
      ? (draft.clarifications_required as Record<string, unknown>[])
      : [];
    setDraft({
      ...draft,
      clarifications_required: questions.map((q) =>
        String(q.id) === questionId ? { ...q, ...patch } : q
      ),
    });
  };

  // Application complète d'une clarification : synchronise l'étape + le backend
  const handleApplyClarification = async (questionId: string) => {
    const q = allClarifications.find((item) => String(item.id) === questionId);
    if (!q || !procedureId) return;
    const res = (q.resolution ?? {}) as Record<string, unknown>;
    const answer = String(res.answer || "").trim();
    if (!answer) return;
    setResolvingId(questionId); setResolutionError("");
    try {
      const version = await resolveMutation.mutateAsync({
        clarification_id: questionId, answer, rationale: String(res.rationale || ""),
        answer_complete: res.answer_complete === true,
        affected_steps_reviewed: q.affected_steps_reviewed === true,
      });
      setDraft({ ...draft, clarifications_required: version.workflow_definition.clarifications_required,
        validation_diagnostics: version.workflow_definition.validation_diagnostics });
    } catch {
      setResolutionError("Enregistrement impossible. La question reste ouverte ; reessayez.");
    } finally { setResolvingId(null); }
  };

  // Documents sources pour affichage de références PDF
  const sourceDocs = Array.isArray(draft.source_documents)
    ? (draft.source_documents as Record<string, unknown>[])
    : [];
  const primarySource = sourceDocs[0];

  // 1. Définition stricte des clarifications globales (concernent le document entier)
  const isGlobalClarification = (q: Record<string, unknown>): boolean => {
    const affected = Array.isArray(q.affected_step_ids)
      ? (q.affected_step_ids as string[]).filter(Boolean)
      : [];
    const qId = String(q.id || "").toLowerCase();
    const qScope = String(q.scope || "").toLowerCase();

    // Portée globale explicite ou identifiant général
    if (
      qScope === "global" ||
      qScope === "procedure" ||
      qScope === "document" ||
      qId.includes("equipment-identity") ||
      qId.includes("equipment") ||
      qId.includes("final-state") ||
      qId.includes("objective") ||
      qId.includes("machine") ||
      qId.includes("scope") ||
      qId.includes("general")
    ) {
      return true;
    }

    // Si aucune étape spécifique n'est ciblée
    if (affected.length === 0) {
      return true;
    }

    return false;
  };

  const allClarifications = (draft.clarifications_required ?? []) as Record<string, unknown>[];
  // Questions globales qui vont EXCLUSIVEMENT dans la liste en haut
  const globalClarifications = allClarifications.filter(isGlobalClarification);

  // Filtrage strict des diagnostics : ignorer totalement source_integrity et logs internes
  const allDiagnostics = (draft.validation_diagnostics ?? []).filter((d) => {
    const cat = String(d.category || "").toLowerCase();
    const code = String(d.code || "").toLowerCase();
    const msg = String(d.message || "").toLowerCase();
    return (
      cat !== "source_integrity" &&
      !code.includes("fact_citation") &&
      !msg.includes("citation ne correspond pas") &&
      !msg.includes("texte extrait")
    );
  });



  // Masquage conditionnel des sous-titres redondants
  const isRedundantStage = (phaseTitle?: string, stagesCount?: number, stageTitle?: string): boolean => {
    if (!stageTitle) return true;
    if ((stagesCount ?? 0) <= 1) return true;
    const norm = (s?: string) =>
      String(s || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toLowerCase();
    return norm(stageTitle) === norm(phaseTitle);
  };

  return (
    <div className="space-y-6">
      {resolutionError && <p role="alert" className="text-red-700">{resolutionError}</p>}
      {/* ── 1. Cadrage synthétique de l'intervention (2 Cartes Bento côte à côte) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white rounded-[20px] p-5 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.04)] border border-slate-200/60">
          <TextField
            label="Objectif de maintenance"
            value={draft.maintenance_objective ?? ""}
            original={original?.maintenance_objective ?? ""}
            readOnly={readOnly}
            multiline
            rows={3}
            onCommit={(maintenance_objective) =>
              setDraft({ ...draft, maintenance_objective })
            }
          />
        </div>
        <div className="bg-white rounded-[20px] p-5 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.04)] border border-slate-200/60">
          <TextField
            label="État attendu après intervention"
            value={draft.expected_final_state ?? ""}
            original={original?.expected_final_state ?? ""}
            readOnly={readOnly}
            multiline
            rows={3}
            onCommit={(expected_final_state) =>
              setDraft({ ...draft, expected_final_state })
            }
          />
        </div>
      </div>

      {/* ── 2. Points généraux à trancher (Zéro répétition sur les étapes) ─── */}
      {globalClarifications.length > 0 && (
        <section className="rounded-xl border border-amber-300 bg-amber-50/70 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-950">
            <AlertTriangle className="h-4 w-4 text-amber-700" />
            <span>Points généraux à valider par le HSE ({globalClarifications.length})</span>
          </div>
          <p className="mt-1 text-xs text-amber-800">
            Ces décisions s'appliquent à l'ensemble de la procédure LOTO. Renseignez votre décision pour lever le blocage.
          </p>

          <div className="mt-3 space-y-3">
            {globalClarifications.map((q, idx) => {
              const qId = String(q.id || idx);
              const resolution = (q.resolution && typeof q.resolution === "object"
                ? q.resolution
                : {}) as Record<string, unknown>;
              const isResolved = q.status === "resolved";

              return (
                <div key={qId} className="rounded-lg border border-amber-200 bg-white p-3.5 shadow-sm text-xs">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="font-semibold text-slate-900">
                      <span className="mr-2 inline-block rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-900">
                        {String(q.impact || "Blocage")}
                      </span>
                      {String(q.question)}
                    </p>
                    {isResolved && (
                      <span className="flex items-center gap-1 font-semibold text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Tranché
                      </span>
                    )}
                  </div>

                  {q.why_needed ? (
                    <p className="mt-1 text-slate-600">{String(q.why_needed)}</p>
                  ) : null}

                  {!readOnly ? (
                    <div className="mt-2.5 space-y-2 border-t border-slate-100 pt-2.5">
                      <div className="grid gap-2 sm:grid-cols-2">
                        <input
                          type="text"
                          className="rounded border border-slate-300 px-2.5 py-1.5 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                          placeholder="Décision / Réponse HSE..."
                          value={String(resolution.answer || "")}
                          onChange={(e) =>
                            updateClarification(qId, {
                              resolution: { ...resolution, answer: e.target.value, answer_complete: false },
                              status: "unresolved",
                              affected_steps_reviewed: false,
                            })
                          }
                        />
                        <input
                          type="text"
                          className="rounded border border-slate-300 px-2.5 py-1.5 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                          placeholder="Justification technique ou référence doc..."
                          value={String(resolution.rationale || "")}
                          onChange={(e) =>
                            updateClarification(qId, {
                              resolution: { ...resolution, rationale: e.target.value },
                            })
                          }
                        />
                      </div>
                        <label className="block"><input type="checkbox" checked={resolution.answer_complete === true}
                          onChange={e => updateClarification(qId, { status: "unresolved", resolution: { ...resolution, answer_complete: e.target.checked } })} /> Reponse complete et justifiee pour tous les points de cette question.</label>
                        <label className="block"><input type="checkbox" checked={q.affected_steps_reviewed === true}
                          onChange={e => updateClarification(qId, { status: "unresolved", affected_steps_reviewed: e.target.checked })} /> Criteres observables des etapes concernees revus separement.</label>
                        <p>Une reponse partielle est conservee sans lever le blocage. Aucun critere n'est recopie automatiquement.</p>
                        <div className="flex items-center justify-between pt-1">
                          <Button
                            size="sm"
                            variant="primary"
                            disabled={!String(resolution.answer || "").trim() || resolvingId === qId}
                            onClick={() => handleApplyClarification(qId)}
                          >
                            {resolvingId === qId ? "Enregistrement..." : "Enregistrer la réponse"}
                          </Button>
                          {isResolved && (
                            <span className="text-emerald-700 font-semibold text-[11px] flex items-center gap-1">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Décision appliquée
                            </span>
                          )}
                        </div>
                      </div>
                  ) : (
                    <p className="mt-2 text-slate-700 font-medium">
                      Décision enregistrée : {String(resolution.answer || "Non renseignée")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── 3. Phases & Étapes de la procédure ──────────────────────────────── */}
      {(draft.phases?.length ?? 0) === 0 ? (
        <EmptyState
          title="Aucune phase dans ce brouillon"
          description="Aucune action structurée n’a été proposée. Complétez ou clarifiez l’objectif avant la revue HSE."
        />
      ) : (
        draft.phases.map((phase) => (
          <div
            key={phase.phase_id}
            className="bg-white/60 backdrop-blur-sm rounded-[24px] p-6 border border-slate-200/70 space-y-4 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.03)]"
          >
            {/* Titre de la phase */}
            <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="inline-flex items-center rounded-lg bg-blue-50 text-blue-700 border border-blue-200/60 text-xs font-bold uppercase tracking-wider px-3 py-1">
                  {phase.sequence}. {phaseLabel(String(phase.phase_type))}
                </span>
                <h3 className="text-base font-bold text-slate-900">
                  {phase.title}
                </h3>
              </div>
              <span className="text-xs font-mono font-semibold text-slate-500 bg-white/80 border border-slate-200/60 rounded-lg px-2.5 py-1 shadow-2xs">
                {phase.stages?.reduce((acc, st) => acc + (st.steps?.length ?? 0), 0) ?? 0} action(s)
              </span>
            </div>

            {/* Stages & Étapes */}
            <div className="space-y-6">
              {phase.stages.map((stage) => (
                <div key={stage.stage_id} className="space-y-3">
                  {!isRedundantStage(phase.title, phase.stages?.length ?? 0, stage.title) && (
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                      <span className="h-2 w-2 rounded-full bg-slate-400" />
                      {stage.title}
                    </div>
                  )}

                  <div className="space-y-3.5">
                    {stage.steps.map((step, idx) => {
                      const o = findOriginalStep(original, step.step_id);
                      const isExpanded = !!expandedDetails[step.step_id];
                      const isIssuesOpen = !!openIssuesStep[step.step_id];
                      const isDocumented = step.basis === "documented_procedure";

                      // Calcul STRICT des alertes et clarifications rattachées à cette étape spécifique
                      const stepClarifications = allClarifications.filter((q) => {
                        const stepComps = (step.component_refs ?? []) as string[];
                        const qComps = Array.isArray(q.related_component_ids)
                          ? (q.related_component_ids as string[])
                          : [];
                        // 1. Les composants de l'étape doivent croiser les composants de la clarification
                        if (stepComps.length > 0 && qComps.length > 0) {
                          return stepComps.some((c) => qComps.includes(c));
                        }
                        // 2. OU si aucun composant n'est renseigné sur la clarification, vérifier affected_step_ids
                        const affected = Array.isArray(q.affected_step_ids)
                          ? (q.affected_step_ids as string[])
                          : [];
                        if (qComps.length === 0 && affected.includes(step.step_id)) {
                          return true;
                        }
                        return false;
                      });

                      const stepDiagnostics = allDiagnostics.filter(
                        (d) => d.entity_id === step.step_id
                      );

                      const blockingClarifs = stepClarifications.filter(
                        (q) => q.status !== "resolved" && q.impact === "blocking"
                      );
                      const reviewClarifs = stepClarifications.filter(
                        (q) => q.status !== "resolved" && q.impact !== "blocking"
                      );
                      const blockingDiags = stepDiagnostics.filter(
                        (d) => d.severity === "blocking" || d.severity === "error"
                      );
                      const reviewDiags = stepDiagnostics.filter(
                        (d) => d.severity !== "blocking" && d.severity !== "error"
                      );

                      const totalBlockers = blockingClarifs.length + blockingDiags.length;
                      const totalReviews = reviewClarifs.length + reviewDiags.length;
                      const hasIssues = totalBlockers > 0 || totalReviews > 0;

                      const borderLeftClass = totalBlockers > 0
                        ? "border-l-4 border-l-rose-500"
                        : totalReviews > 0
                          ? "border-l-4 border-l-amber-500"
                          : "border-l-4 border-l-blue-600";

                      return (
                        <div
                          key={step.step_id}
                          className={clsx(
                            "bg-white rounded-2xl p-5 border border-slate-900/10 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all",
                            borderLeftClass
                          )}
                        >
                          {/* Ligne d'en-tête de l'étape */}
                          <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              {/* Numéro d'ordre global continu */}
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white shadow-sm shadow-blue-600/20">
                                {stepOrderMap.get(step.step_id) ?? step.sequence}
                              </span>
                              <code className="rounded-md bg-slate-100 border border-slate-200 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-700">
                                {step.step_id}
                              </code>

                              {/* Source IA vs Documentée */}
                              {isDocumented ? (
                                <span className="inline-flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 border border-blue-100">
                                  <CheckCircle2 className="h-3 w-3" />
                                  Source documentée
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700 border border-purple-100">
                                  <Sparkles className="h-3 w-3" />
                                  Proposition IA
                                </span>
                              )}

                              {/* Badges composants cibles AR (Liaison Workflow <-> AR) */}
                              {Array.isArray(step.component_refs) && step.component_refs.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1">
                                  {step.component_refs.map((ref: string) => (
                                    <span
                                      key={ref}
                                      className="inline-flex items-center gap-1 rounded-md bg-slate-100 border border-slate-200 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-700 shadow-xs"
                                      title={`Composant cible AR : ${ref}`}
                                    >
                                      <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                                      {ref}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {/* Badges locaux de problèmes */}
                              {totalBlockers > 0 && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    window.scrollTo({ top: 0, behavior: "smooth" });
                                    window.dispatchEvent(new CustomEvent("open-blocking-resolution"));
                                  }}
                                  className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-[11px] font-bold text-rose-800 border border-rose-200 hover:bg-rose-200 transition-colors cursor-pointer"
                                  title="Trancher dans le panneau central en haut de page"
                                >
                                  <AlertCircle className="h-3.5 w-3.5 text-rose-600" />
                                  Blocage ({totalBlockers}) ↑
                                </button>
                              )}

                              {totalReviews > 0 && totalBlockers === 0 && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    window.scrollTo({ top: 0, behavior: "smooth" });
                                    window.dispatchEvent(new CustomEvent("open-blocking-resolution"));
                                  }}
                                  className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-bold text-amber-800 border border-amber-200 hover:bg-amber-200 transition-colors cursor-pointer"
                                  title="Trancher dans le panneau central en haut de page"
                                >
                                  <HelpCircle className="h-3.5 w-3.5 text-amber-600" />
                                  À clarifier ({totalReviews}) ↑
                                </button>
                              )}

                              {totalBlockers === 0 && totalReviews === 0 && stepClarifications.some((q) => q.status === "resolved") && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                                  Clarification résolue
                                </span>
                              )}
                            </div>

                            {/* Déplacement d'étape */}
                            {!readOnly && (
                              <div className="flex items-center gap-1">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  disabled={idx === 0}
                                  onClick={() =>
                                    moveStep(
                                      phase.phase_id,
                                      stage.stage_id,
                                      step.step_id,
                                      "up"
                                    )
                                  }
                                  aria-label="Monter d'une position"
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
                                      "down"
                                    )
                                  }
                                  aria-label="Descendre d'une position"
                                >
                                  ↓
                                </Button>
                              </div>
                            )}
                          </div>

                          {/* Édition in-line principale (Instruction, Méthode, Critères) */}
                          <div className="space-y-3">
                            {/* Décisions HSE appliquées sur cette étape (distinction source vs décision) */}
                            {stepClarifications.filter((q) => q.status === "resolved").map((rq, rqIdx) => {
                              const rResolution = (rq.resolution && typeof rq.resolution === "object"
                                ? rq.resolution
                                : {}) as Record<string, unknown>;
                              return (
                                <div
                                  key={String(rq.id || rqIdx)}
                                  className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-xs text-emerald-950 flex flex-wrap items-center justify-between gap-2 shadow-2xs"
                                >
                                  <div className="space-y-0.5">
                                    <div className="flex items-center gap-1.5 font-bold text-emerald-900">
                                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                                      <span>Décision HSE validée : {String(rResolution.answer || "")}</span>
                                    </div>
                                    <p className="text-[11px] text-emerald-800 pl-5.5">
                                      {String(rq.question)}
                                      {rResolution.rationale ? (
                                        <span className="text-emerald-700 italic"> — {String(rResolution.rationale)}</span>
                                      ) : null}
                                    </p>
                                  </div>
                                  <span className="rounded-md border border-emerald-300 bg-emerald-100/80 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                                    Décision HSE enregistrée
                                  </span>
                                </div>
                              );
                            })}

                            <TextField
                              label="Instruction d'exécution"
                              value={step.instruction}
                              original={o?.instruction}
                              readOnly={readOnly}
                              multiline
                              onCommit={(instruction) =>
                                patchStep(
                                  phase.phase_id,
                                  stage.stage_id,
                                  step.step_id,
                                  { instruction }
                                )
                              }
                            />

                            <div className="grid gap-3 sm:grid-cols-2">
                              <SelectField label="Phase de l’action" value={String(step.execution_phase || phase.phase_type)}
                                options={[...Object.entries(PHASE_LABELS).map(([value,label]) => ({value,label})),
                                  ...(!PHASE_LABELS[phase.phase_type] ? [{value: phase.phase_type, label: phaseLabel(phase.phase_type)}] : [])]}
                                readOnly={readOnly} onCommit={kind => setDraft(moveStepToPhase(draft, step.step_id, kind))} />
                              <SelectField
                                label="Méthode de validation"
                                value={
                                  step.verification?.method ??
                                  step.validation?.method ??
                                  "not_defined"
                                }
                                original={o?.verification?.method ?? o?.validation?.method}
                                options={(step.execution_phase || phase.phase_type).toLowerCase() === "maintenance"
                                  ? VALIDATION_METHODS.filter(m => m.value === "human_confirmation") : VALIDATION_METHODS}
                                readOnly={readOnly}
                                onCommit={(method) =>
                                  patchStep(
                                    phase.phase_id,
                                    stage.stage_id,
                                    step.step_id,
                                    {
                                      verification: {
                                        ...(step.verification ?? step.validation ?? {}),
                                        method,
                                      },
                                    }
                                  )
                                }
                              />
                              <TextField
                                label={step.verification?.method === "human_confirmation" ? "Critères de réalisation (facultatifs, sans contrôle caméra)" : "Critères observables (un par ligne)"}
                                multiline
                                rows={Math.max(2, (step.verification?.criteria ?? []).length || 1)}
                                value={(
                                  step.verification?.criteria ??
                                  (step.validation?.expected_state
                                    ? [step.validation.expected_state]
                                    : [])
                                ).join("\n")}
                                original={(
                                  o?.verification?.criteria ??
                                  (o?.validation?.expected_state
                                    ? [o.validation.expected_state]
                                    : [])
                                ).join("\n")}
                                readOnly={readOnly}
                                onCommit={(expected_state) =>
                                  patchStep(
                                    phase.phase_id,
                                    stage.stage_id,
                                    step.step_id,
                                    {
                                      verification: {
                                        ...(step.verification ??
                                          step.validation ?? { method: "not_defined" }),
                                        criteria: expected_state
                                          .split("\n")
                                          .map((v) => v.trim())
                                          .filter(Boolean),
                                      },
                                    }
                                  )
                                }
                              />
                            </div>
                            {step.verification?.method === "human_confirmation" && <p className="text-sm text-blue-800">
                              Confirmation humaine normale : aucune photo, IA ou dérogation requise. Le guidage reste indépendant de cette validation.
                            </p>}

                            {/* ── 4. Zone contextuelle des problèmes locaux (au clic) ─── */}
                            {hasIssues && isIssuesOpen && (
                              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/50 p-3.5 space-y-3 text-xs">
                                <div className="flex items-center justify-between font-bold text-amber-900 border-b border-amber-200/60 pb-1.5">
                                  <span className="flex items-center gap-1.5">
                                    <ShieldAlert className="h-4 w-4 text-amber-700" />
                                    Diagnostics & Points à lever pour cette action
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => toggleIssues(step.step_id)}
                                    className="text-amber-800 hover:text-amber-950 underline font-normal"
                                  >
                                    Fermer
                                  </button>
                                </div>

                                {/* Diagnostics techniques bloquants */}
                                {stepDiagnostics.map((diag, dIdx) => (
                                  <div
                                    key={dIdx}
                                    className="flex items-start gap-2 rounded bg-white p-2.5 border border-amber-200/70"
                                  >
                                    <AlertCircle
                                      className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                                        diag.severity === "blocking"
                                          ? "text-rose-600"
                                          : "text-amber-600"
                                      }`}
                                    />
                                    <div>
                                      <p className="font-semibold text-slate-800">
                                        {diag.message}
                                      </p>
                                      <p className="text-[11px] text-slate-500">
                                        Code technique : <code className="font-mono">{diag.code}</code>
                                      </p>
                                    </div>
                                  </div>
                                ))}

                                {/* Clarifications liées (Centralisées) */}
                                {stepClarifications.map((q, qIdx) => {
                                  const qId = String(q.id || qIdx);
                                  const res = (q.resolution && typeof q.resolution === "object"
                                    ? q.resolution
                                    : {}) as Record<string, unknown>;
                                  const isResolved = q.status === "resolved";
                                  const relatedComps = Array.isArray(q.related_component_ids)
                                    ? (q.related_component_ids as string[]).filter(Boolean)
                                    : [];
                                  let ruleId = "R-0" + (qIdx + 1);
                                  if (relatedComps.includes("C05") || relatedComps.includes("C07")) ruleId = "R-01";
                                  else if (relatedComps.includes("C06")) ruleId = "R-02";
                                  else if (relatedComps.includes("C02") || relatedComps.includes("C03")) ruleId = "R-03";
                                  else if (relatedComps.includes("C04")) ruleId = "R-04";

                                  const compLabel = relatedComps.length > 0 ? relatedComps.join(" / ") : "";
                                  const prefix = compLabel ? `[${ruleId} • ${compLabel}]` : `[${ruleId}]`;
                                  const whyNeeded = String(q.why_needed || "").replace(/indeterminate/gi, "indéterminée");

                                  return (
                                    <div
                                      key={qId}
                                      className={clsx(
                                        "rounded-lg p-3 border shadow-2xs space-y-1.5 text-xs transition-all",
                                        isResolved
                                          ? "bg-white border-emerald-200"
                                          : "bg-white border-amber-200"
                                      )}
                                    >
                                      <div className="flex items-start justify-between gap-2">
                                        <p className="font-semibold text-slate-900 leading-snug">
                                          <span className="font-mono text-amber-900 font-bold mr-1.5 bg-amber-100 px-1.5 py-0.5 rounded text-[11px]">
                                            {prefix}
                                          </span>
                                          {String(q.question)}
                                        </p>
                                        {primarySource && Array.isArray(q.source_pages) && q.source_pages.length > 0 && (
                                          <a
                                            href={`${env.apiBaseUrl}/v1/generation/documents/${String(primarySource.source_id)}`}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:underline shrink-0"
                                          >
                                            <FileText className="h-3 w-3" />
                                            Page(s) {q.source_pages.join(", ")}
                                          </a>
                                        )}
                                      </div>

                                      {whyNeeded ? (
                                        <p className="text-[11px] text-slate-600 leading-relaxed">
                                          {whyNeeded}
                                        </p>
                                      ) : null}

                                      {isResolved ? (
                                        <div className="flex items-center gap-1.5 text-emerald-800 font-medium text-[11px] bg-emerald-50 px-2.5 py-1.5 rounded border border-emerald-200">
                                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                                          <span>
                                            Décision HSE validée : <strong>{String(res.answer || "")}</strong>
                                            {res.rationale ? <span className="text-emerald-700 font-normal"> ({String(res.rationale)})</span> : null}
                                          </span>
                                        </div>
                                      ) : (
                                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-100">
                                          <span className="text-[11px] text-amber-800 italic">
                                            Point bloquant à trancher au niveau central du dossier.
                                          </span>
                                          <button
                                            type="button"
                                            onClick={() => {
                                              window.scrollTo({ top: 0, behavior: "smooth" });
                                              window.dispatchEvent(new CustomEvent("open-blocking-resolution"));
                                            }}
                                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-2.5 py-1 rounded border border-rose-300 transition cursor-pointer shadow-2xs"
                                          >
                                            Trancher dans le panneau central ↑
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Bouton pour détails avancés (non indispensables au premier regard) */}
                            <button
                              type="button"
                              onClick={() => toggleDetails(step.step_id)}
                              className="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors pt-1"
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5" />
                              )}
                              <span>
                                {isExpanded
                                  ? "Masquer les consignes avancées (repli, sécurité)"
                                  : "Afficher les consignes avancées (repli, sécurité, preuves)"}
                              </span>
                            </button>

                            {/* Section détails avancés */}
                            {isExpanded && (
                              <div className="space-y-3 rounded-lg border border-slate-100 bg-slate-50/70 p-3.5 text-xs">
                                <div className="rounded bg-white p-2.5 text-slate-600 border border-slate-200/60 space-y-1">
                                  <p>
                                    <strong>Conditions indéterminées :</strong>{" "}
                                    {(step.verification?.indeterminate_when ?? []).join(" ; ") ||
                                      "Non spécifié"}
                                  </p>
                                  <p>
                                    <strong>Preuves attendues :</strong>{" "}
                                    {(step.verification?.required_evidence ?? []).join(" ; ") ||
                                      "Non spécifié"}
                                  </p>
                                </div>

                                <TextField
                                  label="Note de sécurité"
                                  value={step.safety_note ?? ""}
                                  original={o?.safety_note ?? ""}
                                  readOnly={readOnly}
                                  onCommit={(safety_note) =>
                                    patchStep(
                                      phase.phase_id,
                                      stage.stage_id,
                                      step.step_id,
                                      { safety_note }
                                    )
                                  }
                                />

                                <TextField
                                  label="Instruction de repli ou d'arrêt sécurisé"
                                  value={step.rollback_instruction ?? ""}
                                  original={o?.rollback_instruction ?? ""}
                                  readOnly={readOnly}
                                  multiline
                                  hint="Conduite à tenir si l'action ne peut pas être exécutée en sécurité."
                                  onCommit={(rollback_instruction) =>
                                    patchStep(
                                      phase.phase_id,
                                      stage.stage_id,
                                      step.step_id,
                                      { rollback_instruction }
                                    )
                                  }
                                />

                                <TagListEditor
                                  label="Avertissements et risques résiduels"
                                  values={step.warnings ?? []}
                                  original={o?.warnings ?? []}
                                  readOnly={readOnly}
                                  placeholder="Risque de brûlure, pression résiduelle..."
                                  onCommit={(warnings) =>
                                    patchStep(
                                      phase.phase_id,
                                      stage.stage_id,
                                      step.step_id,
                                      { warnings }
                                    )
                                  }
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
