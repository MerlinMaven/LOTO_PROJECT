/**
 * Intervention API client — wraps GET /api/v1/interventions
 * (Authoring Service — PostgreSQL-backed, HSE domain)
 */

import { http } from "@/api/client";

export type InterventionStatus =
  | "pending"
  | "in_progress"
  | "paused"
  | "completed"
  | "aborted";

export interface InterventionSummary {
  id: string;
  machine_id: string;
  procedure_version_id: string;
  operator_name: string;
  status: InterventionStatus;
  current_step_ref: string | null;
  started_at: string;
  completed_at: string | null;
  aborted_at: string | null;
  abort_reason: string | null;
  pdf_report_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedInterventions {
  data: InterventionSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListInterventionsParams {
  page?: number;
  page_size?: number;
  status?: InterventionStatus | null;
}

export async function listInterventions(
  params: ListInterventionsParams = {},
): Promise<PaginatedInterventions> {
  const res = await http.get<PaginatedInterventions>("/api/v1/interventions", {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
      ...(params.status ? { status: params.status } : {}),
    },
  });
  return res.data;
}
