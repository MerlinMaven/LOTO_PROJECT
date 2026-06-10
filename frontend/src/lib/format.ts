/** Small formatting helpers for dates, confidence, and identifiers. */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffSec = Math.round((Date.now() - then) / 1000);
  const abs = Math.abs(diffSec);
  const units: [number, string][] = [
    [60, "second"],
    [3600, "minute"],
    [86400, "hour"],
    [2592000, "day"],
    [31536000, "month"],
    [Infinity, "year"],
  ];
  let prev = 1;
  for (const [limit, name] of units) {
    if (abs < limit) {
      const value = Math.round(diffSec / prev);
      const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
      return rtf.format(-value, name as Intl.RelativeTimeFormatUnit);
    }
    prev = limit;
  }
  return formatDate(iso);
}

/** 0..1 -> "92%". Returns "—" for null/undefined. */
export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

/** Confidence band used for colour coding. */
export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(value: number | null | undefined): ConfidenceBand {
  if (value === null || value === undefined) return "low";
  if (value >= 0.85) return "high";
  if (value >= 0.6) return "medium";
  return "low";
}

export function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.slice(0, 8);
}
