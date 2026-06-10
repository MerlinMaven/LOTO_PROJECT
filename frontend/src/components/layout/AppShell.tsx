import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import { useAuthStore } from "@/store/authStore";

/**
 * Top-level application chrome: branded sidebar + topbar + content area.
 * Responsive — the sidebar collapses to a top strip on small screens.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const reviewerId = useAuthStore((s) => s.reviewerId);
  const reviewerRole = useAuthStore((s) => s.reviewerRole);

  return (
    <div className="flex min-h-screen flex-col bg-steel-50 md:flex-row">
      {/* Sidebar */}
      <aside className="flex shrink-0 flex-col border-b border-steel-800 bg-steel-900 text-steel-100 md:w-60 md:border-b-0 md:border-r">
        <div className="flex items-center gap-2 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-published font-bold text-white">
            L
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">SmartLOTO</div>
            <div className="text-xs text-steel-400">HSE Review</div>
          </div>
        </div>
        <nav className="flex gap-1 px-3 pb-3 md:flex-col">
          <SidebarLink to="/procedures" label="Procedures" />
        </nav>
        <div className="mt-auto hidden px-5 py-4 text-xs text-steel-400 md:block">
          OSHA 29 CFR 1910.147
          <br />
          Human-in-the-loop validation
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-steel-200 bg-white px-6 py-3">
          <h1 className="text-sm font-semibold text-steel-700">
            HSE Review Dashboard
          </h1>
          <div className="flex items-center gap-3 text-right">
            <div className="leading-tight">
              <div className="text-xs font-semibold text-steel-700">
                {reviewerId}
              </div>
              <div className="text-[11px] uppercase tracking-wide text-steel-400">
                {reviewerRole}
              </div>
            </div>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-steel-200 text-xs font-semibold text-steel-700">
              {reviewerId.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-x-hidden px-6 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          "rounded-md px-3 py-2 text-sm font-medium transition",
          isActive
            ? "bg-steel-700 text-white"
            : "text-steel-300 hover:bg-steel-800 hover:text-white",
        )
      }
    >
      {label}
    </NavLink>
  );
}
