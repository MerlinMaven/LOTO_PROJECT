import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { clsx } from "clsx";
import { useProcedure, useUpdateDraft } from "@/hooks/useProcedures";
import { useReviewStore } from "@/store/reviewStore";
import { useAuthStore } from "@/store/authStore";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { QRCodeModal } from "@/components/ui/QRCodeModal";
import { ComponentReviewPanel } from "@/components/review/ComponentReviewPanel";
import { WorkflowReviewPanel } from "@/components/review/WorkflowReviewPanel";
import { VisionPromptPanel } from "@/components/review/VisionPromptPanel";
import { DiffViewer } from "@/components/review/DiffViewer";
import { ReviewMetricsPanel } from "@/components/review/ReviewMetricsPanel";
import { AuditHistoryPanel } from "@/components/review/AuditHistoryPanel";
import { ApprovalWorkflow } from "@/components/review/ApprovalWorkflow";
import { SOURCE_LABELS, isEditable } from "@/lib/status";
import { formatDate } from "@/lib/format";
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
  LucideIcon,
} from "lucide-react";

type TabKey =
  | "components"
  | "workflow"
  | "vision"
  | "diff"
  | "metrics"
  | "audit";

const TABS: { key: TabKey; label: string; Icon: LucideIcon }[] = [
  { key: "components", label: "Composants",  Icon: Cpu },
  { key: "workflow",   label: "Workflow",    Icon: GitBranch },
  { key: "vision",     label: "Vision",      Icon: Eye },
  { key: "diff",       label: "Diff",        Icon: GitCompare },
  { key: "metrics",    label: "Métriques",   Icon: BarChart2 },
  { key: "audit",      label: "Audit",       Icon: ClipboardCheck },
];

export function DraftReview() {
  const { procedureId } = useParams<{ procedureId: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("components");
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

  const version  = procedure?.active_version ?? null;
  const editable = version ? isEditable(version.status) : false;

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
    } catch (err) {
      setSaveError((err as ApiError).message ?? "Save failed.");
    }
  };

  const dirty         = isDirty();
  const activeVersion = useMemo(() => procedure?.active_version ?? null, [procedure]);

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

      {/* ── Breadcrumb + header ─────────────────────────────────────── */}
      <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        {/* Breadcrumb */}
        <button
          onClick={() => navigate("/procedures")}
          className="mb-3 flex items-center gap-1.5 text-[11px] font-medium text-slate-400 transition-colors hover:text-slate-700"
        >
          <ArrowLeft className="h-3 w-3" />
          Procédures
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          {/* Title block */}
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              {procedure.title}
            </h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-1 text-[11px] text-slate-500">
                <span className="font-medium text-slate-400">Machine</span>
                <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-700">
                  {procedure.machine_id}
                </code>
              </span>
              {version && (
                <>
                  <span className="h-3 w-px bg-slate-200" />
                  <span className="text-[11px] text-slate-500">
                    <span className="text-slate-400">Auteur :</span>{" "}
                    <span className="font-medium text-slate-600">{version.created_by ?? procedure.created_by}</span>
                  </span>
                  <span className="h-3 w-px bg-slate-200" />
                  <span className="text-[11px] text-slate-500">
                    <span className="text-slate-400">Source :</span>{" "}
                    {SOURCE_LABELS[version.generation_source]}
                  </span>
                  <span className="h-3 w-px bg-slate-200" />
                  <span className="text-[11px] text-slate-400">
                    Mis à jour : {formatDate(version.updated_at)}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Right badges + QR */}
          <div className="flex shrink-0 items-center gap-2">
            {version && <StatusBadge status={version.status} />}
            {version && (
              <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600">
                v{version.version_number}
              </span>
            )}
            <button
              onClick={() => setQrOpen(true)}
              title="Afficher le QR Code machine"
              className="flex items-center gap-1.5 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-slate-600 shadow-sm transition-all duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
            >
              <QrCode className="h-3.5 w-3.5" />
              QR Code
            </button>
          </div>
        </div>
      </div>

      {/* ── Unsaved-changes banner ──────────────────────────────────── */}
      {editable && dirty && (
        <div className="flex items-center justify-between rounded-md border border-amber-200 bg-amber-50 px-4 py-2.5 shadow-sm">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-semibold text-amber-700">
              Modifications non sauvegardées
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={reset}
              disabled={updateDraft.isPending}
              className="flex items-center gap-1.5 rounded border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 transition-all hover:bg-amber-100 disabled:opacity-50"
            >
              <RotateCcw className="h-3 w-3" />
              Annuler
            </button>
            <button
              onClick={handleSave}
              disabled={updateDraft.isPending}
              className="flex items-center gap-1.5 rounded bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-amber-700 disabled:opacity-50"
            >
              {updateDraft.isPending ? (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              Sauvegarder
            </button>
          </div>
        </div>
      )}

      {saveError && (
        <div className="flex items-start gap-2.5 rounded-md border border-rose-200 bg-rose-50 px-4 py-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <p className="text-sm text-rose-700">{saveError}</p>
        </div>
      )}

      {/* ── Tab bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-0 border-b border-slate-200">
        {TABS.map(({ key, label, Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={clsx(
              "-mb-px flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide transition-all duration-150",
              tab === key
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-400 hover:border-slate-300 hover:text-slate-600",
            )}
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={tab === key ? 2.5 : 2} />
            {label}
          </button>
        ))}
      </div>

      {/* ── Active panel ─────────────────────────────────────────────── */}
      <div className="min-h-[200px] rounded-md border border-slate-200 bg-white shadow-sm">
        <div className="p-1">
          {tab === "components" && <ComponentReviewPanel readOnly={!editable} />}
          {tab === "workflow"   && <WorkflowReviewPanel  readOnly={!editable} />}
          {tab === "vision"     && <VisionPromptPanel    readOnly={!editable} />}
          {tab === "diff"       && <DiffViewer />}
          {tab === "metrics"    && <ReviewMetricsPanel   version={activeVersion} />}
          {tab === "audit"      && version && (
            <AuditHistoryPanel
              procedureVersionId={version.id}
              enabled={tab === "audit"}
            />
          )}
        </div>
      </div>

      {/* ── Approval workflow ────────────────────────────────────────── */}
      {version && (
        <div className="rounded-md border border-slate-200 bg-white shadow-sm">
          <ApprovalWorkflow
            procedureId={procedure.id}
            version={version}
            authorId={version.created_by ?? procedure.created_by}
          />
        </div>
      )}

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
