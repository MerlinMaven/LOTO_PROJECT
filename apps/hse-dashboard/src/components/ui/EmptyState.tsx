import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-steel-300 bg-steel-50 px-6 py-12 text-center">
      {icon && <div className="text-3xl text-steel-400">{icon}</div>}
      <h3 className="text-sm font-semibold text-steel-700">{title}</h3>
      {description && (
        <p className="max-w-md text-xs text-steel-500">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
