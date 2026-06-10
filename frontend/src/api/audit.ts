/** Audit trail endpoint. */

import { http } from "./client";
import type { PaginatedResponse } from "@/types/api";
import type { AuditEvent } from "@/types/audit";

export interface AuditQueryParams {
  machine_id?: string;
  procedure_version_id?: string;
  event_type?: string;
  actor_id?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export const auditApi = {
  async query(
    params: AuditQueryParams = {},
  ): Promise<PaginatedResponse<AuditEvent>> {
    const { data } = await http.get<PaginatedResponse<AuditEvent>>("/v1/audit", {
      params,
    });
    return data;
  },
};
