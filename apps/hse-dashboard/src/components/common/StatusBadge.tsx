import { clsx } from "clsx";
import type { ProcedureStatus } from "@/types/procedure";
import { STATUS_CLASSES, STATUS_SHORT, normalizeStatus } from "@/lib/status";

export function StatusBadge({
  status,
  className,
}: {
  status: ProcedureStatus | string;
  className?: string;
}) {
  const norm = normalizeStatus(status);
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_CLASSES[norm] ?? "text-slate-600 bg-slate-50 border-slate-200",
        className,
      )}
    >
      {STATUS_SHORT[norm] ?? norm}
    </span>
  );
}
