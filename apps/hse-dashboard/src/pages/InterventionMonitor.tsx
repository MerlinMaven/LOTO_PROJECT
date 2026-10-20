import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  listInterventions,
  type InterventionStatus,
  type InterventionSummary,
} from "@/api/interventions";
import { LoadingPane } from "@/components/ui/Spinner";
import {
  Activity,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

const STATUS_LABELS: Record<InterventionStatus, string> = {
  pending:     "En attente",
  in_progress: "En cours",
  paused:      "En pause",
  completed:   "Terminé",
  aborted:     "Annulé",
};

const STATUS_STYLES: Record<
  InterventionStatus,
  { dot: string; badge: string }
> = {
  pending:     { dot: "bg-slate-400",  badge: "border-slate-200 bg-slate-50  text-slate-600" },
  in_progress: { dot: "bg-blue-500",   badge: "border-blue-200  bg-blue-50   text-blue-700"  },
  paused:      { dot: "bg-amber-400",  badge: "border-amber-200 bg-amber-50  text-amber-700" },
  completed:   { dot: "bg-emerald-500",badge: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  aborted:     { dot: "bg-rose-500",   badge: "border-rose-200  bg-rose-50   text-rose-700"  },
};

const ALL_STATUSES: (InterventionStatus | "all")[] = [
  "all",
  "in_progress",
  "paused",
  "completed",
  "aborted",
];

function StatusPill({ status }: { status: InterventionStatus }) {
  const s = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-semibold", s.badge)}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {STATUS_LABELS[status]}
    </span>
  );
}

function MetricCard({
  label,
  value,
  accentClass = "text-slate-900",
}: {
  label: string;
  value: number;
  accentClass?: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={clsx("mt-1.5 text-2xl font-bold tabular-nums", accentClass)}>{value}</p>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function duration(start: string, end: string | null): string {
  if (!end) return "en cours";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return `${mins} min`;
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

  const counts = {
    in_progress: interventions.filter((i) => i.status === "in_progress").length,
    paused:      interventions.filter((i) => i.status === "paused").length,
    completed:   interventions.filter((i) => i.status === "completed").length,
    aborted:     interventions.filter((i) => i.status === "aborted").length,
  };

  return (
    <div className="space-y-5">

      {/* ── Page header ───────────────────────────────────────────────── */}
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white shadow-sm">
          <Activity className="h-[18px] w-[18px] text-slate-600" strokeWidth={2} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Moniteur d'interventions
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Vue en temps réel de toutes les interventions LOTO suivies par l'Authoring Service.
            Les dérogations nécessitent une revue HSE post-intervention.
          </p>
        </div>
      </div>

      {/* ── Metric cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Total" value={total} />
        <MetricCard label="En cours" value={counts.in_progress} accentClass="text-blue-700" />
        <MetricCard label="Terminés" value={counts.completed} accentClass="text-emerald-700" />
        <MetricCard label="Annulés" value={counts.aborted} accentClass="text-rose-700" />
      </div>

      {/* ── Status filter ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-0 border-b border-slate-200">
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide transition-all duration-150",
              statusFilter === s
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-400 hover:border-slate-300 hover:text-slate-600",
            )}
          >
            {s === "all" ? "Toutes" : STATUS_LABELS[s as InterventionStatus]}
          </button>
        ))}
      </div>

      {/* ── Table ────────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm">
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <LoadingPane label="Chargement des interventions…" />
          </div>
        )}

        {isError && (
          <div className="flex items-start gap-3 px-6 py-8">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-sm text-rose-700">
              {(error as Error)?.message ?? "Impossible de charger les interventions."}
            </p>
          </div>
        )}

        {!isLoading && !isError && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                {["ID Intervention", "Machine", "Opérateur", "Statut", "Démarrée", "Durée", "Rapport"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {interventions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-400">
                    Aucune intervention trouvée.
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

      {/* ── Pagination ───────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span className="tabular-nums">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} sur {total}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="flex items-center gap-1 rounded border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-600 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-3 w-3" />
              Préc.
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="flex items-center gap-1 rounded border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-600 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Suiv.
              <ChevronRight className="h-3 w-3" />
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
    <tr className="group transition-colors duration-100 hover:bg-slate-50">
      <td className="px-4 py-3">
        <code className="font-mono text-[11px] text-slate-400 group-hover:text-slate-600">
          {shortId}…
        </code>
      </td>
      <td className="px-4 py-3">
        <span
          className="block max-w-[140px] truncate font-mono text-xs font-semibold text-slate-700"
          title={row.machine_id}
        >
          {row.machine_id}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-slate-600">{row.operator_name}</td>
      <td className="px-4 py-3">
        <StatusPill status={row.status} />
      </td>
      <td className="px-4 py-3 text-[11px] tabular-nums text-slate-500">
        {formatDate(row.started_at)}
      </td>
      <td className="px-4 py-3 text-[11px] tabular-nums text-slate-500">
        {duration(row.started_at, end)}
      </td>
      <td className="px-4 py-3">
        {row.pdf_report_url ? (
          <a
            href={row.pdf_report_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 transition-colors hover:text-blue-800"
          >
            PDF
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : (
          <span className="text-xs text-slate-300">—</span>
        )}
      </td>
    </tr>
  );
}
