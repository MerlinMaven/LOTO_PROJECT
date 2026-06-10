import { clsx } from "clsx";
import { confidenceBand, formatConfidence } from "@/lib/format";

const BAND_BAR: Record<string, string> = {
  high: "bg-approved",
  medium: "bg-draft",
  low: "bg-hazard",
};

interface ConfidenceBarProps {
  value: number | null | undefined;
  label?: string;
  className?: string;
}

export function ConfidenceBar({ value, label, className }: ConfidenceBarProps) {
  const band = confidenceBand(value);
  const pct = value === null || value === undefined ? 0 : Math.round(value * 100);
  return (
    <div className={clsx("w-full", className)}>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-steel-500">{label ?? "Confidence"}</span>
        <span className="font-semibold tabular-nums text-steel-700">
          {formatConfidence(value)}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-steel-100">
        <div
          className={clsx("h-full rounded-full transition-all", BAND_BAR[band])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
