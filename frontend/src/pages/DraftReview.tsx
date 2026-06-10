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

type TabKey =
  | "components"
  | "workflow"
  | "vision"
  | "diff"
  | "metrics"
  | "audit";

const TABS: { key: TabKey; label: string }[] = [
  { key: "components", label: "Components" },
  { key: "workflow", label: "Workflow" },
  { key: "vision", label: "Vision" },
  { key: "diff", label: "Diff" },
  { key: "metrics", label: "Metrics" },
  { key: "audit", label: "Audit" },
];

export function DraftReview() {
  const { procedureId } = useParams<{ procedureId: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("components");
  const [saveError, setSaveError] = useState<string | null>(null);

  const {
    data: procedure,
    isLoading,
    isError,
    error,
  } = useProcedure(procedureId);
  const reviewerId = useAuthStore((s) => s.reviewerId);

  const load = useReviewStore((s) => s.load);
  const reset = useReviewStore((s) => s.reset);
  const commitSaved = useReviewStore((s) => s.commitSaved);
  const isDirty = useReviewStore((s) => s.isDirty);
  const draft = useReviewStore((s) => s.draft);

  const version = procedure?.active_version ?? null;
  const editable = version ? isEditable(version.status) : false;

  // Populate the store whenever the server version changes.
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

  const dirty = isDirty();
  const activeVersion = useMemo(
    () => procedure?.active_version ?? null,
    [procedure],
  );

  // ── Loading / error states ────────────────────────────────────────────────

  if (isLoading) return <LoadingPane label="Loading procedure…" />;

  if (isError || !procedure) {
    return (
      <EmptyState
        title="Procedure not found"
        description={
          (error as ApiError)?.message ?? "Could not load this procedure."
        }
        action={
          <Button variant="secondary" onClick={() => navigate("/procedures")}>
            Back to list
          </Button>
        }
      />
    );
  }

  // ── Page ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <button
            onClick={() => navigate("/procedures")}
            className="mb-1 text-xs text-steel-500 hover:text-steel-700"
          >
            ← Procedures
          </button>
          <h2 className="text-lg font-semibold text-steel-800">
            {procedure.title}
          </h2>
          <div className="mt-0.5 flex flex-wrap gap-3 text-xs text-steel-500">
            <span>
              Machine:{" "}
              <code className="text-[11px]">{procedure.machine_id}</code>
            </span>
            <span>Author: {version?.created_by ?? procedure.created_by}</span>
            {version && (
              <span>Source: {SOURCE_LABELS[version.generation_source]}</span>
            )}
            {version && <span>Updated: {formatDate(version.updated_at)}</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {version && <StatusBadge status={version.status} />}
          {version && (
            <span className="rounded bg-steel-100 px-2 py-0.5 text-xs font-semibold text-steel-600">
              v{version.version_number}
            </span>
          )}
        </div>
      </div>

      {/* Save bar — only visible for editable drafts with unsaved changes */}
      {editable && dirty && (
        <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5">
          <span className="text-sm font-medium text-draft">
            Unsaved changes
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={reset}
              disabled={updateDraft.isPending}
            >
              Discard
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              loading={updateDraft.isPending}
            >
              Save draft
            </Button>
          </div>
        </div>
      )}

      {saveError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-hazard">
          {saveError}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 border-b border-steel-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={clsx(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition",
              tab === t.key
                ? "border-steel-700 text-steel-800"
                : "border-transparent text-steel-500 hover:text-steel-700",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Active panel */}
      <div className="min-h-[200px]">
        {tab === "components" && (
          <ComponentReviewPanel readOnly={!editable} />
        )}
        {tab === "workflow" && <WorkflowReviewPanel readOnly={!editable} />}
        {tab === "vision" && <VisionPromptPanel readOnly={!editable} />}
        {tab === "diff" && <DiffViewer />}
        {tab === "metrics" && <ReviewMetricsPanel version={activeVersion} />}
        {tab === "audit" && version && (
          <AuditHistoryPanel
            procedureVersionId={version.id}
            enabled={tab === "audit"}
          />
        )}
      </div>

      {/* Approval workflow — below the panels so the reviewer finishes reviewing first */}
      {version && (
        <ApprovalWorkflow
          procedureId={procedure.id}
          version={version}
          authorId={version.created_by ?? procedure.created_by}
        />
      )}
    </div>
  );
}
