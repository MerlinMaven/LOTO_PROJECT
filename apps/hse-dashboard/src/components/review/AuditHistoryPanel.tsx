import { useAuditEvents } from "@/hooks/useAuditEvents";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/format";
import type { ApiError } from "@/types/api";

const EVENT_LABELS: Record<string, string> = {
  PROCEDURE_CREATED: "Created",
  PROCEDURE_DRAFT_UPDATED: "Draft updated",
  PROCEDURE_APPROVED: "Approved",
  PROCEDURE_REJECTED: "Rejected",
  PROCEDURE_PUBLISHED: "Published",
  PROCEDURE_ARCHIVED: "Archived",
};

interface AuditHistoryPanelProps {
  procedureVersionId: string;
  enabled?: boolean;
}

export function AuditHistoryPanel({
  procedureVersionId,
  enabled = true,
}: AuditHistoryPanelProps) {
  const { data, isLoading, isError, error } = useAuditEvents(
    { procedure_version_id: procedureVersionId, page_size: 50 },
    enabled,
  );

  if (isLoading) return <LoadingPane label="Loading audit events…" />;

  if (isError) {
    return (
      <EmptyState
        title="Could not load audit trail"
        description={(error as ApiError)?.message ?? "Unexpected error."}
      />
    );
  }

  if (!data || data.data.length === 0) {
    return (
      <EmptyState
        title="No audit events"
        description="No events have been recorded for this version yet."
      />
    );
  }

  return (
    <ol className="space-y-1">
      {data.data.map((event) => (
        <li key={event.id} className="surface flex items-start gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-steel-100 px-2 py-0.5 text-xs font-semibold text-steel-700">
                {EVENT_LABELS[event.event_type] ?? event.event_type}
              </span>
              {event.actor_id && (
                <span className="text-xs text-steel-500">
                  by {event.actor_id}
                </span>
              )}
            </div>
            {event.payload && Object.keys(event.payload).length > 0 && (
              <pre className="mt-1.5 overflow-x-auto rounded bg-steel-50 px-2 py-1.5 text-[10px] leading-relaxed text-steel-600">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            )}
          </div>
          <time
            dateTime={event.occurred_at}
            className="shrink-0 text-xs tabular-nums text-steel-400"
          >
            {formatDate(event.occurred_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
