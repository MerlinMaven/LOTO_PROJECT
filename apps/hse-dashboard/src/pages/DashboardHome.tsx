import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import { useProcedureList, useArchiveProcedure } from "@/hooks/useProcedures";
import type { ProcedureListItem, ProcedureStatus } from "@/types/procedure";
import { ALL_STATUSES, STATUS_SHORT, SOURCE_LABELS } from "@/lib/status";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { QRCodeModal } from "@/components/ui/QRCodeModal";
import { Button } from "@/components/ui/Button";
import { formatRelative } from "@/lib/format";
import type { ApiError } from "@/types/api";
import { Search, QrCode, Archive, ClipboardList, AlertCircle } from "lucide-react";

type Tab = "all" | ProcedureStatus;

const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "Toutes" },
  ...ALL_STATUSES.map((s) => ({ key: s as Tab, label: STATUS_SHORT[s] })),
];

/** Canonical display label: [machine_id] - [title] (Fait par : [author]) */
function procedureLabel(p: ProcedureListItem): string {
  return `${p.machine_id} - ${p.title} (Fait par : ${p.created_by})`;
}

export function DashboardHome() {
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<ProcedureListItem | null>(null);
  const [qrTarget, setQrTarget] = useState<ProcedureListItem | null>(null);

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
  const archiveMutation = useArchiveProcedure();
  const navigate = useNavigate();

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    await archiveMutation.mutateAsync(deleteTarget.id);
    setDeleteTarget(null);
  };

  return (
    <div className="space-y-5">

      {/* ── Page header ───────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white shadow-sm">
            <ClipboardList className="h-4.5 w-4.5 h-[18px] w-[18px] text-slate-600" strokeWidth={2} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Procédures LOTO</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Revue, édition et approbation des procédures générées par IA.
              Aucune procédure n'est activée sans validation humaine.
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher par titre…"
            aria-label="Rechercher une procédure"
            className="w-full rounded-md border border-slate-300 bg-white py-2 pl-8 pr-3 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-0 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide transition-all duration-150",
              tab === t.key
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-400 hover:border-slate-300 hover:text-slate-600",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── States ───────────────────────────────────────────────────── */}
      {isLoading && <LoadingPane label="Chargement des procédures…" />}

      {isError && (
        <div className="flex items-start gap-3 rounded-md border border-rose-200 bg-rose-50 px-4 py-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <div>
            <p className="text-sm font-semibold text-rose-700">Impossible de charger les procédures</p>
            <p className="text-xs text-rose-600">
              {(error as ApiError)?.message ?? "Erreur inattendue."}
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && data && data.data.length === 0 && (
        <EmptyState
          title="Aucune procédure ici"
          description={
            tab === "all"
              ? "Les procédures générées apparaîtront ici après publication."
              : `Aucune procédure avec le statut "${STATUS_SHORT[tab as ProcedureStatus]}".`
          }
        />
      )}

      {/* ── Table ────────────────────────────────────────────────────── */}
      {!isLoading && !isError && data && data.data.length > 0 && (
        <div className="overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Procédure
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Statut
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Source
                </th>
                <th className="w-36 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Confiance
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Erreurs
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Mis à jour
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.data.map((p) => (
                <tr
                  key={p.id}
                  className="group transition-colors duration-100 hover:bg-slate-50"
                >
                  {/* Procedure identity — click to open */}
                  <td
                    className="cursor-pointer px-4 py-3"
                    onClick={() => navigate(`/procedures/${p.id}`)}
                  >
                    <div className="font-medium text-slate-800 group-hover:text-blue-700 transition-colors">
                      <span className="font-mono text-xs font-semibold text-blue-600">
                        {p.machine_id}
                      </span>
                      <span className="mx-1.5 text-slate-300">·</span>
                      <span className="text-slate-700">{p.title}</span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-400">
                      Version {p.current_version_number}{" "}
                      <span className="text-slate-300">(Fait par :{" "}
                        <span className="font-medium text-slate-500">{p.created_by}</span>)
                      </span>
                    </div>
                  </td>

                  <td className="px-4 py-3">
                    <StatusBadge status={p.current_status} />
                  </td>

                  <td className="px-4 py-3 text-xs text-slate-500">
                    {SOURCE_LABELS[p.generation_source]}
                  </td>

                  <td className="px-4 py-3">
                    <ConfidenceBar value={p.overall_confidence} label="" />
                  </td>

                  <td className="px-4 py-3">
                    {p.open_validation_errors > 0 ? (
                      <span className="inline-flex items-center gap-1 rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700">
                        <AlertCircle className="h-3 w-3" />
                        {p.open_validation_errors} erreur{p.open_validation_errors > 1 ? "s" : ""}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-300">—</span>
                    )}
                  </td>

                  <td className="px-4 py-3 text-[11px] tabular-nums text-slate-400">
                    {formatRelative(p.updated_at)}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        title="Afficher le QR Code"
                        onClick={(e) => { e.stopPropagation(); setQrTarget(p); }}
                        className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 shadow-sm transition-all duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                      >
                        <QrCode className="h-3 w-3" />
                        QR
                      </button>

                      {p.current_status !== "archived" && (
                        <button
                          title="Archiver (soft delete)"
                          onClick={(e) => { e.stopPropagation(); setDeleteTarget(p); }}
                          className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-500 shadow-sm transition-all duration-150 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700"
                        >
                          <Archive className="h-3 w-3" />
                          Archiver
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Row count */}
      {data && data.total > 0 && (
        <p className="text-[11px] tabular-nums text-slate-400">
          {data.data.length} sur {data.total} procédure{data.total > 1 ? "s" : ""}
        </p>
      )}

      {/* ── Modals ────────────────────────────────────────────────────── */}
      <ConfirmModal
        open={deleteTarget !== null}
        title="Archiver la procédure ?"
        message={
          deleteTarget
            ? `La procédure « ${procedureLabel(deleteTarget)} » sera archivée. Elle disparaîtra des vues actives mais reste conservée pour la conformité HSE (OSHA 1910.147). Cette action est irréversible depuis l'interface.`
            : ""
        }
        confirmLabel="Oui, archiver"
        onConfirm={handleConfirmDelete}
        onClose={() => setDeleteTarget(null)}
        loading={archiveMutation.isPending}
      />

      {qrTarget && (
        <QRCodeModal
          open={qrTarget !== null}
          onClose={() => setQrTarget(null)}
          machineId={qrTarget.machine_id}
          machineName={qrTarget.title}
        />
      )}
    </div>
  );
}
