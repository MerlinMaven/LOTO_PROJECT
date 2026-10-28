import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { clsx } from "clsx";
import { useProcedure, useUpdateDraft, useResolveClarification } from "@/hooks/useProcedures";
import { useReviewStore } from "@/store/reviewStore";
import { useAuthStore } from "@/store/authStore";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { QRCodeModal } from "@/components/ui/QRCodeModal";
import { ComponentReviewPanel } from "@/components/review/ComponentReviewPanel";
import { WorkflowReviewPanel } from "@/components/review/WorkflowReviewPanel";
import { VisionPanel } from "@/components/review/VisionPanel";
import { DiffViewer } from "@/components/review/DiffViewer";
import { ReviewMetricsPanel } from "@/components/review/ReviewMetricsPanel";
import { AuditHistoryPanel } from "@/components/review/AuditHistoryPanel";
import { ApprovalWorkflow } from "@/components/review/ApprovalWorkflow";
import { SOURCE_LABELS, isEditable } from "@/lib/status";
import { formatDate } from "@/lib/format";
import { getBusinessBlockingCount, isClarificationResolved } from "@/lib/kpi";
import type { ApiError } from "@/types/api";
import {
  ArrowLeft,
  QrCode,
  Save,
  RotateCcw,
  AlertTriangle,
  AlertCircle,
  Cpu,
  GitBranch,
  Eye,
  GitCompare,
  BarChart2,
  ClipboardCheck,
  FileText,
  LucideIcon,
  Lock,
  X,
  ChevronRight,
  ShieldAlert,
  CheckCircle2,
} from "lucide-react";
import { env } from "@/config/env";


type TabKey =
  | "workflow"
  | "components"
  | "vision"
  | "diff"
  | "metrics"
  | "audit";

const TABS: { key: TabKey; label: string; Icon: LucideIcon }[] = [
  { key: "workflow",   label: "Workflow (Procédure)", Icon: GitBranch },
  { key: "components", label: "Composants",           Icon: Cpu },
  { key: "vision",     label: "Vision",               Icon: Eye },
  { key: "diff",       label: "Différences",          Icon: GitCompare },
  { key: "metrics",    label: "Métriques",            Icon: BarChart2 },
  { key: "audit",      label: "Audit",                Icon: ClipboardCheck },
];

function getClarificationPlaceholder(question: string, ruleId: string): string {
  const qLower = question.toLowerCase();
  if (
    qLower.includes("interrupteur") ||
    qLower.includes("haut") ||
    qLower.includes("bas") ||
    qLower.includes("position") ||
    ruleId === "R-01"
  ) {
    return "ex: HAUT = OUVERT / BAS = FERMÉ...";
  }
  if (
    qLower.includes("clé") ||
    qLower.includes("carter") ||
    qLower.includes("verrou") ||
    ruleId === "R-02"
  ) {
    return "ex: Clé prisonnière consignée sous cadenas...";
  }
  if (
    qLower.includes("seuil") ||
    qLower.includes("tension") ||
    qLower.includes("multimètre") ||
    qLower.includes("vat") ||
    ruleId === "R-03"
  ) {
    return "ex: Seuil < 50V AC/DC, mesure au VAT homologué...";
  }
  if (
    qLower.includes("lampe") ||
    qLower.includes("pile") ||
    qLower.includes("remplacement") ||
    ruleId === "R-04"
  ) {
    return "ex: Pile 9V déconnectée avant manipulation de l'ampoule...";
  }
  return "Saisissez la décision technique HSE...";
}

