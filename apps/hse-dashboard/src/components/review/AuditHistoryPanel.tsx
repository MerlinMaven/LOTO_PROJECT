import { useAuditEvents } from "@/hooks/useAuditEvents";
import { LoadingPane } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/format";
import type { ApiError } from "@/types/api";
import {
  FileEdit,
  CheckCircle2,
  XCircle,
  Send,
  Sparkles,
  Archive,
  History,
  User,
  Clock,
} from "lucide-react";

interface AuditConfig {
  label: string;
  badgeClass: string;
  icon: typeof FileEdit;
}

const EVENT_CONFIG: Record<string, AuditConfig> = {
  PROCEDURE_CREATED: {
    label: "Procédure générée (IA)",
    badgeClass: "bg-purple-50 text-purple-700 border-purple-200",
    icon: Sparkles,
  },
  PROCEDURE_DRAFT_UPDATED: {
    label: "Brouillon mis à jour",
    badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
    icon: FileEdit,
  },
  PROCEDURE_APPROVED: {
    label: "Conformité HSE approuvée",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    icon: CheckCircle2,
  },
  PROCEDURE_REJECTED: {
    label: "Procédure rejetée",
    badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
    icon: XCircle,
  },
  PROCEDURE_PUBLISHED: {
    label: "Procédure publiée pour les opérateurs",
    badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200",
    icon: Send,
  },
  PROCEDURE_ARCHIVED: {
    label: "Procédure archivée",
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
    icon: Archive,
  },
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

  if (isLoading) return <LoadingPane label="Chargement de la piste d'audit…" />;

  if (isError) {
    return (
      <EmptyState
        title="Impossible de charger l'historique d'audit"
        description={(error as ApiError)?.message ?? "Une erreur inattendue est survenue."}
      />
    );
  }

  if (!data || data.data.length === 0) {
    return (
      <EmptyState
        title="Aucun événement d'audit"
        description="Aucun événement n'a encore été enregistré pour cette version."
      />
    );
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <History className="h-4 w-4 text-blue-600" />
            Journal d'Audit Immuable (Traçabilité OSHA 29 CFR 1910.147)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Historique certifié des révisions, approbations et signatures de cette procédure.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 border border-slate-200">
          {data.data.length} événement{data.data.length > 1 ? "s" : ""}
        </span>
      </div>

      <ol className="relative border-l border-slate-200 ml-3 space-y-6">
        {data.data.map((event) => {
          const config = EVENT_CONFIG[event.event_type] ?? {
            label: event.event_type,
            badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
            icon: FileEdit,
          };
          const Icon = config.icon;

          const payload = (event.payload && typeof event.payload === "object"
            ? (event.payload as Record<string, unknown>)
            : {}) as Record<string, unknown>;

          const notes = typeof payload.notes === "string" && payload.notes.trim() ? payload.notes.trim() : null;
          const decision = typeof payload.decision === "string" ? payload.decision : null;

          return (
            <li key={event.id} className="ml-6 group">
              {/* Timeline marker */}
              <span className="absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full bg-white border border-slate-300 shadow-xs group-hover:scale-110 transition-transform">
                <Icon className="h-3 w-3 text-slate-600" />
              </span>

              {/* Event card */}
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs transition hover:border-slate-300">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold shadow-xs ${config.badgeClass}`}
                    >
                      <Icon className="h-3 w-3" />
                      {config.label}
                    </span>

                    <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600">
                      <User className="h-3 w-3 text-slate-400" />
                      {event.actor_id || "Système SmartLOTO"}
                    </span>
                  </div>

                  <time
                    dateTime={event.created_at || event.occurred_at}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 tabular-nums"
                  >
                    <Clock className="h-3 w-3" />
                    {formatDate(event.created_at || event.occurred_at)}
                  </time>
                </div>

                {/* Notes & Décisions métier (Zéro JSON brut) */}
                {decision && (
                  <div className="mt-2 text-xs">
                    <span className="font-medium text-slate-500">Décision signée : </span>
                    <strong className={decision === "approved" ? "text-emerald-700" : "text-rose-700"}>
                      {decision === "approved" ? "Conforme pour mise en production" : "Rejeté avec réserves"}
                    </strong>
                  </div>
                )}

                {notes && (
                  <div className="mt-2 rounded-lg bg-slate-50 border border-slate-200/70 p-2.5 text-xs text-slate-700">
                    <span className="font-semibold text-slate-500 block mb-0.5">Remarques du signataire :</span>
                    <p className="italic">« {notes} »</p>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
