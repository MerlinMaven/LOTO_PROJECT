/**
 * Generation API client — wraps POST /api/v1/generation/run
 */

import { http } from "@/api/client";

export interface GenerationRunRequest {
  machine_id: string;
  machine_name: string;
  components: string;
  requested_by: string;
  source_type: "text" | "image";
  image_base64?: string;
  provider: "openrouter" | "mistral" | "groq" | "vllm" | "stub";
}

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
  yolo_metadata: Record<string, unknown>;
  validation_errors: ValidationIssueSummary[];
  validation_warnings: ValidationIssueSummary[];
  generation_notes: string[];
  llm_provider: string | null;
  error_message?: string | null;
  procedure_id?: string | null;
}

export async function runGeneration(
  data: GenerationRunRequest,
): Promise<GenerationRunResponse> {
  const res = await http.post<GenerationRunResponse>(
    "/v1/generation/run",
    data,
  );
  return res.data;
}
