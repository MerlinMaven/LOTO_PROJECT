import { useState } from "react";
import { clsx } from "clsx";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { useApproveProcedure, usePublishProcedure } from "@/hooks/useProcedures";
import { useAuthStore } from "@/store/authStore";
import type { ApprovalDecision, ProcedureVersionRead } from "@/types/procedure";
import { canTransition, isEditable } from "@/lib/status";
import type { ApiError } from "@/types/api";

interface ApprovalWorkflowProps {
  procedureId: string;
  version: ProcedureVersionRead;
  /** draft.created_by — the 4-eyes rule rejects approver === author */
  authorId: string;
}

export function ApprovalWorkflow({
  procedureId,
  version,
  authorId,
}: ApprovalWorkflowProps) {
  const [open, setOpen] = useState(false);
  const [decision, setDecision] = useState<ApprovalDecision>("approved");
  const [notes, setNotes] = useState("");
  const [approvedBy, setApprovedBy] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const reviewerId = useAuthStore((s) => s.reviewerId);
  const approveMutation = useApproveProcedure(procedureId);
  const publishMutation = usePublishProcedure(procedureId);

  const canApprove =
    isEditable(version.status) && canTransition(version.status, "approved");
  const canPublish =
    version.status === "approved" &&
    canTransition(version.status, "published");

  if (!canApprove && !canPublish) return null;

  const handleSubmit = async () => {
    setFormError(null);
    const by = approvedBy.trim() || reviewerId;
    if (!by) {
      setFormError("Enter the approver ID.");
      return;
    }
    try {
      await approveMutation.mutateAsync({
        decision,
        notes: notes.trim() || undefined,
        approved_by: by,
      });
      setOpen(false);
      setNotes("");
      setApprovedBy("");
    } catch (err) {
      setFormError((err as ApiError).message ?? "Request failed.");
    }
  };

  const handlePublish = async () => {
    try {
      await publishMutation.mutateAsync();
    } catch {
      // error surfaced via mutation.error below
    }
  };

  const mutationError =
    (approveMutation.error as ApiError | null)?.message ??
    (publishMutation.error as ApiError | null)?.message;

  return (
    <>
      <div className="surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-steel-800">
              Approval Workflow
            </h3>
            <p className="text-xs text-steel-500">
              4-eyes rule — approver must differ from draft author ({authorId}).
            </p>
          </div>
          <div className="flex gap-2">
            {canApprove && (
              <Button variant="primary" onClick={() => setOpen(true)}>
                Review &amp; Decide
              </Button>
            )}
            {canPublish && (
              <Button
                variant="success"
                onClick={handlePublish}
                loading={publishMutation.isPending}
              >
                Publish
              </Button>
            )}
          </div>
        </div>

        {mutationError && (
          <p className="mt-2 text-xs text-hazard">{mutationError}</p>
        )}

        {version.latest_approval && (
          <div className="mt-3 rounded bg-steel-50 px-3 py-2 text-xs text-steel-600">
            Last decision:{" "}
            <strong
              className={
                version.latest_approval.decision === "approved"
                  ? "text-approved"
                  : "text-hazard"
              }
            >
              {version.latest_approval.decision}
            </strong>{" "}
            by {version.latest_approval.approved_by} ·{" "}
            {new Date(version.latest_approval.decided_at).toLocaleString()}
            {version.latest_approval.notes && (
              <span className="ml-1 italic">
                — &ldquo;{version.latest_approval.notes}&rdquo;
              </span>
            )}
          </div>
        )}
      </div>

      <Modal
        open={open}
        title="Review Decision"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={approveMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant={decision === "approved" ? "success" : "danger"}
              onClick={handleSubmit}
              loading={approveMutation.isPending}
            >
              {decision === "approved" ? "Approve" : "Reject"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <span className="field-label">Decision</span>
            <div className="mt-1 flex gap-6">
              {(["approved", "rejected"] as ApprovalDecision[]).map((d) => (
                <label
                  key={d}
                  className="flex cursor-pointer items-center gap-2"
                >
                  <input
                    type="radio"
                    name="decision"
                    value={d}
                    checked={decision === d}
                    onChange={() => setDecision(d)}
                    className="accent-steel-700"
                  />
                  <span
                    className={clsx(
                      "text-sm font-medium",
                      d === "approved" ? "text-approved" : "text-hazard",
                    )}
                  >
                    {d.charAt(0).toUpperCase() + d.slice(1)}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <label className="block">
            <span className="field-label">
              Approved by <span className="text-hazard">*</span>
            </span>
            <input
              type="text"
              value={approvedBy}
              onChange={(e) => setApprovedBy(e.target.value)}
              placeholder={`Reviewer ID (not "${authorId}")`}
              className="field-input"
            />
          </label>

          <label className="block">
            <span className="field-label">Notes (optional)</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Review findings, conditions, or rejection reason…"
              className="field-input"
            />
          </label>

          {formError && <p className="text-xs text-hazard">{formError}</p>}
        </div>
      </Modal>
    </>
  );
}
