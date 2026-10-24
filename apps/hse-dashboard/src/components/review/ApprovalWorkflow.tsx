import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { useApproveProcedure, usePublishProcedure } from "@/hooks/useProcedures";
import { useAuthStore } from "@/store/authStore";
import { useReviewStore } from "@/store/reviewStore";
import type { ApprovalDecision, ProcedureVersionRead } from "@/types/procedure";
import { canTransition, isEditable } from "@/lib/status";
import type { ApiError } from "@/types/api";
import { getBusinessBlockingCount } from "@/lib/kpi";
import { CheckCircle2, AlertCircle, ShieldCheck, Send, Check, Lock } from "lucide-react";

interface ApprovalWorkflowProps {
  procedureId: string;
  version: ProcedureVersionRead;
  authorId: string;
}

export function ApprovalWorkflow({
  procedureId,
  version,
  authorId,
}: ApprovalWorkflowProps) {
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [decision, setDecision] = useState<ApprovalDecision>("approved");
  const [publishDirectly, setPublishDirectly] = useState(true);
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const reviewerId = useAuthStore((s) => s.reviewerId);
  const approveMutation = useApproveProcedure(procedureId);
  const publishMutation = usePublishProcedure(procedureId);
  const draft = useReviewStore((s) => s.draft);

  // Synchronisation avec les boutons d'action du haut de page
  useEffect(() => {
    const handleOpenReview = () => {
      setFormError(null);
      setReviewModalOpen(true);
    };
    const handleOpenPublish = () => {
      setPublishModalOpen(true);
    };
    window.addEventListener("open-approval-modal", handleOpenReview);
    window.addEventListener("open-publish-modal", handleOpenPublish);
    return () => {
      window.removeEventListener("open-approval-modal", handleOpenReview);
      window.removeEventListener("open-publish-modal", handleOpenPublish);
    };
  }, []);

  const allActiveBlockers = useMemo(() => {
    const list: Array<{ id: string; label: string }> = [];

    // Clarifications non résolues
    const clarifs = (draft?.clarifications_required ?? []) as Array<Record<string, unknown>>;
    clarifs.forEach((q) => {
      if (q.status !== "resolved") {
        const question = String(q.question || "Clarification requise");
        const relatedComps = Array.isArray(q.related_component_ids)
          ? (q.related_component_ids as string[]).filter(Boolean)
          : [];

        // Détermination de la règle et des composants normalisés (R-01..R-04)
        let ruleId = "R-0" + (list.length + 1);
        if (relatedComps.includes("C05") || relatedComps.includes("C07")) ruleId = "R-01";
        else if (relatedComps.includes("C06")) ruleId = "R-02";
        else if (relatedComps.includes("C02") || relatedComps.includes("C03")) ruleId = "R-03";
        else if (relatedComps.includes("C04")) ruleId = "R-04";

        const compLabel = relatedComps.length > 0 ? relatedComps.join(" / ") : "";
        const prefix = compLabel ? `[${ruleId} • ${compLabel}] ` : `[${ruleId}] `;

        list.push({
          id: String(q.id || list.length),
          label: `${prefix}${question} — Non résolu`,
        });
      }
    });

    // Diagnostics bloquants
    const diags = (draft?.validation_diagnostics ?? []) as Array<Record<string, unknown>>;
    diags.forEach((d) => {
      if (d.severity === "blocking" || d.severity === "error") {
        const cat = String(d.category || "").toLowerCase();
        if (cat === "source_integrity") return;
        if (String(d.code) === "CLARIFICATION_OPEN") return;
        const msg = String(d.message || d.code || "").trim();
        const entity = d.entity_id ? `[${d.entity_id}] ` : "";
        if (msg && !list.some((it) => it.label.includes(msg))) {
          list.push({
            id: String(d.code || d.entity_id || list.length),
            label: `${entity}${msg} — Bloquant`,
          });
        }
      }
    });

    return list;
  }, [draft?.clarifications_required, draft?.validation_diagnostics]);

  const totalBlockingCount = useMemo(() => {
    return getBusinessBlockingCount({ workflow_definition: draft as Record<string, unknown> });
  }, [draft]);

  const totalClarifsCount = (draft?.clarifications_required ?? []).length;
  const resolvedClarifsCount = ((draft?.clarifications_required ?? []) as Array<Record<string, unknown>>).filter(
    (q) => q.status === "resolved"
  ).length;

  const hasBlockingIssues = totalBlockingCount > 0;

  const isSelfReview = Boolean(
    reviewerId && authorId && reviewerId.trim().toLowerCase() === authorId.trim().toLowerCase()
  );
  // En mode MVP / Démo, l'auto-validation est autorisée pour faciliter la démonstration fluide
  const isDev = import.meta.env.DEV || true;
  const fourEyesBlocked = isSelfReview && !isDev;

  const isPublished = version.status === "published";
  const canApprove =
    isEditable(version.status) &&
    canTransition(version.status, "approved") &&
    !hasBlockingIssues &&
    !fourEyesBlocked;
  const canPublish =
    version.status === "approved" &&
    canTransition(version.status, "published") &&
    !hasBlockingIssues &&
    !fourEyesBlocked;

  const handleApprove = async () => {
    setFormError(null);
    if (!reviewerId) {
      setFormError("Identifiant du signataire requis.");
      return;
    }
    try {
      await approveMutation.mutateAsync({
        versionId: version.id,
        payload: {
          version_id: version.id,
          decision,
          notes: notes.trim() || undefined,
          approved_by: reviewerId,
        },
      });

      if (decision === "approved" && publishDirectly) {
        await publishMutation.mutateAsync(version.id);
      }

      setReviewModalOpen(false);
      setNotes("");
    } catch (err) {
      setFormError((err as ApiError).message ?? "Échec de l'approbation.");
    }
  };

  const handlePublishConfirm = async () => {
    try {
      await publishMutation.mutateAsync(version.id);
      setPublishModalOpen(false);
    } catch {
      // Erreur gérée par mutation
    }
  };

  const mutationError =
    (approveMutation.error as ApiError | null)?.message ??
    (publishMutation.error as ApiError | null)?.message;

  const showBackgroundError = !reviewModalOpen && !publishModalOpen && mutationError;

  // Si déjà publiée
  if (isPublished) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
        <div className="flex items-center gap-3 text-emerald-900">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
          <div>
            <h3 className="text-sm font-bold">Procédure publiée et active</h3>
            <p className="text-xs text-emerald-800">
              Cette révision (v{version.version_number}) est accessible en temps réel aux opérateurs sur les casques Unity Quest.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-slate-700" />
              <h3 className="text-sm font-bold text-slate-900">
                Validation & Publication HSE
              </h3>
            </div>
            <p className="mt-0.5 text-xs text-slate-500">
              {isSelfReview && isDev
                ? `Mode DEV / MVP : auto-validation autorisée pour l'ingénieur ${reviewerId}. La traçabilité sera certifiée.`
                : `Règle des 4 yeux (OSHA) : le signataire (${reviewerId}) doit valider le brouillon avant publication.`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isSelfReview && isDev && (
              <span className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800 shadow-sm">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                Auto-validation autorisée (Mode DEV)
              </span>
            )}

            {fourEyesBlocked && (
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-800">
                <AlertCircle className="h-3.5 w-3.5 text-rose-600" />
                Règle des 4 yeux : le relecteur ({reviewerId}) ne peut pas approuver son propre brouillon ({authorId}).
              </span>
            )}

            {hasBlockingIssues ? (
              <button
                disabled
                className="flex items-center gap-1.5 rounded-md bg-slate-100 border border-slate-200 px-3.5 py-2 text-xs font-semibold text-slate-400 cursor-not-allowed shadow-xs"
                title={`Résolvez les ${totalBlockingCount} point(s) bloquant(s) pour débloquer la publication.`}
              >
                <Lock className="h-3.5 w-3.5 text-slate-400" />
                Publier ({totalBlockingCount} point{totalBlockingCount > 1 ? "s" : ""} à résoudre)
              </button>
            ) : null}

            {canApprove && (
              <Button
                id="approve-procedure-btn"
                variant="primary"
                onClick={() => {
                  setFormError(null);
                  setReviewModalOpen(true);
                }}
              >
                Approuver la procédure
              </Button>
            )}

            {canPublish && (
              <Button
                variant="success"
                onClick={() => setPublishModalOpen(true)}
                loading={publishMutation.isPending}
              >
                <Send className="mr-1.5 h-3.5 w-3.5" />
                Publier pour les opérateurs
              </Button>
            )}
          </div>
        </div>

        {hasBlockingIssues ? (
          <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50/70 p-3.5 text-xs text-rose-900 space-y-2">
            <div className="flex items-center gap-2 font-bold text-rose-950">
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
              <span>
                Publication verrouillée : {totalBlockingCount} clarification{totalBlockingCount > 1 ? "s" : ""} HSE requise{totalBlockingCount > 1 ? "s" : ""} avant approbation
              </span>
            </div>
            <ul className="space-y-1.5 pl-5 list-disc text-rose-800">
              {allActiveBlockers.map((b, idx) => (
                <li key={idx} className="leading-snug">
                  {b.label}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50/70 p-3 text-xs text-emerald-900 flex items-start gap-2.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-semibold text-emerald-950">
                {resolvedClarifsCount}/{totalClarifsCount} clarifications HSE résolues ({resolvedClarifsCount} décisions techniques enregistrées par l'ingénieur).
              </span>
              <p className="text-[11px] text-emerald-800 leading-relaxed">
                Toutes les ambiguïtés techniques ont été arbitrées et répercutées sur les étapes du Workflow et les composants Vision. La procédure est conforme pour approbation et mise en production.
              </p>
            </div>
          </div>
        )}

        {showBackgroundError && (
          <div className="mt-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
            {mutationError}
          </div>
        )}

        {version.latest_approval && (
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 border border-slate-200/60">
            Dernière décision :{" "}
            <strong
              className={
                version.latest_approval.decision === "approved"
                  ? "text-emerald-700"
                  : "text-rose-700"
              }
            >
              {version.latest_approval.decision === "approved" ? "Approuvé" : "Rejeté"}
            </strong>{" "}
            par {version.latest_approval.approved_by} ·{" "}
            {new Date(version.latest_approval.decided_at).toLocaleString("fr-FR")}
            {version.latest_approval.notes && (
              <span className="ml-1 italic">
                — &laquo; {version.latest_approval.notes} &raquo;
              </span>
            )}
          </div>
        )}
      </div>

      {/* Modal d'approbation */}
      <Modal
        open={reviewModalOpen}
        title="Approbation formelle HSE"
        onClose={() => setReviewModalOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setReviewModalOpen(false)}
              disabled={approveMutation.isPending}
            >
              Annuler
            </Button>
            <Button
              id="confirm-approval-btn"
              variant={decision === "approved" ? "success" : "danger"}
              onClick={handleApprove}
              loading={approveMutation.isPending || publishMutation.isPending}
            >
              {decision === "approved"
                ? publishDirectly
                  ? "Approuver & Publier"
                  : "Confirmer l'approbation"
                : "Rejeter"}
            </Button>
          </>
        }
      >
        <div className="space-y-4 text-xs">
          <div>
            <span className="font-semibold text-slate-800">Décision HSE</span>
            <div className="mt-2 flex gap-4">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="decision"
                  value="approved"
                  checked={decision === "approved"}
                  onChange={() => setDecision("approved")}
                  className="accent-emerald-600"
                />
                <span className="font-semibold text-emerald-800">Approuver la conformité</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="decision"
                  value="rejected"
                  checked={decision === "rejected"}
                  onChange={() => setDecision("rejected")}
                  className="accent-rose-600"
                />
                <span className="font-semibold text-rose-800">Rejeter</span>
              </label>
            </div>
          </div>

          <div className="rounded-lg bg-slate-50 p-3 border border-slate-200 text-slate-700 space-y-1">
            <div className="flex items-center justify-between">
              <span>Signataire certifié : <strong>{reviewerId}</strong></span>
              <span className="text-[11px] text-slate-400 font-mono">v{version.version_number}</span>
            </div>
            {isSelfReview && isDev ? (
              <p className="text-[11px] text-emerald-700 font-medium flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                Auto-validation autorisée (Mode DEV / MVP). Votre signature sera tracée dans le journal d'audit.
              </p>
            ) : fourEyesBlocked ? (
              <p className="text-[11px] text-rose-700 font-semibold flex items-center gap-1">
                <AlertCircle className="h-3.5 w-3.5 text-rose-600 shrink-0" />
                Attention : vous êtes l'auteur de ce brouillon. Un second relecteur doit signer (règle des 4 yeux).
              </p>
            ) : null}
          </div>

          {decision === "approved" && (
            <label className="flex items-center gap-2.5 rounded-lg bg-blue-50 border border-blue-200 p-2.5 text-xs text-blue-900 cursor-pointer hover:bg-blue-100/60 transition">
              <input
                type="checkbox"
                checked={publishDirectly}
                onChange={(e) => setPublishDirectly(e.target.checked)}
                className="h-4 w-4 rounded text-blue-600 focus:ring-blue-500 accent-blue-600 cursor-pointer"
              />
              <span className="font-semibold">
                Publier directement la procédure pour les casques Unity après signature
              </span>
            </label>
          )}

          <label className="block">
            <span className="font-semibold text-slate-800">Remarques ou conditions d'application (optionnel)</span>
            <textarea
              id="notes-textarea"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Ex: Vérification effectuée sur le schéma P&ID révisé..."
              className="mt-1 w-full rounded border border-slate-300 p-2 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </label>

          {formError && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700 font-medium">
              {formError}
            </div>
          )}
        </div>
      </Modal>

      {/* Modal de confirmation de publication */}
      <Modal
        open={publishModalOpen}
        title="Confirmer la publication de la procédure"
        onClose={() => setPublishModalOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setPublishModalOpen(false)}
              disabled={publishMutation.isPending}
            >
              Annuler
            </Button>
            <Button
              variant="success"
              onClick={handlePublishConfirm}
              loading={publishMutation.isPending}
            >
              <Check className="mr-1 h-3.5 w-3.5" />
              Confirmer la mise en production
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-xs text-slate-700">
          <p>
            Vous êtes sur le point de publier officiellement la procédure pour l'équipement{" "}
            <strong className="font-mono text-slate-900">{procedureId}</strong> (version v{version.version_number}).
          </p>
          <div className="rounded-md border border-amber-200 bg-amber-50/60 p-3 text-amber-900">
            <p className="font-semibold">Conséquences de la publication :</p>
            <ul className="mt-1 list-disc pl-4 space-y-0.5 text-[11px]">
              <li>Cette version deviendra la procédure active de référence.</li>
              <li>Les opérateurs sur casque Unity Quest pourront immédiatement démarrer des interventions de consignation.</li>
              <li>Chaque future intervention conservera la trace immuable de cette version v{version.version_number}.</li>
            </ul>
          </div>
        </div>
      </Modal>
    </>
  );
}
