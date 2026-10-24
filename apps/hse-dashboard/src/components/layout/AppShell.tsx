import { useMemo, useRef, useEffect, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { clsx } from "clsx";
import { useAuthStore } from "@/store/authStore";
import { useSearchStore } from "@/store/searchStore";
import { ClipboardList, Zap, Activity, LucideIcon, Search, Shield, X, Command } from "lucide-react";
import { SmartLotoLogo } from "@/components/common/SmartLotoLogo";

const NAV_ITEMS = [
  { to: "/procedures",    label: "Procédures LOTO", Icon: ClipboardList },
  { to: "/generate",      label: "Générateur IA",   Icon: Zap },
  { to: "/interventions", label: "Interventions AR", Icon: Activity },
];

export function AppShell({ children }: { children: ReactNode }) {
  const reviewerId   = useAuthStore((s) => s.reviewerId);
  const reviewerRole = useAuthStore((s) => s.reviewerRole);
  const searchQuery = useSearchStore((s) => s.searchQuery);
  const setSearchQuery = useSearchStore((s) => s.setSearchQuery);

  const searchInputRef = useRef<HTMLInputElement>(null);

  const isMac = useMemo(() => {
    if (typeof window === "undefined" || !navigator) return false;
    return /Mac|iPod|iPhone|iPad/.test(navigator.userAgent || navigator.platform);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const location = useLocation();
  const pathname = location.pathname;

  // Calcul fluide de l'index actif pour l'animation de translation
  const activeIndex = useMemo(() => {
    if (pathname.startsWith("/generate")) return 1;
    if (pathname.startsWith("/interventions")) return 2;
    if (pathname.startsWith("/procedures") || pathname === "/") return 0;
    return -1;
  }, [pathname]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B1120] text-slate-100 antialiased">

      {/* ── Sidebar (MoveX Deep Canvas Navigation) ───────────────────────── */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col justify-between py-4 pl-3 pr-0 select-none z-10 overflow-hidden relative">
        <div>
          {/* Logo Brand (SmartLOTO Safety Vision) - Centré */}
          <div className="px-3 py-5 mr-3 flex flex-col items-center justify-center text-center border-b border-white/10 mb-5">
            <SmartLotoLogo sizeClassName="h-16" />
          </div>

          {/* Navigation Items avec indicateur glissant 60fps et encoches incurvées */}
          <nav className="relative flex flex-col gap-2">
            {/* Indicateur actif connecté à la zone principale avec courbes concaves inversées */}
            {activeIndex >= 0 && (
              <div
                className="pointer-events-none absolute left-0 right-0 z-0 h-[52px] rounded-l-2xl rounded-r-none bg-[#F4F6F9] transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
                style={{
                  transform: `translateY(${activeIndex * 60}px)`,
                }}
              >
                {/* Courbe inversée haute (top-right concave curve) */}
                <div
                  className="pointer-events-none absolute right-0 -top-5 h-5 w-5 rounded-br-[20px] bg-transparent"
                  style={{
                    boxShadow: "8px 8px 0 8px #F4F6F9",
                  }}
                />
                {/* Courbe inversée basse (bottom-right concave curve) */}
                <div
                  className="pointer-events-none absolute right-0 -bottom-5 h-5 w-5 rounded-tr-[20px] bg-transparent"
                  style={{
                    boxShadow: "8px -8px 0 8px #F4F6F9",
                  }}
                />
              </div>
            )}

            {NAV_ITEMS.map(({ to, label, Icon }) => (
              <SidebarLink key={to} to={to} label={label} Icon={Icon} />
            ))}
          </nav>
        </div>

        {/* Footer OSHA Compliance Badge */}
        <div className="mr-3 rounded-2xl bg-slate-900/80 border border-slate-800/80 p-3.5 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-blue-400">
            <Shield className="h-3.5 w-3.5" />
            <span>OSHA 29 CFR 1910.147</span>
          </div>
          <p className="text-[10px] leading-relaxed text-slate-400">
            Validation humaine obligatoire avant déploiement vers les casques Unity AR.
          </p>
        </div>
      </aside>

      {/* ── Main Content Encastré (MoveX Canvas 100% uni #F4F6F9 sans ombre ni bordure de jonction) ── */}
      <div className="flex flex-1 flex-col min-w-0 bg-[#F4F6F9] overflow-hidden relative z-10">

        {/* Topbar Unifiée 100% unie #F4F6F9 */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/60 bg-[#F4F6F9] px-6 md:px-8 py-3.5">

          {/* Left: Status Badge */}
          <div className="flex items-center gap-3">
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200/80 px-3 py-1 text-xs font-semibold text-emerald-800 shadow-2xs">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>TABLEAU DE BORD HSE</span>
            </div>
          </div>

          {/* Center: Global Search Bar ("Command Bar" contrastée) */}
          <div
            onClick={() => searchInputRef.current?.focus()}
            className="hidden lg:flex items-center justify-between bg-white border border-slate-900/15 hover:border-slate-900/30 shadow-[0_2px_10px_-2px_rgba(11,17,32,0.06)] focus-within:border-blue-600 focus-within:ring-4 focus-within:ring-blue-600/10 transition-all rounded-full px-4 py-2 w-full max-w-md relative cursor-text"
          >
            <div className="flex items-center gap-2.5 flex-1 min-w-0">
              <Search className="pointer-events-none h-4 w-4 shrink-0 text-slate-600" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Rechercher équipement, tag ou action..."
                className="w-full bg-transparent text-xs text-slate-800 placeholder-slate-400 focus:outline-none"
              />
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-2">
              {searchQuery && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSearchQuery("");
                    searchInputRef.current?.focus();
                  }}
                  className="rounded-full p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition cursor-pointer"
                  title="Vider la recherche"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              <kbd
                className="hidden sm:inline-flex items-center gap-1 rounded-md bg-slate-900 px-2 py-0.5 font-sans text-[10px] font-semibold text-slate-200 shadow-xs select-none cursor-pointer"
                onClick={() => searchInputRef.current?.focus()}
                title={isMac ? "Raccourci : ⌘K" : "Raccourci : Ctrl+K"}
              >
                {isMac ? (
                  <>
                    <Command className="h-2.5 w-2.5 text-slate-300" />
                    <span>K</span>
                  </>
                ) : (
                  <span>Ctrl K</span>
                )}
              </kbd>
            </div>
          </div>

          {/* Right: User Profile & Role */}
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight hidden sm:block">
              <div className="text-xs font-bold text-slate-900 tracking-tight">
                {reviewerId || "hse_reviewer@smartloto.io"}
              </div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-blue-600">
                {reviewerRole || "Réviseur & Signataire HSE"}
              </div>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-xs font-bold text-white shadow-md shadow-blue-600/20 ring-2 ring-white">
              {(reviewerId || "HR").slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>

        {/* Main Canvas Scroll Area */}
        <main className="flex-1 overflow-y-auto px-4 md:px-8 py-6 text-slate-900">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
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
  Icon: LucideIcon;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          "relative z-10 flex items-center gap-3.5 h-[52px] select-none transition-colors duration-300 group",
          isActive
            ? "w-full pl-3.5 pr-4 text-slate-900 font-semibold rounded-l-2xl rounded-r-none"
            : "mr-3 pl-3.5 pr-3 text-slate-400 font-medium rounded-2xl hover:bg-white/[0.04] hover:text-slate-200"
        )
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={clsx(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all duration-300",
              isActive
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/30 scale-100"
                : "bg-transparent text-slate-400 group-hover:text-slate-200 group-hover:bg-white/5"
            )}
          >
            <Icon
              className="h-4 w-4 shrink-0 transition-colors"
              strokeWidth={isActive ? 2.5 : 2}
            />
          </div>
          <span className="truncate">{label}</span>
        </>
      )}
    </NavLink>
  );
}
