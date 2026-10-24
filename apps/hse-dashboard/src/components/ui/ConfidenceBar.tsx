import { clsx } from "clsx";
import { useRef, useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { confidenceBand, formatConfidence } from "@/lib/format";
import type { ConfidenceBreakdown } from "@/lib/kpi";
import { Layers, ShieldCheck, BookOpen } from "lucide-react";

const BAND_BAR: Record<string, string> = {
  high: "bg-gradient-to-r from-blue-600 to-emerald-500",
  medium: "bg-gradient-to-r from-blue-600 to-emerald-500",
  low: "bg-gradient-to-r from-rose-500 to-amber-500",
};

interface ConfidenceBarProps {
  value: number | null | undefined;
  label?: string;
  className?: string;
  breakdown?: ConfidenceBreakdown["breakdown"] | null;
}

interface TooltipPos {
  top: number;
  left: number;
}

/**
 * Tooltip rendered into document.body via React Portal so it fully escapes
 * the table's `overflow: hidden` / `overflow-x: auto` constraint that was
 * clipping the popover when hovering the first table row.
 *
 * Flip logic: if not enough space above the anchor, renders below it.
 */
function ConfidenceTooltip({
  anchorRef,
  breakdown,
  visible,
}: {
  anchorRef: React.RefObject<HTMLDivElement | null>;
  breakdown: ConfidenceBreakdown["breakdown"];
  visible: boolean;
}) {
  const [pos, setPos] = useState<TooltipPos | null>(null);
  const [above, setAbove] = useState(true);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const recompute = useCallback(() => {
    if (!anchorRef.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const tooltipH = tooltipRef.current?.offsetHeight ?? 160;
    const MARGIN = 8;
    const spaceAbove = rect.top;
    const shouldBeAbove = spaceAbove >= tooltipH + MARGIN * 2;
    const top = shouldBeAbove
      ? rect.top + window.scrollY - tooltipH - MARGIN
      : rect.bottom + window.scrollY + MARGIN;
    const left = Math.min(
      Math.max(8, rect.left + window.scrollX),
      window.innerWidth - 216, // 208px tooltip + 8px right margin
    );
    setAbove(shouldBeAbove);
    setPos({ top, left });
  }, [anchorRef]);

  useEffect(() => {
    if (visible) {
      recompute();
    }
  }, [visible, recompute]);

  if (!visible || !pos) return null;

  return createPortal(
    <div
      ref={tooltipRef}
      style={{
        position: "absolute",
        top: pos.top,
        left: pos.left,
        zIndex: 9999,
        // Small arrow indicator direction via box-shadow hint
        transformOrigin: above ? "bottom left" : "top left",
      }}
      className="w-52 rounded-lg border border-slate-200 bg-white shadow-xl pointer-events-none animate-in fade-in duration-100"
    >
      <div className="rounded-t-lg bg-slate-50 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        Détail du score de confiance
      </div>
      <div className="divide-y divide-slate-100 px-3 py-1">
        {/* Pilier 1 */}
        <div className="flex items-center justify-between py-1.5">
          <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <Layers className="h-3 w-3 text-blue-500" />
            Extraction &amp; AR
          </span>
          <span className="text-[11px] font-semibold text-slate-800 tabular-nums">
            {breakdown.structureScore}
            <span className="font-normal text-slate-400"> / 40 pts</span>
          </span>
        </div>
        {/* Pilier 2 */}
        <div className="flex items-center justify-between py-1.5">
          <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <ShieldCheck className="h-3 w-3 text-amber-500" />
            Validité Métier
          </span>
          <span className="text-[11px] font-semibold text-slate-800 tabular-nums">
            {breakdown.blockingScore}
            <span className="font-normal text-slate-400"> / 40 pts</span>
            {breakdown.blockingCount > 0 && (
              <span className="ml-1 text-[10px] font-normal text-rose-500">
                ({breakdown.blockingCount} bloquant{breakdown.blockingCount > 1 ? "s" : ""})
              </span>
            )}
          </span>
        </div>
        {/* Pilier 3 */}
        <div className="flex items-center justify-between py-1.5">
          <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <BookOpen className="h-3 w-3 text-emerald-500" />
            Ancrage Citations
          </span>
          <span className="text-[11px] font-semibold text-slate-800 tabular-nums">
            {breakdown.citationScore}
            <span className="font-normal text-slate-400"> / 20 pts</span>
            {breakdown.unmatchedCount > 0 && (
              <span className="ml-1 text-[10px] font-normal text-orange-500">
                ({breakdown.unmatchedCount} à vérifier)
              </span>
            )}
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function ConfidenceBar({ value, label, className, breakdown }: ConfidenceBarProps) {
  const band = confidenceBand(value);
  const pct = value === null || value === undefined ? 0 : Math.round(value * 100);
  const [hovered, setHovered] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);

  const bar = (
    <div className={clsx("w-full", className)}>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-500 font-medium">{label ?? "Confiance"}</span>
        <span className="font-bold tabular-nums text-slate-800">
          {formatConfidence(value)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={clsx("h-full rounded-full transition-all duration-500", BAND_BAR[band])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );

  if (!breakdown) return bar;

  return (
    <div
      ref={anchorRef}
      className="relative w-full cursor-default"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {bar}
      <ConfidenceTooltip anchorRef={anchorRef} breakdown={breakdown} visible={hovered} />
    </div>
  );
}
