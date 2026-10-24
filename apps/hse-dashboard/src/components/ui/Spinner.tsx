import { clsx } from "clsx";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Chargement"
      className={clsx(
        "inline-block h-5 w-5 animate-spin rounded-full border-2 border-steel-300 border-t-steel-700",
        className,
      )}
    />
  );
}

export function LoadingPane({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-steel-500">
      <Spinner />
      <p className="text-sm">{label}</p>
    </div>
  );
}
