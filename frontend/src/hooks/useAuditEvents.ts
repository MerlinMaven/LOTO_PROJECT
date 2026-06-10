/** Query hook for the audit trail. */

import { useQuery } from "@tanstack/react-query";
import { auditApi, type AuditQueryParams } from "@/api/audit";

export function useAuditEvents(params: AuditQueryParams, enabled = true) {
  return useQuery({
    queryKey: ["audit", params],
    queryFn: () => auditApi.query(params),
    enabled,
  });
}
