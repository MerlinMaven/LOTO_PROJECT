import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import { useAuthStore } from "@/store/authStore";
import { ClipboardList, Zap, Activity, ShieldCheck } from "lucide-react";

const NAV_ITEMS = [
  { to: "/procedures", label: "Procédures", Icon: ClipboardList },
  { to: "/generate",   label: "Générer",    Icon: Zap },
  { to: "/interventions", label: "Interventions", Icon: Activity },
];

export function AppShell({ children }: { children: ReactNode }) {
  const reviewerId   = useAuthStore((s) => s.reviewerId);
  const reviewerRole = useAuthStore((s) => s.reviewerRole);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 md:flex-row">

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="flex shrink-0 flex-col border-b border-slate-700 bg-slate-900 md:w-64 md:border-b-0 md:border-r md:border-slate-700">

        {/* Brand */}
        <div className="flex items-center gap-3 border-b border-slate-700/60 px-5 py-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-600 shadow-sm">
            <ShieldCheck className="h-5 w-5 text-white" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-bold tracking-wide text-white">SmartLOTO</div>
            <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
              HSE Review Console
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-0.5 px-3 pt-4">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <SidebarLink key={to} to={to} label={label} Icon={Icon} />
          ))}
        </nav>

        {/* Footer compliance note */}
        <div className="mt-auto border-t border-slate-700/60 px-5 py-4">
          <p className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
            OSHA 29 CFR 1910.147
          </p>
          <p className="mt-0.5 text-[10px] text-slate-600">
            Human-in-the-loop mandatory
          </p>
        </div>
      </aside>

      {/* ── Main column ─────────────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col">

        {/* Topbar */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 shadow-sm">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              HSE Review Dashboard
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-xs font-semibold text-slate-800">{reviewerId}</div>
              <div className="text-[10px] font-medium uppercase tracking-widest text-slate-400">
                {reviewerRole}
              </div>
            </div>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 ring-2 ring-blue-200">
              {reviewerId.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="min-w-0 flex-1 overflow-x-hidden px-6 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarLink({
  to,
  label,
  Icon,
}: {
  to: string;
  label: string;
  Icon: React.FC<{ className?: string; strokeWidth?: number }>;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-150",
          isActive
            ? "bg-blue-600 text-white shadow-sm"
            : "text-slate-400 hover:bg-slate-800 hover:text-slate-100",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={clsx("h-4 w-4 shrink-0", isActive ? "text-white" : "text-slate-500")}
            strokeWidth={isActive ? 2.5 : 2}
          />
          {label}
        </>
      )}
    </NavLink>
  );
}