export function DraftReview() {
  const { procedureId } = useParams<{ procedureId: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("workflow");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [qrOpen, setQrOpen] = useState(false);

  const {
    data: procedure,
    isLoading,
    isError,
    error,
  } = useProcedure(procedureId);
  const reviewerId = useAuthStore((s) => s.reviewerId);

  const load        = useReviewStore((s) => s.load);
  const reset       = useReviewStore((s) => s.reset);
  const commitSaved = useReviewStore((s) => s.commitSaved);
  const isDirty     = useReviewStore((s) => s.isDirty);
  const draft       = useReviewStore((s) => s.draft);

  const version  = procedure?.review_version ?? procedure?.active_version ?? null;
  const editable = version ? isEditable(version.status) : false;

  const resolveMutation = useResolveClarification(procedureId ?? "");
  const [resolvingAnswers, setResolvingAnswers] = useState<Record<string, string>>({});
  const [resolvingRationales, setResolvingRationales] = useState<Record<string, string>>({});
  const [submittingClarifId, setSubmittingClarifId] = useState<string | null>(null);
  const [editingClarifId, setEditingClarifId] = useState<string | null>(null);

  // Écouteur d'événement pour ouverture centralisée depuis n'importe quel onglet/étape
  useEffect(() => {
    const handler = () => {
      setBlockingSummaryOpen(true);
      setTimeout(() => {
        document.getElementById("blocking-resolution-center")?.scrollIntoView({ behavior: "smooth" });
      }, 60);
    };
    window.addEventListener("open-blocking-resolution", handler);
    return () => window.removeEventListener("open-blocking-resolution", handler);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (version) load(version);
  }, [version?.id]);

  const updateDraft = useUpdateDraft(procedureId ?? "");

  const handleSave = async () => {
    if (!draft || !version) return;
    setSaveError(null);
    try {
      const saved = await updateDraft.mutateAsync({
        workflow_definition: draft,
        edited_by: reviewerId,
      });
      commitSaved(saved);
      if (unresolvedClarificationsCount === 0) {
        setBlockingSummaryOpen(false);
      }
    } catch (err) {
      setSaveError((err as ApiError).message ?? "Échec de l'enregistrement.");
    }
  };

  // Résolution centralisée et directe des points bloquants (Zéro répétition)
  const handleResolveClarificationCentral = async (questionId: string) => {
    const question = draft?.clarifications_required?.find((item) => String(item.id) === questionId);
    const resolution = (question?.resolution ?? {}) as Record<string, unknown>;
    const answer = (resolvingAnswers[questionId] ?? String(resolution.answer ?? "")).trim();
    const rationale = (resolvingRationales[questionId] ?? String(resolution.rationale ?? "")).trim();
    if (!answer || !rationale || !draft) {
      setSaveError("La d\u00e9cision et sa justification sont requises pour confirmer la r\u00e9solution HSE.");
      return;
    }
    setSaveError(null);

    setResolvingAnswers((prev) => ({ ...prev, [questionId]: answer }));
    setSubmittingClarifId(questionId);
    try {
      // Save pending component/citation edits before resolving on the server.
      if (useReviewStore.getState().isDirty()) {
        const saved = await updateDraft.mutateAsync({ workflow_definition: draft, edited_by: reviewerId });
        commitSaved(saved);
      }
      const saved = await resolveMutation.mutateAsync({
        clarification_id: questionId,
        answer,
        rationale,
        answer_complete: true,
        affected_steps_reviewed: true,
      });
      commitSaved(saved);
      const updatedQuestions = saved.workflow_definition.clarifications_required ?? [];

      setEditingClarifId(null);
      if (updatedQuestions.every(isClarificationResolved)) {
        setBlockingSummaryOpen(false);
      }
    } catch (err) {
      setSaveError((err as ApiError).message ?? "La r\u00e9solution n\u2019a pas pu \u00eatre enregistr\u00e9e.");
    } finally {
      setSubmittingClarifId(null);
    }
  };

  // ── 4-Eyes Rule & Dev Bypass ──────────────────────────────────────────
  const authorId = version?.created_by ?? procedure?.created_by;
  const isSelfReview = Boolean(
    reviewerId && authorId && reviewerId.trim().toLowerCase() === authorId.trim().toLowerCase()
  );
  const isDev = import.meta.env.DEV;
  const fourEyesBlocked = isSelfReview && !isDev;

  // ── Stats calculation ──────────────────────────────────────────────────
  const dirty = isDirty();
  const activeVersion = useMemo(() => procedure?.review_version ?? procedure?.active_version ?? null, [procedure]);
  const activeWorkflow = draft as Record<string, unknown> | null;
  const sourceDocuments = Array.isArray(activeWorkflow?.source_documents)
    ? (activeWorkflow.source_documents as Record<string, unknown>[])
    : [];
  const sourceDocument = sourceDocuments[0];
  const openQuestions = Array.isArray(activeWorkflow?.clarifications_required)
    ? (activeWorkflow.clarifications_required as Record<string, unknown>[])
    : [];

  const unresolvedClarificationsCount = useMemo(() => {
    return openQuestions.filter((q) => !isClarificationResolved(q)).length;
  }, [openQuestions]);

  const totalBlockingCount = useMemo(() => {
    const wf = (draft ?? activeWorkflow) as Record<string, unknown> | null;
    if (wf) {
      return getBusinessBlockingCount({ workflow_definition: wf });
    }
    const raw = activeVersion?.validation_errors ?? [];
    const filtered = raw.filter((err) => {
      const lower = String(err).toLowerCase();
      return (
        !lower.includes("source_integrity") &&
        !lower.includes("citation ne correspond pas") &&
        !lower.includes("fact_citation") &&
        !lower.includes("texte extrait")
      );
    });
    return new Set(filtered).size;
  }, [draft, activeWorkflow, activeVersion?.validation_errors]);

  // ── Central Resolution Panel toggle ─────────────────────────────────────
  const [blockingSummaryOpen, setBlockingSummaryOpen] = useState(false);

  // ── Loading / error ───────────────────────────────────────────────────────
  if (isLoading) return <LoadingPane label="Chargement de la procédure…" />;

  if (isError || !procedure) {
    return (
      <EmptyState
        title="Procédure introuvable"
        description={(error as ApiError)?.message ?? "Impossible de charger cette procédure."}
        action={
          <Button variant="secondary" onClick={() => navigate("/procedures")}>
            Retour à la liste
          </Button>
        }
      />
    );
  }

  // ── Page ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* ── HSE Header: Equipment, Objective, Status, Readiness, Actions ──────────────── */}
      <div className="rounded-[20px] border border-slate-900/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all">
        {/* Breadcrumb */}
        <button
          onClick={() => navigate("/procedures")}
          className="mb-3.5 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition-colors hover:text-blue-600 cursor-pointer"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Retour aux procédures
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          {/* Title & machine */}
          <div className="max-w-2xl">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-xl font-bold tracking-tight text-slate-900">
                {procedure.title}
              </h2>
              <span className="rounded-lg bg-slate-100 border border-slate-200 px-2.5 py-0.5 font-mono text-xs font-bold text-slate-700">
                {procedure.machine_id}
              </span>
              {version && <StatusBadge status={version.status} />}
              {version && (
                <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-0.5 font-mono text-xs font-semibold text-slate-600">
                  v{version.version_number}
                </span>
              )}
            </div>

            {/* Objective / Scope */}
            {activeWorkflow?.objective ? (
              <p className="mt-2 text-xs text-slate-600 leading-relaxed">
                <span className="font-semibold text-slate-700">Objectif : </span>
                {String(activeWorkflow.objective)}
              </p>
            ) : null}

            {/* Summary indicators */}
            <div className="mt-3.5 flex flex-wrap items-center gap-2.5 text-xs">
              {/* Readiness status — clickable to open Central Resolution Center */}
              {totalBlockingCount > 0 ? (
                <button
                  id="toggle-blocking-summary-btn"
                  type="button"
                  onClick={() => setBlockingSummaryOpen((v) => !v)}
                  title="Ouvrir le Centre de Résolution Direct des points bloquants"
                  className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 border border-rose-200 px-3 py-1 font-semibold text-rose-700 hover:bg-rose-100 transition cursor-pointer shadow-xs"
                >
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {totalBlockingCount} point{totalBlockingCount > 1 ? "s" : ""} bloquant{totalBlockingCount > 1 ? "s" : ""}
                  <ChevronRight className={clsx("h-3 w-3 transition-transform", blockingSummaryOpen && "rotate-90")} />
                </button>
              ) : unresolvedClarificationsCount > 0 ? (
                <button
                  id="toggle-blocking-summary-btn"
                  type="button"
                  onClick={() => setBlockingSummaryOpen((v) => !v)}
                  title="Examiner les clarifications HSE"
                  className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 font-semibold text-amber-800 hover:bg-amber-100 transition cursor-pointer shadow-xs"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  {unresolvedClarificationsCount} clarification{unresolvedClarificationsCount > 1 ? "s" : ""} à examiner
                  <ChevronRight className={clsx("h-3 w-3 transition-transform", blockingSummaryOpen && "rotate-90")} />
                </button>
              ) : (
                <button
                  id="toggle-blocking-summary-btn"
                  type="button"
                  onClick={() => setBlockingSummaryOpen((v) => !v)}
                  title="Voir les décisions HSE validées"
                  className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 font-semibold text-emerald-700 hover:bg-emerald-100 transition cursor-pointer shadow-xs"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  ✓ Prêt pour publication ({openQuestions.length} décisions validées)
                  <ChevronRight className={clsx("h-3 w-3 transition-transform", blockingSummaryOpen && "rotate-90")} />
                </button>
              )}

              {/* Source PDF */}
              {Boolean(sourceDocument?.source_id) && (
                <a
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-blue-700 transition"
                  href={`${env.apiBaseUrl}/v1/generation/documents/${String(sourceDocument?.source_id)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileText className="h-3.5 w-3.5 text-slate-500" />
                  Source : {String(sourceDocument?.filename || "PDF")}
                </a>
              )}

              {/* Last update */}
              {version?.updated_at && (
                <span className="text-[11px] text-slate-400">
                  Mis à jour le {formatDate(version.updated_at)}
                </span>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex shrink-0 items-center gap-2">
            {/* Le bouton QR Code ne doit JAMAIS être rendu si le statut n'est pas PUBLISHED */}
            {version?.status === "published" && (
              <button
                onClick={() => setQrOpen(true)}
                title="Afficher le QR Code machine pour opérateurs"
                className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 hover:text-blue-600"
              >
                <QrCode className="h-4 w-4" />
                QR Code
              </button>
            )}

            {editable && (
              <>
                <button
                  onClick={reset}
                  disabled={!dirty || updateDraft.isPending}
                  className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
                  title="Annuler les modifications non enregistrées"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Annuler
                </button>
                <button
                  onClick={handleSave}
                  disabled={!dirty || updateDraft.isPending}
                  className={clsx(
                    "flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold shadow-xs transition",
                    dirty
                      ? "bg-amber-600 text-white hover:bg-amber-700 shadow-amber-600/20"
                      : "bg-slate-100 text-slate-400 cursor-not-allowed"
                  )}
                >
                  {updateDraft.isPending ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  {dirty ? "Sauvegarder le brouillon" : "Brouillon à jour"}
                </button>
              </>
            )}

            {isSelfReview && isDev && (
              <span className="inline-flex items-center gap-1 rounded-xl border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-800 shadow-xs animate-pulse">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                Auto-validation autorisée (Mode DEV)
              </span>
            )}

            {version?.status === "published" ? (
              <span className="flex items-center gap-1.5 rounded-xl bg-emerald-50 border border-emerald-200 px-3.5 py-2 text-xs font-semibold text-emerald-700 shadow-xs">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Procédure publiée
              </span>
            ) : fourEyesBlocked ? (
              <button
                disabled
                title="Règle des 4 yeux : le relecteur doit être différent du créateur de la procédure."
                className="flex items-center gap-1.5 rounded-xl bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-400 cursor-not-allowed border border-slate-200"
              >
                <ClipboardCheck className="h-4 w-4 text-slate-400" />
                Publier (4 yeux requis)
              </button>
            ) : totalBlockingCount > 0 ? (
              <button
                type="button"
                onClick={() => {
                  setTab("workflow");
                  setBlockingSummaryOpen(true);
                  setTimeout(() => {
                    const el =
                      document.getElementById("blocking-resolution-center") ||
                      document.getElementById("general-clarifications") ||
                      document.getElementById("approval-section");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }, 100);
                }}
                title={`Résolvez les ${totalBlockingCount} point(s) bloquant(s) dans le workflow avant de publier.`}
                className="flex items-center gap-1.5 rounded-xl bg-slate-100 border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-200 hover:text-slate-700 transition cursor-pointer shadow-xs"
              >
                <Lock className="h-3.5 w-3.5 text-slate-400" />
                Publier ({totalBlockingCount} point{totalBlockingCount > 1 ? "s" : ""} à résoudre)
              </button>
            ) : (
              <button
                id="top-approve-publish-btn"
                type="button"
                onClick={() => {
                  if (version?.status === "approved") {
                    window.dispatchEvent(new CustomEvent("open-publish-modal"));
                  } else {
                    window.dispatchEvent(new CustomEvent("open-approval-modal"));
                  }
                }}
                className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-blue-600/25 transition hover:bg-blue-700 cursor-pointer"
              >
                <ClipboardCheck className="h-4 w-4" />
                {version?.status === "approved" ? "Publier la procédure" : "Approuver & Publier"}
              </button>
            )}
          </div>
        </div>

        {/* ── Bandeau compact replié après résolution des clarifications ─── */}
        {openQuestions.length > 0 && unresolvedClarificationsCount === 0 && !blockingSummaryOpen && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50/80 px-4 py-2.5 text-xs text-emerald-950 shadow-2xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>
                <strong>Centre de Résolution HSE :</strong> {openQuestions.length}/{openQuestions.length} clarifications résolues et enregistrées dans le workflow.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setBlockingSummaryOpen(true)}
              className="text-xs font-semibold text-emerald-700 hover:text-emerald-900 underline shrink-0 cursor-pointer"
            >
              Revoir / Modifier les décisions
            </button>
          </div>
        )}

        {/* ── Inline blocking summary panel (Centre de Résolution Direct) ─── */}
        {blockingSummaryOpen && (
          <div
            id="blocking-resolution-center"
            className="mt-4 pt-4 border-t border-rose-200/80 space-y-3.5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rose-100 pb-2.5">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-rose-700" />
                  <h3 className="text-sm font-bold text-rose-950">
                    Centre de Résolution Direct — {openQuestions.length - unresolvedClarificationsCount}/{openQuestions.length} clarifications résolues
                  </h3>
                </div>
                <p className="mt-0.5 text-xs text-rose-800">
                  Ces décisions s'appliquent à l'ensemble du dossier technique (R-01 à R-04). Tranchez-les ici en une seule fois : vos décisions sont répercutées automatiquement sur toutes les actions du Workflow.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {unresolvedClarificationsCount === 0 && (
                  <button
                    type="button"
                    onClick={() => setBlockingSummaryOpen(false)}
                    className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-700 shadow-xs cursor-pointer"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Replier le centre
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setBlockingSummaryOpen(false)}
                  className="rounded p-1 text-rose-400 hover:bg-rose-100 hover:text-rose-700 transition cursor-pointer"
                  title="Fermer le centre de résolution"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {openQuestions.map((q, cIdx) => {
                const qId = String(q.id || cIdx);
                const res = (q.resolution && typeof q.resolution === "object"
                  ? q.resolution
                  : {}) as Record<string, unknown>;
                const isResolved = isClarificationResolved(q);
                const isEditing = editingClarifId === qId;
                const currentAnswer = resolvingAnswers[qId] ?? String(res.answer || "");
                const currentRationale = resolvingRationales[qId] ?? String(res.rationale || "");

                // Calcul Rule ID normalisé
                const relatedComps = Array.isArray(q.related_component_ids)
                  ? (q.related_component_ids as string[]).filter(Boolean)
                  : [];
                let ruleId = "R-0" + (cIdx + 1);
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
                      "rounded-lg border p-3.5 shadow-2xs space-y-2 transition-all",
                      isResolved && !isEditing
                        ? "border-emerald-200 bg-white"
                        : "border-rose-200 bg-white"
                    )}
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-rose-900 bg-rose-100 px-2 py-0.5 rounded">
                          {prefix}
                        </span>
                        <h4 className="font-semibold text-xs text-slate-900">
                          {String(q.question)}
                        </h4>
                      </div>

                      <div className="flex items-center gap-2">
                        {Boolean(sourceDocument?.source_id) && Array.isArray(q.source_pages) && q.source_pages.length > 0 && (
                          <a
                            href={`${env.apiBaseUrl}/v1/generation/documents/${String(sourceDocument?.source_id)}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:underline shrink-0"
                          >
                            <FileText className="h-3 w-3" />
                            Page(s) {q.source_pages.join(", ")}
                          </a>
                        )}

                        {isResolved && !isEditing ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                            Validé
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-800">
                            <AlertCircle className="h-3 w-3 text-rose-600" />
                            Clarification requise
                          </span>
                        )}
                      </div>
                    </div>

                    {whyNeeded && (
                      <p className="text-[11px] text-slate-600 leading-relaxed">
                        <span className="font-medium text-slate-700">Contexte : </span>
                        {whyNeeded}
                      </p>
                    )}

                    {/* État résolu : affichage propre de la décision avec bouton de modification */}
                    {isResolved && !isEditing ? (
                      <div className="flex flex-wrap items-center justify-between gap-2 rounded bg-emerald-50/80 border border-emerald-200 px-3 py-2 text-xs">
                        <div className="space-y-0.5">
                          <p className="text-emerald-900">
                            <span className="font-semibold">Décision HSE validée : </span>
                            <strong>{String(res.answer || "")}</strong>
                          </p>
                          {Boolean(res.rationale) && (
                            <p className="text-[11px] text-emerald-700">
                              <span className="font-medium">Justification : </span>
                              {String(res.rationale)}
                            </p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setResolvingAnswers((prev) => ({ ...prev, [qId]: String(res.answer || "") }));
                            setResolvingRationales((prev) => ({ ...prev, [qId]: String(res.rationale || "") }));
                            setEditingClarifId(qId);
                          }}
                          className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 underline shrink-0 cursor-pointer"
                        >
                          Modifier la décision
                        </button>
                      </div>
                    ) : (
                      /* Mode saisie / édition directe */
                      <div className="space-y-2 pt-1 border-t border-slate-100">
                        <div className="grid gap-2 sm:grid-cols-2">
                          <input
                            type="text"
                            className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-rose-500 focus:ring-1 focus:ring-rose-500"
                            placeholder={getClarificationPlaceholder(String(q.question), ruleId)}
                            value={currentAnswer}
                            onChange={(e) =>
                              setResolvingAnswers((prev) => ({ ...prev, [qId]: e.target.value }))
                            }
                          />
                          <input
                            type="text"
                            className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:border-rose-500 focus:ring-1 focus:ring-rose-500"
                            placeholder="Justification technique HSE (requise)..."
                            value={currentRationale}
                            onChange={(e) =>
                              setResolvingRationales((prev) => ({ ...prev, [qId]: e.target.value }))
                            }
                          />
                        </div>

                        <div className="flex items-center justify-between pt-0.5">
                          {isEditing ? (
                            <button
                              type="button"
                              onClick={() => setEditingClarifId(null)}
                              className="text-[11px] text-slate-500 hover:text-slate-800 underline cursor-pointer"
                            >
                              Annuler la modification
                            </button>
                          ) : null}

                          <Button
                            size="sm"
                            variant="primary"
                            disabled={!currentAnswer.trim() || !currentRationale.trim() || submittingClarifId !== null}
                            onClick={() => handleResolveClarificationCentral(qId)}
                          >
                            {submittingClarifId === qId ? "Application en cours..." : "Appliquer globalement"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {saveError && (
        <div className="flex items-start gap-2.5 rounded-md border border-rose-200 bg-rose-50 px-4 py-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <p className="text-sm text-rose-700">{saveError}</p>
        </div>
      )}

      {/* ── Tab bar (MoveX Segmented Control Pill Tabs) ─────────────── */}
      <div className="inline-flex flex-wrap items-center gap-1.5 rounded-2xl bg-slate-200/50 p-1.5 border border-slate-900/5">
        {TABS.map(({ key, label, Icon }) => {
          const isActive = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={clsx(
                "flex items-center gap-2 px-4 py-2 text-xs font-semibold uppercase tracking-wider rounded-xl transition-all duration-150 cursor-pointer",
                isActive
                  ? "bg-[#0B1120] text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              )}
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={isActive ? 2.5 : 2} />
              {label}
            </button>
          );
        })}
      </div>

      {/* ── Active panel (Direct Bento Canvas - no redundant outer container) ─ */}
      <div className="space-y-6">
        {tab === "workflow"   && <WorkflowReviewPanel  readOnly={!editable} />}
        {tab === "components" && <ComponentReviewPanel readOnly={!editable} />}
        {tab === "vision"     && <VisionPanel          readOnly={!editable} />}
        {tab === "diff"       && (
          <div className="rounded-[20px] border border-slate-900/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all">
            <DiffViewer />
          </div>
        )}
        {tab === "metrics"    && (
          <div className="rounded-[20px] border border-slate-900/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all">
            <ReviewMetricsPanel version={activeVersion} />
          </div>
        )}
        {tab === "audit"      && version && (
          <div className="rounded-[20px] border border-slate-900/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all">
            <AuditHistoryPanel
              procedureVersionId={version.id}
              enabled={tab === "audit"}
            />
          </div>
        )}
      </div>

      {/* ── Approval & Publication workflow ──────────────────────────── */}
      {version && (
        <div id="approval-section" className="rounded-[20px] border border-slate-200/60 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.04)]">
          <ApprovalWorkflow
            procedureId={procedure.id}
            version={version}
            authorId={version.created_by ?? procedure.created_by}
          />
        </div>
      )}

      {/* ── Zone Avancée (Export brut / JSON / Développeur) ──────────── */}
      <details className="group rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
        <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-800 flex items-center justify-between">
          <span>Options avancées (Export brut JSON & Métadonnées)</span>
          <span className="text-[10px] text-slate-400 group-open:rotate-180 transition-transform">▼</span>
        </summary>
        <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div className="text-[11px] text-slate-500 space-y-0.5">
            <p>ID Procédure : <code className="font-mono text-slate-700">{procedure.id}</code></p>
            {version && <p>ID Version : <code className="font-mono text-slate-700">{version.id}</code></p>}
            <p>Source de génération : <span className="font-semibold">{SOURCE_LABELS[version?.generation_source ?? "manual"]}</span></p>
          </div>
          {activeVersion && (
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(activeWorkflow ?? activeVersion, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `procedure-${procedure.machine_id}-v${version?.version_number ?? 1}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              <FileText className="h-3.5 w-3.5 text-slate-500" />
              Télécharger le JSON brut (Debug / Archive)
            </button>
          )}
        </div>
      </details>

      {/* QR Code modal */}
      <QRCodeModal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        machineId={procedure.machine_id}
        machineName={procedure.title}
      />
    </div>
  );
}
