import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import { useProcedureList, useArchiveProcedure } from "@/hooks/useProcedures";
import { useSearchStore } from "@/store/searchStore";
import type { ProcedureListItem, ProcedureStatus } from "@/types/procedure";
import { ALL_STATUSES, STATUS_SHORT, SOURCE_LABELS, normalizeStatus } from "@/lib/status";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { QRCodeModal } from "@/components/ui/QRCodeModal";
import { formatRelative } from "@/lib/format";
import { calculateConfidenceBreakdown, getBusinessBlockingCount } from "@/lib/kpi";
import type { ApiError } from "@/types/api";
import {
  QrCode,
  Archive,
  ClipboardList,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Zap,
} from "lucide-react";

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
  const search = useSearchStore((s) => s.searchQuery);

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

  const procedures = data?.data ?? [];
  const totalCount = data?.total ?? procedures.length;

  // Track all procedures when unfiltered to preserve tab counts & global KPIs
  const [allKnownProcedures, setAllKnownProcedures] = useState<ProcedureListItem[]>([]);

  useEffect(() => {
    if (data?.data && tab === "all") {
      setAllKnownProcedures(data.data);
    }
  }, [data?.data, tab]);

  const baseForCounts = tab === "all" ? procedures : (allKnownProcedures.length ? allKnownProcedures : procedures);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: baseForCounts.length,
    };
    ALL_STATUSES.forEach((s) => {
      counts[s] = baseForCounts.filter((p) => {
        const norm = normalizeStatus(p.current_status);
        return norm === s;
      }).length;
    });
    return counts;
  }, [baseForCounts]);

  // Calcul dynamique des 4 KPI Bento MoveX
  const kpis = useMemo(() => {
    const list = baseForCounts.length ? baseForCounts : procedures;
    if (!list.length) {
      return { total: 0, avgConfidence: 0, blockingCount: 0, readyCount: 0, readyPct: 0 };
    }
    const total = totalCount || list.length;
    let sumConf = 0;
    let sumBlocking = 0;
    let readyCount = 0;

    list.forEach((p) => {
      const confData = calculateConfidenceBreakdown(p.workflow_definition);
      const confScore = confData ? confData.score : (p.overall_confidence ? Math.round(p.overall_confidence * 100) : 75);
      sumConf += confScore;
      sumBlocking += getBusinessBlockingCount(p);
      const norm = normalizeStatus(p.current_status);
      if (norm === "published" || norm === "approved") {
        readyCount += 1;
      }
    });

    const avgConfidence = Math.round(sumConf / list.length);
    const readyPct = Math.round((readyCount / list.length) * 100);

    return { total, avgConfidence, blockingCount: sumBlocking, readyCount, readyPct };
  }, [baseForCounts, procedures, totalCount]);

  return (
    <div className="space-y-6">

      {/* ── Page Header (Search unified in Topbar + Action rapide) ────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Procédures de Consignation LOTO
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Cockpit de contrôle HSE : revue, validation des signatures physiques et approbation OSHA 1910.147.
          </p>
        </div>

        <button
          onClick={() => navigate("/generate")}
          className="inline-flex items-center gap-2 rounded-xl bg-[#0B1120] hover:bg-blue-600 text-white text-xs font-semibold px-4 py-2.5 shadow-sm transition-colors cursor-pointer"
        >
          <Zap className="h-4 w-4 text-blue-400" />
          Nouvelle analyse PDF
        </button>
      </div>

      {/* ── 4 Bento KPI Cards Grid (Bordures ciselées & accents) ────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 : Procédures Totales */}
        <div className="bg-white rounded-[20px] border border-slate-900/10 border-t-2 border-t-blue-600 p-5 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all relative overflow-hidden group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Procédures Totales
            </span>
            <div className="h-9 w-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-2xs group-hover:bg-blue-600 group-hover:text-white transition-all">
              <ClipboardList className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
              {kpis.total}
            </span>
            <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
              <TrendingUp className="h-3 w-3" />
              Actives
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Dossiers techniques enregistrés
          </p>
        </div>

        {/* KPI 2 : Confiance IA Moyenne */}
        <div className="bg-white rounded-[20px] border border-slate-900/10 border-t-2 border-t-emerald-500 p-5 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all relative overflow-hidden group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Confiance IA Moyenne
            </span>
            <div className="h-9 w-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-2xs group-hover:bg-emerald-600 group-hover:text-white transition-all">
              <ShieldCheck className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
              {kpis.avgConfidence}%
            </span>
            <span className="text-[11px] font-medium text-slate-400">
              Score composite
            </span>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-500"
              style={{ width: `${kpis.avgConfidence}%` }}
            />
          </div>
        </div>

        {/* KPI 3 : Points Bloquants Actifs */}
        <div className="bg-white rounded-[20px] border border-slate-900/10 border-t-2 border-t-rose-500 p-5 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all relative overflow-hidden group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Points Bloquants
            </span>
            <div className="h-9 w-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shadow-2xs group-hover:bg-rose-600 group-hover:text-white transition-all">
              <AlertTriangle className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
              {kpis.blockingCount}
            </span>
            {kpis.blockingCount > 0 ? (
              <span className="text-[11px] font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">
                À trancher HSE
              </span>
            ) : (
              <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                ✓ 0 bloquant
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Clarifications OSHA avant approbation
          </p>
        </div>

        {/* KPI 4 : Prêtes pour Casque AR */}
        <div className="bg-white rounded-[20px] border border-slate-900/10 border-t-2 border-t-indigo-600 p-5 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all relative overflow-hidden group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Prêtes pour Casque AR
            </span>
            <div className="h-9 w-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-2xs group-hover:bg-indigo-600 group-hover:text-white transition-all">
              <CheckCircle2 className="h-4.5 w-4.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
              {kpis.readyPct}%
            </span>
            <span className="text-[11px] font-medium text-slate-400">
              ({kpis.readyCount}/{kpis.total || 1})
            </span>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-600 transition-all duration-500"
              style={{ width: `${kpis.readyPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* ── Segmented Control Filter Tabs with Count Micro-Pills ──── */}
      <div className="inline-flex flex-wrap items-center gap-1.5 rounded-2xl bg-slate-200/50 p-1.5 border border-slate-900/5">
        {TABS.map((t) => {
          const isSelected = tab === t.key;
          const count = tabCounts[t.key] ?? 0;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                "inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all duration-150 cursor-pointer",
                isSelected
                  ? "bg-[#0B1120] text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60",
              )}
            >
              <span>{t.label}</span>
              <span
                className={clsx(
                  "inline-flex items-center justify-center min-w-[18px] h-4.5 px-1.5 rounded-full text-[10px] font-bold transition-colors",
                  isSelected
                    ? "bg-blue-600 text-white"
                    : "bg-slate-300/80 text-slate-700",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── States ───────────────────────────────────────────────────── */}
      {isLoading && <LoadingPane label="Chargement des procédures…" />}

      {isError && (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 shadow-sm">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <div>
            <p className="text-sm font-semibold text-rose-800">Impossible de charger les procédures</p>
            <p className="text-xs text-rose-600 mt-0.5">
              {(error as ApiError)?.message ?? "Erreur inattendue."}
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && data && data.data.length === 0 && (
        <EmptyState
          title="Aucune procédure trouvée"
          description={
            tab === "all"
              ? "Les procédures générées apparaîtront ici après publication."
              : `Aucune procédure avec le statut "${STATUS_SHORT[tab as ProcedureStatus]}".`
          }
        />
      )}

      {/* ── Bento Table (Airy Rows, Clean Lines, Soft-Pill Badges) ──── */}
      {!isLoading && !isError && data && data.data.length > 0 && (
        <div className="bg-white rounded-[20px] border border-slate-900/10 shadow-[0_4px_20px_-4px_rgba(11,17,32,0.06)] hover:border-slate-900/20 transition-all overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-900/10 bg-slate-900/[0.025] text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  <th className="px-5 py-3.5 text-left">
                    Procédure
                  </th>
                  <th className="px-5 py-3.5 text-left">
                    Statut
                  </th>
                  <th className="px-5 py-3.5 text-left">
                    Source
                  </th>
                  <th className="w-40 px-5 py-3.5 text-left">
                    Confiance IA
                  </th>
                  <th className="px-5 py-3.5 text-left">
                    Points bloquants
                  </th>
                  <th className="px-5 py-3.5 text-left">
                    Mis à jour
                  </th>
                  <th className="px-5 py-3.5 text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/90 font-sans">
                {data.data.map((p) => {
                  const blockingCount = getBusinessBlockingCount(p);
                  const confidenceData = calculateConfidenceBreakdown(p.workflow_definition);
                  const confidence = confidenceData ? confidenceData.score / 100 : (p.overall_confidence ?? null);
                  const breakdown = confidenceData?.breakdown ?? null;
                  return (
                    <tr
                      key={p.id}
                      className="group transition-colors duration-150 hover:bg-slate-50/80 cursor-pointer"
                      onClick={() => navigate(`/procedures/${p.id}`)}
                    >
                      {/* Identity */}
                      <td className="px-5 py-4">
                        <div className="font-semibold text-slate-900">
                          <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-100 mr-2">
                            {p.machine_id}
                          </span>
                          <span className="group-hover:text-blue-600 transition-colors font-semibold">{p.title}</span>
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400">
                          Version {p.current_version_number}{" "}
                          <span className="text-slate-300">·</span> Fait par{" "}
                          <span className="font-medium text-slate-600">{p.created_by}</span>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-5 py-4">
                        <StatusBadge status={p.current_status} />
                      </td>

                      {/* Source */}
                      <td className="px-5 py-4 text-xs text-slate-500">
                        <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600 border border-slate-200/60">
                          {SOURCE_LABELS[p.generation_source]}
                        </span>
                      </td>

                      {/* Confiance */}
                      <td className="px-5 py-4" onClick={(e) => e.stopPropagation()}>
                        <ConfidenceBar value={confidence} label="" breakdown={breakdown} />
                      </td>

                      {/* Points bloquants (Soft-Pill) */}
                      <td className="px-5 py-4">
                        {blockingCount > 0 ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-200/80 bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 shadow-2xs">
                            <AlertCircle className="h-3 w-3 text-rose-600" />
                            {blockingCount} point{blockingCount > 1 ? "s" : ""} bloquant{blockingCount > 1 ? "s" : ""}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200/80 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 shadow-2xs">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                            Conforme
                          </span>
                        )}
                      </td>

                      {/* Mis à jour */}
                      <td className="px-5 py-4 text-[11px] tabular-nums text-slate-400">
                        {formatRelative(p.updated_at)}
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5">
                          {p.current_status === "published" && (
                            <button
                              title="Afficher le QR Code machine"
                              onClick={() => setQrTarget(p)}
                              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 shadow-2xs hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 transition-all cursor-pointer"
                            >
                              <QrCode className="h-3.5 w-3.5 text-blue-600" />
                              QR Code
                            </button>
                          )}

                          {p.current_status !== "archived" && (
                            <button
                              title="Archiver la procédure"
                              onClick={() => setDeleteTarget(p)}
                              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 shadow-2xs hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700 transition-all cursor-pointer"
                            >
                              <Archive className="h-3.5 w-3.5" />
                              Archiver
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Footer count */}
      {data && data.total > 0 && (
        <p className="text-[11px] font-medium text-slate-400">
          Affichage de {data.data.length} sur {data.total} procédure{data.total > 1 ? "s" : ""}
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
