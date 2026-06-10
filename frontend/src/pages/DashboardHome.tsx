import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import { useProcedureList } from "@/hooks/useProcedures";
import type { ProcedureStatus } from "@/types/procedure";
import { ALL_STATUSES, STATUS_SHORT, SOURCE_LABELS } from "@/lib/status";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { formatRelative } from "@/lib/format";
import type { ApiError } from "@/types/api";

type Tab = "all" | ProcedureStatus;

const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "All" },
  ...ALL_STATUSES.map((s) => ({ key: s as Tab, label: STATUS_SHORT[s] })),
];

export function DashboardHome() {
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");

  const params = useMemo(
    () => ({
      status: tab === "all" ? undefined : tab,
      search: search.trim() || undefined,
      page: 1,
      page_size: 50,
    }),
    [tab, search],
  );

  const { data, isLoading, isError, error } = useProcedureList(params);
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-steel-800">Procedures</h2>
          <p className="text-sm text-steel-500">
            Review, edit, and approve AI-generated LOTO procedures. No procedure
            becomes trusted without human sign-off.
          </p>
        </div>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title…"
          className="field-input w-full max-w-xs"
          aria-label="Search procedures"
        />
      </div>

      {/* Tabs */}
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

      {/* Content */}
      {isLoading && <LoadingPane label="Loading procedures…" />}

      {isError && (
        <EmptyState
          title="Could not load procedures"
          description={(error as ApiError)?.message ?? "Unexpected error."}
        />
      )}

      {!isLoading && !isError && data && data.data.length === 0 && (
        <EmptyState
          title="No procedures here yet"
          description={
            tab === "all"
              ? "Generated drafts will appear here once the Generation Factory publishes them."
              : `No procedures with status "${STATUS_SHORT[tab as ProcedureStatus]}".`
          }
        />
      )}

      {!isLoading && !isError && data && data.data.length > 0 && (
        <div className="surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-steel-50 text-left text-xs uppercase tracking-wide text-steel-500">
              <tr>
                <th className="px-4 py-2 font-semibold">Procedure</th>
                <th className="px-4 py-2 font-semibold">Status</th>
                <th className="px-4 py-2 font-semibold">Source</th>
                <th className="px-4 py-2 font-semibold w-48">Confidence</th>
                <th className="px-4 py-2 font-semibold">Issues</th>
                <th className="px-4 py-2 font-semibold">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-steel-100">
              {data.data.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/procedures/${p.id}`)}
                  className="cursor-pointer transition hover:bg-steel-50"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-steel-800">{p.title}</div>
                    <div className="text-xs text-steel-400">
                      v{p.current_version_number} · {p.created_by}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={p.current_status} />
                  </td>
                  <td className="px-4 py-3 text-steel-600">
                    {SOURCE_LABELS[p.generation_source]}
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBar value={p.overall_confidence} label="" />
                  </td>
                  <td className="px-4 py-3">
                    {p.open_validation_errors > 0 ? (
                      <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-hazard">
                        {p.open_validation_errors} error
                        {p.open_validation_errors > 1 ? "s" : ""}
                      </span>
                    ) : (
                      <span className="text-xs text-steel-400">none</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-steel-500">
                    {formatRelative(p.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > 0 && (
        <p className="text-xs text-steel-400">
          {data.data.length} of {data.total} procedure
          {data.total > 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
