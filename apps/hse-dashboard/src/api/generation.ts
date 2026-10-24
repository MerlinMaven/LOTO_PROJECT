/** PDF document generation endpoints and job tracking. */

import { http } from "@/api/client";

export interface ValidationIssueSummary {
  code: string;
  message: string;
  severity: string;
  field_path?: string | null;
}

export interface GenerationRunResponse {
  job_id: string;
  status: string;
  is_publishable: boolean;
  workflow_definition: Record<string, unknown>;
  validation_errors: ValidationIssueSummary[];
  validation_warnings: ValidationIssueSummary[];
  generation_notes: string[];
  error_message?: string | null;
  procedure_id?: string | null;
  version_id?: string | null;
  document_id?: string | null;
  source_filename?: string | null;
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type JobStage = "queued" | "reading" | "analyzing" | "validating" | "saving" | "succeeded" | "failed";

export interface DocumentJob {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  message: string;
  progress: string[];
  error?: string | null;
  result?: GenerationRunResponse & { version_id: string; document_id: string };
  source_filename?: string;
  source_sha256?: string;
  document_id?: string;
  procedure_id?: string | null;
  version_id?: string | null;
  timings_ms?: Record<string, number>;
  created_at?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  heartbeat_at?: string | null;
  finished_at?: string | null;
  elapsed_seconds?: number | null;
  can_retry?: boolean;
  duplicate?: boolean;
}

export async function submitPdfDocument(
  file: File,
  idempotencyKey?: string,
): Promise<DocumentJob> {
  const form = new FormData();
  form.append("file", file, file.name);
  const headers: Record<string, string> = { "Content-Type": "multipart/form-data" };
  if (idempotencyKey) {
    headers["X-Idempotency-Key"] = idempotencyKey;
  }
  const { data } = await http.post<DocumentJob>("/v1/generation/documents", form, {
    headers,
  });
  return data;
}

export async function getDocumentJob(jobId: string): Promise<DocumentJob> {
  const { data } = await http.get<DocumentJob>(`/v1/generation/jobs/${jobId}`);
  return data;
}

export async function listDocumentJobs(limit: number = 20): Promise<DocumentJob[]> {
  const { data } = await http.get<DocumentJob[]>("/v1/generation/jobs", {
    params: { limit },
  });
  return data;
}

export async function retryDocumentJob(jobId: string): Promise<DocumentJob> {
  const { data } = await http.post<DocumentJob>(`/v1/generation/jobs/${jobId}/retry`);
  return data;
}
