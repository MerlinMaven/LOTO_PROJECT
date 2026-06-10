import { clsx } from "clsx";
import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function Card({
  title,
  subtitle,
  actions,
  className,
  bodyClassName,
  children,
}: CardProps) {
  return (
    <section className={clsx("surface", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-steel-100 px-4 py-3">
          <div>
            {title && (
              <h2 className="text-sm font-semibold text-steel-800">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-steel-500">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}
