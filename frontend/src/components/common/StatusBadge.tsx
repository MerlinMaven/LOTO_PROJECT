import { clsx } from "clsx";
import type { ProcedureStatus } from "@/types/procedure";
import { STATUS_CLASSES, STATUS_SHORT } from "@/lib/status";

export function StatusBadge({
  status,
  className,
}: {
  status: ProcedureStatus;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_CLASSES[status],
        className,
      )}
    >
      {STATUS_SHORT[status]}
    </span>
  );
}
