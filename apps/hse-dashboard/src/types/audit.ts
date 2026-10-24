/** Audit event types — mirror app/schemas/audit.py (AuditEventRead). */

export interface AuditEvent {
  id: string;
  event_type: string;
  actor_id: string | null;
  machine_id: string | null;
  intervention_id: string | null;
  procedure_version_id: string | null;
  payload: Record<string, unknown>;
  ip_address: string | null;
  occurred_at: string;
  created_at?: string;
}
