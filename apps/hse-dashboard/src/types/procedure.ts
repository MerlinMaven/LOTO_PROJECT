/** Procedure / version / approval types — mirror app/schemas/procedure.py. */

import type { WorkflowDefinition } from "./workflow";

export type ProcedureStatus =
  | "draft_pending_review"
  | "approved"
  | "published"
  | "archived";

export type ApprovalDecision = "approved" | "rejected";

export type GenerationSource =
  | "manual"
  | "llm_text"
  | "llm_vision"
  | "pdf_extracted"
  | "video_extracted";

export interface ApprovalRead {
  id: string;
  version_id: string;
  approved_by: string;
  decision: ApprovalDecision;
  notes: string | null;
  decided_at: string;
  is_superseded: boolean;
}

export interface ProcedureVersionSummary {
  id: string;
  version_number: string;
  status: ProcedureStatus;
  created_by: string;
  created_at: string;
}

export interface ProcedureVersionRead {
  id: string;
  procedure_id: string;
  version_number: string;
  status: ProcedureStatus;
  generation_source: GenerationSource;
  llm_model_used: string | null;
  schema_version: string;
  workflow_definition: WorkflowDefinition;
  validation_errors: string[] | null;
  created_by: string;
  submitted_for_review_at: string | null;
  created_at: string;
  updated_at: string;
  latest_approval: ApprovalRead | null;
}

export interface ProcedureRead {
  id: string;
  machine_id: string;
  title: string;
  created_by: string;
  active_version_id: string | null;
  created_at: string;
  updated_at: string;
  versions: ProcedureVersionRead[];
  active_version: ProcedureVersionRead | null;
  review_version?: ProcedureVersionRead | null;
}

/** Dashboard home row — mirrors ProcedureListItem. */
export interface ProcedureListItem {
  id: string;
  machine_id: string;
  title: string;
  created_by: string;
  current_status: ProcedureStatus;
  current_version_id: string;
  current_version_number: string;
  generation_source: GenerationSource;
  overall_confidence: number | null;
  open_validation_errors: number;
  has_published_version: boolean;
  workflow_definition?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// ── Write payloads ───────────────────────────────────────────────────────────

export interface DraftUpdatePayload {
  workflow_definition: WorkflowDefinition;
  edited_by: string;
  edit_summary?: string;
}

export interface ApprovalCreatePayload {
  version_id?: string;
  decision: ApprovalDecision;
  notes?: string;
  approved_by: string;
}

export interface ProcedurePublishResponse {
  procedure_id: string;
  published_version_id: string;
  deprecated_version_id: string | null;
  published_at: string;
}
