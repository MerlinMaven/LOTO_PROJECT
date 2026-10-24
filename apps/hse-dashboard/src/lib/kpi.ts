import type { ProcedureListItem } from "@/types/procedure";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface ConfidenceBreakdown {
  /** Score global sur 100 (entier). */
  score: number;
  breakdown: {
    /** Pilier 1 — Extraction structurelle (max 40 pts). */
    structureScore: number;
    /** Pilier 2 — Maturité métier / blocages HSE (max 40 pts). */
    blockingScore: number;
    /** Pilier 3 — Ancrage documentaire / citations (max 20 pts). */
    citationScore: number;
    /** Nombre de points bloquants métier (hors bruit IA). */
    blockingCount: number;
    /** Nombre de faits avec citation_status === 'unmatched'. */
    unmatchedCount: number;
    /** Nombre total de faits techniques. */
    totalFacts: number;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Filtre dérivé des erreurs métier
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Ne compte QUE les items où la severity est 'blocking' ou 'error'
 * et ignore les logs de citation LLM (source_integrity, fact_citation*, etc.)
 */
export function getBusinessBlockingCount(
  item: ProcedureListItem | { workflow_definition?: Record<string, unknown> | null; open_validation_errors?: number }
): number {
  const wf = item.workflow_definition as Record<string, unknown> | undefined;
  if (!wf) {
    return item.open_validation_errors ?? 0;
  }

  const diags = Array.isArray(wf.validation_diagnostics)
    ? (wf.validation_diagnostics as Array<Record<string, unknown>>)
    : [];

  const blockingDiags = diags.filter((d) => {
    const sev = String(d.severity || "").toLowerCase();
    const cat = String(d.category || "").toLowerCase();
    const code = String(d.code || "").toLowerCase();
    const msg = String(d.message || "").toLowerCase();
    if (code === "verification_method_unsupported_by_operator_client") return false;
    const isBlocking = sev === "blocking" || sev === "error";
    const isAIInternalTrace =
      cat === "source_integrity" ||
      code.includes("fact_citation") ||
      msg.includes("citation ne correspond pas") ||
      msg.includes("texte extrait");
    return isBlocking && !isAIInternalTrace;
  });

  const clarifs = Array.isArray(wf.clarifications_required)
    ? (wf.clarifications_required as Array<Record<string, unknown>>)
    : [];
  const openClarifsCount = clarifs.filter(
    (q) => q.status !== "resolved" && !String((q.resolution as { answer?: string } | undefined)?.answer || "").trim()
  ).length;

  const nonClarificationBlockingDiags = blockingDiags.filter((d) => {
    const code = String(d.code || "").toUpperCase();
    return !code.includes("CLARIFICATION");
  });

  let stepBlockingCount = 0;
  const phases = Array.isArray(wf.phases)
    ? (wf.phases as Array<{ stages?: Array<{ steps?: Array<Record<string, unknown>> }> }>)
    : [];
  phases.forEach((p) =>
    (p.stages ?? []).forEach((st) =>
      (st.steps ?? []).forEach((step) => {
        const sDiags = Array.isArray(step.diagnostics)
          ? (step.diagnostics as Array<Record<string, unknown>>)
          : [];
        sDiags.forEach((d) => {
          const sev = String(d.severity || "").toLowerCase();
          const cat = String(d.category || "").toLowerCase();
          if ((sev === "blocking" || sev === "error") && !d.resolved && cat !== "source_integrity") {
            stepBlockingCount++;
          }
        });
      })
    )
  );

  return nonClarificationBlockingDiags.length + stepBlockingCount + openClarifsCount;
}

// ─────────────────────────────────────────────────────────────────────────────
// Formule de confiance multicritère pondérée (3 piliers)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Calcule le score de confiance pondéré sur 100 pts, décomposé en 3 piliers :
 *
 * ┌─────────────────────────────────────────────────── max ──┐
 * │ Pilier 1 — Extraction structurelle (composants, étapes,  │  40 pts
 * │            observations visuelles / AR)                   │
 * │ Pilier 2 — Maturité métier & blocages HSE                │  40 pts
 * │            max(0, 40 − B × 6) avec B = points bloquants  │
 * │ Pilier 3 — Ancrage documentaire / citations              │  20 pts
 * │            proportionnel à (total − unmatched) / total   │
 * └───────────────────────────────────────────────────────────┘
 */
export function calculateConfidenceBreakdown(
  workflowOrItem?: Record<string, unknown> | null
): ConfidenceBreakdown | null {
  if (!workflowOrItem) return null;

  const workflow = (workflowOrItem.workflow_definition && typeof workflowOrItem.workflow_definition === "object"
    ? workflowOrItem.workflow_definition
    : workflowOrItem) as Record<string, unknown>;

  // ── Pilier 1 : Socle d'extraction structurelle ────────────────────────────
  const components = Array.isArray(workflow.components)
    ? (workflow.components as unknown[])
    : [];
  const visualObs = Array.isArray(workflow.visual_observations)
    ? (workflow.visual_observations as unknown[])
    : [];

  const phases = Array.isArray(workflow.phases)
    ? (workflow.phases as Array<{ stages?: Array<{ steps?: Array<Record<string, unknown>> }> }>)
    : [];
  const allSteps = phases.flatMap((p) =>
    (p.stages ?? []).flatMap((st) => st.steps ?? [])
  );

  let structureScore = 0;
  if (components.length > 0) structureScore += 15; // Composants extraits
  if (allSteps.length > 0) structureScore += 15;    // Étapes de workflow générées
  if (visualObs.length > 0) structureScore += 10;   // Ancres AR / observations visuelles
  // Max = 40 pts

  // ── Pilier 2 : Maturité métier & blocages HSE ─────────────────────────────
  const NOISE_CODES = new Set([
    "fact_citation_unverified",
    "source_integrity",
    "verification_method_unsupported_by_operator_client",
  ]);

  const isBusinessBlocking = (d: Record<string, unknown>): boolean => {
    const sev = String(d.severity || "").toLowerCase();
    const cat = String(d.category || "").toLowerCase();
    const code = String(d.code || "").toLowerCase();
    const msg = String(d.message || "").toLowerCase();
    if (!(sev === "blocking" || sev === "error")) return false;
    if (cat === "source_integrity") return false;
    if (NOISE_CODES.has(code)) return false;
    if (code.includes("fact_citation")) return false;
    if (msg.includes("citation ne correspond pas") || msg.includes("texte extrait")) return false;
    return !d.resolved;
  };

  const diags = Array.isArray(workflow.validation_diagnostics)
    ? (workflow.validation_diagnostics as Array<Record<string, unknown>>)
    : [];
  const globalBlockingDiags = diags.filter(isBusinessBlocking);

  const hasClarifDiags = globalBlockingDiags.some((d) =>
    String(d.code || "").toUpperCase().includes("CLARIFICATION")
  );

  let stepBlockingCount = 0;
  phases.forEach((p) =>
    (p.stages ?? []).forEach((st) =>
      (st.steps ?? []).forEach((step) => {
        const stepDiags = Array.isArray(step.diagnostics)
          ? (step.diagnostics as Array<Record<string, unknown>>)
          : [];
        stepDiags.forEach((d) => {
          if (isBusinessBlocking(d)) stepBlockingCount++;
        });
      })
    )
  );

  let extraClarifCount = 0;
  if (!hasClarifDiags) {
    const clarifs = Array.isArray(workflow.clarifications_required)
      ? (workflow.clarifications_required as Array<Record<string, unknown>>)
      : [];
    extraClarifCount = clarifs.filter((q) => q.status !== "resolved").length;
  }

  const blockingCount = globalBlockingDiags.length + stepBlockingCount + extraClarifCount;
  const blockingScore = Math.max(0, 40 - blockingCount * 6);
  // Max = 40 pts ; 0 blocage = 40, 4 blocages = 16, 7 blocages = 0 (plancher)

  // ── Pilier 3 : Ancrage documentaire / citations ───────────────────────────
  const facts = Array.isArray(workflow.technical_facts)
    ? (workflow.technical_facts as Array<Record<string, unknown>>)
    : [];
  const totalFacts = facts.length;
  const unmatchedCount = facts.filter(
    (f) => f.citation_status === "unmatched"
  ).length;

  const citationScore =
    totalFacts === 0
      ? 20
      : Math.round(20 * ((totalFacts - unmatchedCount) / totalFacts));
  // Max = 20 pts ; pénalité plafonnée à −20 pts sur le score global

  // ── Score total ───────────────────────────────────────────────────────────
  const score = Math.min(100, Math.max(0, Math.round(structureScore + blockingScore + citationScore)));

  return {
    score,
    breakdown: {
      structureScore,
      blockingScore,
      citationScore,
      blockingCount,
      unmatchedCount,
      totalFacts,
    },
  };
}

/**
 * Raccourci : retourne le score normalisé 0..1 pour la ConfidenceBar.
 */
export function calculateConfidenceScore(
  workflow?: Record<string, unknown> | null
): number | null {
  const result = calculateConfidenceBreakdown(workflow);
  return result ? result.score / 100 : null;
}
