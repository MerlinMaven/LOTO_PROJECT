/** Status / source presentation helpers and the lifecycle transition graph. */

import type { ProcedureStatus, GenerationSource } from "@/types/procedure";

export const STATUS_LABELS: Record<ProcedureStatus, string> = {
  draft_pending_review: "Draft · Pending Review",
  approved: "Approved",
  published: "Published",
  archived: "Archived",
};

export const STATUS_SHORT: Record<ProcedureStatus, string> = {
  draft_pending_review: "Draft",
  approved: "Approved",
  published: "Published",
  archived: "Archived",
};

/** Tailwind classes for status pills (text + bg + border). */
export const STATUS_CLASSES: Record<ProcedureStatus, string> = {
  draft_pending_review: "text-draft bg-amber-50 border-amber-200",
  approved: "text-approved bg-green-50 border-green-200",
  published: "text-published bg-blue-50 border-blue-200",
  archived: "text-archived bg-stone-100 border-stone-300",
};

export const ALL_STATUSES: ProcedureStatus[] = [
  "draft_pending_review",
  "approved",
  "published",
  "archived",
];

/** The only valid forward transitions — mirrors domain/state_machine.py. */
const TRANSITIONS: Record<ProcedureStatus, ProcedureStatus[]> = {
  draft_pending_review: ["approved"],
  approved: ["published"],
  published: ["archived"],
  archived: [],
};

export function canTransition(
  from: ProcedureStatus,
  to: ProcedureStatus,
): boolean {
  return TRANSITIONS[from]?.includes(to) ?? false;
}

export function allowedTransitions(from: ProcedureStatus): ProcedureStatus[] {
  return TRANSITIONS[from] ?? [];
}

export const SOURCE_LABELS: Record<GenerationSource, string> = {
  manual: "Manual",
  llm_text: "AI · Text",
  llm_vision: "AI · Vision",
  pdf_extracted: "AI · PDF",
  video_extracted: "AI · Video",
};

export function isEditable(status: ProcedureStatus): boolean {
  return status === "draft_pending_review";
}
