import { useMemo } from "react";
import { clsx } from "clsx";
import { computeMetrics } from "@/lib/metrics";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { useReviewStore } from "@/store/reviewStore";
import type { ProcedureVersionRead } from "@/types/procedure";

function CompletionRing({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const color =
    pct >= 80
      ? "stroke-approved"
      : pct >= 50
        ? "stroke-draft"
        : "stroke-hazard";
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={72} height={72} viewBox="0 0 72 72" aria-label={`${pct}% review complete`}>
        <circle
          cx="36"
          cy="36"
          r={radius}
          fill="none"
          strokeWidth="8"
          className="stroke-steel-100"
        />
        <circle
          cx="36"
          cy="36"
          r={radius}
          fill="none"
          strokeWidth="8"
          className={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 36 36)"
        />
        <text
          x="36"
          y="41"
          textAnchor="middle"
          fontSize="14"
          fontWeight="600"
          fill="#374151"
        >
          {pct}%
        </text>
      </svg>
      <span className="text-xs text-steel-500">Review complete</span>
    </div>
  );
}

interface ReviewMetricsPanelProps {
  version: ProcedureVersionRead | null;
}

export function ReviewMetricsPanel({ version }: ReviewMetricsPanelProps) {
  const draft = useReviewStore((s) => s.draft);

  const metrics = useMemo(() => {
    if (!draft) return null;
    return computeMetrics(draft, version);
  }, [draft, version]);

  if (!metrics) return null;

  return (
    <div className="space-y-4">
      {/* KPI row */}
      <div className="surface grid grid-cols-2 gap-4 p-4 sm:grid-cols-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-steel-800">
            {metrics.componentCount}
          </div>
          <div className="text-xs text-steel-500">Components</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-steel-800">
            {metrics.stepCount}
          </div>
          <div className="text-xs text-steel-500">Steps</div>
        </div>
        <div className="text-center">
          <div
            className={clsx(
              "text-2xl font-bold",
              metrics.openValidationErrors > 0 ? "text-hazard" : "text-approved",
            )}
          >
            {metrics.openValidationErrors}
          </div>
          <div className="text-xs text-steel-500">Validation errors</div>
        </div>
        <div className="text-center">
          <div
            className={clsx(
              "text-2xl font-bold",
              metrics.pendingFields.length > 0 ? "text-draft" : "text-approved",
            )}
          >
            {metrics.pendingFields.length}
          </div>
          <div className="text-xs text-steel-500">Pending fields</div>
        </div>
      </div>

      {/* Confidence + completion ring */}
      <div className="surface grid gap-6 p-4 sm:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel-500">
            Generation Confidence
          </h4>
          <ConfidenceBar value={metrics.generationConfidence} />
          {metrics.lowConfidenceComponents > 0 && (
            <p className="mt-1.5 text-xs text-draft">
              {metrics.lowConfidenceComponents} component
              {metrics.lowConfidenceComponents > 1 ? "s" : ""} below 0.6 —
              verify detection prompts.
            </p>
          )}
        </div>
        <div className="flex items-center justify-center">
          <CompletionRing value={metrics.reviewCompletion} />
        </div>
      </div>

      {/* Approval readiness */}
      <div
        className={clsx(
          "surface p-4",
          metrics.approvalReady
            ? "border-green-200 bg-green-50"
            : "border-amber-200 bg-amber-50",
        )}
      >
        <h4
          className={clsx(
            "mb-2 text-xs font-semibold uppercase tracking-wide",
            metrics.approvalReady ? "text-approved" : "text-draft",
          )}
        >
          {metrics.approvalReady
            ? "Ready for approval"
            : "Not ready — blockers present"}
        </h4>
        {metrics.blockers.length > 0 ? (
          <ul className="space-y-1">
            {metrics.blockers.map((b, i) => (
              <li
                key={i}
                className="flex items-start gap-1.5 text-xs text-amber-800"
              >
                <span className="mt-0.5">•</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-approved">All checklist items pass.</p>
        )}
      </div>

      {/* Pending fields detail */}
      {metrics.pendingFields.length > 0 && (
        <div className="surface p-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel-500">
            Pending Fields
          </h4>
          <ul className="space-y-1.5">
            {metrics.pendingFields.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-xs">
                <code className="shrink-0 rounded bg-steel-100 px-1 py-0.5 text-[10px] text-steel-600">
                  {f.stepId}
                </code>
                <span className="text-steel-600">{f.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Generator risk warnings */}
      {metrics.riskWarnings.length > 0 && (
        <div className="surface border-red-200 bg-red-50 p-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-hazard">
            Generator Risk Warnings
          </h4>
          <ul className="space-y-1.5">
            {metrics.riskWarnings.map((w, i) => (
              <li key={i} className="flex items-start gap-2 text-xs">
                <code className="shrink-0 rounded bg-red-100 px-1 py-0.5 text-[10px] text-hazard">
                  {w.code}
                </code>
                <span className="text-steel-700">{w.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
