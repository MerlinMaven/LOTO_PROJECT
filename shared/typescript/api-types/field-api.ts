/**
 * SmartLOTO Field Service API — TypeScript contracts
 *
 * FROZEN — these types mirror unity-app/SmartLOTOClient.cs exactly.
 * Do not rename fields. Do not change stage_id from number to string.
 * Generated from shared/contracts/field-api.yaml.
 */

// ── Procedures ────────────────────────────────────────────────────────────────

export interface ProcedureSummary {
  machine_id: string;
  machine_name: string;
}

export interface SpatialGuide {
  hologram_type?: string;
  pos_x: number;
  pos_y: number;
  pos_z: number;
  rot_x: number;
  rot_y: number;
  rot_z: number;
}

export interface ActionData {
  action_id: string;
  description: string;
  vision_prompt?: string;
  completion_check?: string;
  spatial_guide?: SpatialGuide;
}

export interface StageData {
  /** INTEGER — Unity StageData.stage_id is int. Never change to string. */
  stage_id: number;
  title: string;
  actions: ActionData[];
}

export interface WorkflowStages {
  lockout: StageData[];
  restoration: StageData[];
}

export interface AnchorPosition {
  pos_x: number;
  pos_y: number;
  pos_z: number;
  rot_x: number;
  rot_y: number;
  rot_z: number;
}

export interface LOTOProcedure {
  machine_id: string;
  machine_name: string;
  created_by_hse?: string;
  status: "APPROVED";
  workflow_stages: WorkflowStages;
  /** Dict keyed by organ_name. Parsed by custom C# parser. */
  anchors?: Record<string, AnchorPosition>;
}

// ── Anchors ───────────────────────────────────────────────────────────────────

export interface AnchorItem {
  organ_name: string;
  pos_x: number;
  pos_y: number;
  pos_z: number;
  rot_x: number;
  rot_y: number;
  rot_z: number;
}

export interface AnchorsUpdate {
  anchors_list: AnchorItem[];
}

// ── Interventions ─────────────────────────────────────────────────────────────

export interface StartInterventionRequest {
  machine_id: string;
  operator_name: string;
}

export interface InterventionData {
  id: string;
  machine_id: string;
  operator_name: string;
  status: "IN_PROGRESS" | "COMPLETED";
  current_stage_id: number;
}

export interface StartInterventionResponse {
  status: "success";
  intervention: InterventionData;
}

export interface ActionValidationRequest {
  intervention_id: string;
  stage_id: number;
  action_id: string;
  /** Base64-encoded JPEG. Data URL prefix is stripped server-side. */
  image_base64: string;
  vision_prompt: string;
}

export interface ActionOverrideRequest {
  intervention_id: string;
  stage_id: number;
  action_id: string;
  image_base64: string;
  reason: string;
}

export interface StepValidationResponse {
  verified: boolean;
  message: string;
  image_url: string;
}

export interface CloseInterventionRequest {
  intervention_id: string;
  /** Base64-encoded PNG signature. */
  signature_base64: string;
}

export interface CloseInterventionResponse {
  status: "success";
  message: string;
  pdf_report_url: string;
}

export interface SuccessMessage {
  status: "success";
  message: string;
}
