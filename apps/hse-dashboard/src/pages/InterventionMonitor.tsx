import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  listInterventions,
  type InterventionStatus,
  type InterventionSummary,
} from "@/api/interventions";
import { Spinner } from "@/components/ui/Spinner";

const STATUS_LABELS: Record<InterventionStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  paused: "Paused",
  completed: "Completed",
  aborted: "Aborted",
};

const STATUS_CLASSES: Record<InterventionStatus, string> = {
  pending: "bg-steel-100 text-steel-600",
  in_progress: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-emerald-100 text-emerald-700",
  aborted: "bg-red-100 text-red-700",
};

const ALL_STATUSES: (InterventionStatus | "all")[] = [
  "all",
  "in_progress",
  "paused",
  "completed",
  "aborted",
];

function StatusPill({ status }: { status: InterventionStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        STATUS_CLASSES[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div className="surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-steel-500">
        {label}
      </p>
      <p className={clsx("mt-1 text-3xl font-bold", accent ?? "text-steel-800")}>
        {value}
      </p>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function duration(start: string, end: string | null): string {
  if (!end) return "ongoing";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

export function InterventionMonitor() {
  const [statusFilter, setStatusFilter] = useState<InterventionStatus | "all">("all");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["interventions", { status: statusFilter, page }],
    queryFn: () =>
      listInterventions({
        page,
        page_size: pageSize,
        status: statusFilter === "all" ? null : statusFilter,
      }),
    placeholderData: (prev) => prev,
  });

  const interventions = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  // Compute metrics from current page results (approximation for MVP)
  const counts = {
    in_progress: interventions.filter((i) => i.status === "in_progress").length,
    paused: interventions.filter((i) => i.status === "paused").length,
    completed: interventions.filter((i) => i.status === "completed").length,
    aborted: interventions.filter((i) => i.status === "aborted").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-steel-800">
          Intervention Monitor
        </h2>
        <p className="text-sm text-steel-500">
          Real-time view of all LOTO interventions tracked by the Authoring
          Service. Overrides require post-intervention HSE review.
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard label="Total" value={total} />
        <MetricCard
          label="In Progress"
          value={counts.in_progress}
          accent="text-blue-700"
        />
        <MetricCard
          label="Completed"
          value={counts.completed}
          accent="text-emerald-700"
        />
        <MetricCard
          label="Aborted"
          value={counts.aborted}
          accent="text-hazard"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-steel-500">Status:</span>
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => {
              setStatusFilter(s);
              setPage(1);
            }}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-medium transition",
              statusFilter === s
                ? "border-steel-700 bg-steel-700 text-white"
                : "border-steel-200 text-steel-600 hover:border-steel-400",
            )}
          >
            {s === "all" ? "All" : STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="surface overflow-x-auto">
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading interventions…" />
          </div>
        )}

        {isError && (
          <div className="px-6 py-8 text-center text-sm text-hazard">
            {(error as Error)?.message ?? "Failed to load interventions."}
          </div>
        )}

        {!isLoading && !isError && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-steel-200 text-left text-xs font-semibold uppercase tracking-wide text-steel-500">
                <th className="px-4 py-3">Intervention ID</th>
                <th className="px-4 py-3">Machine</th>
                <th className="px-4 py-3">Operator</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Report</th>
              </tr>
            </thead>
            <tbody>
              {interventions.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-12 text-center text-steel-400"
                  >
                    No interventions found.
                  </td>
                </tr>
              ) : (
                interventions.map((row) => (
                  <InterventionRow key={row.id} row={row} />
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-steel-500">
          <span>
            {(page - 1) * pageSize + 1}–
            {Math.min(page * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-steel-200 px-3 py-1 hover:border-steel-400 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-steel-200 px-3 py-1 hover:border-steel-400 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function InterventionRow({ row }: { row: InterventionSummary }) {
  const shortId = row.id.split("-")[0];
  const end = row.completed_at ?? row.aborted_at;

  return (
    <tr className="border-b border-steel-100 transition hover:bg-steel-50">
      <td className="px-4 py-3 font-mono text-xs text-steel-500">{shortId}…</td>
      <td className="px-4 py-3 font-medium text-steel-800">
        <span
          className="block max-w-[140px] truncate"
          title={row.machine_id}
        >
          {row.machine_id}
        </span>
      </td>
      <td className="px-4 py-3 text-steel-600">{row.operator_name}</td>
      <td className="px-4 py-3">
        <StatusPill status={row.status} />
      </td>
      <td className="px-4 py-3 text-steel-500">{formatDate(row.started_at)}</td>
      <td className="px-4 py-3 text-steel-500">
        {duration(row.started_at, end)}
      </td>
      <td className="px-4 py-3">
        {row.pdf_report_url ? (
          <a
            href={row.pdf_report_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-steel-600 underline hover:text-steel-800"
          >
            PDF
          </a>
        ) : (
          <span className="text-xs text-steel-300">—</span>
        )}
      </td>
    </tr>
  );
}
