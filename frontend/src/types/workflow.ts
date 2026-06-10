/**
 * Canonical workflow_definition structure (phases -> stages -> steps), plus the
 * `_generation_metadata` block the DraftPublisher embeds for the HSE reviewer.
 *
 * These mirror the backend's generated JSON. They are intentionally permissive
 * (optional fields) because the reviewer edits a live, partially-complete draft.
 */

export type PhaseType =
  | "lockout"
  | "tagout"
  | "verification"
  | "maintenance"
  | "restoration";

export type ValidationMethod =
  | "vision_detection"
  | "inverse_vision_absence"
  | "manual_confirmation"
  | "sensor_threshold";

export interface StepValidation {
  method: ValidationMethod | string;
  expected_state?: string;
  /** YOLO-World candidate prompts — reviewer-editable suggestions, never results. */
  yolo_candidate_prompts?: string[];
  [key: string]: unknown;
}

export interface WorkflowStep {
  step_id: string;
  sequence: number;
  instruction: string;
  component_ref?: string | null;
  safety_note?: string;
  /** Reviewer-authored rollback / abort guidance for this step. */
  rollback_instruction?: string;
  warnings?: string[];
  validation?: StepValidation;
  [key: string]: unknown;
}

export interface WorkflowStage {
  stage_id: string;
  sequence: number;
  title: string;
  steps: WorkflowStep[];
  [key: string]: unknown;
}

export interface WorkflowPhase {
  phase_id: string;
  phase_type: PhaseType | string;
  sequence: number;
  title: string;
  description?: string;
  stages: WorkflowStage[];
  [key: string]: unknown;
}

// ── Embedded generation metadata (_generation_metadata) ──────────────────────

export interface YoloComponentMetadata {
  component_id: string;
  label: string;
  component_type: string;
  candidate_detection_prompts: string[];
  state_prompts: Record<string, string[]>;
  confidence_threshold_suggestion: number;
  detection_difficulty: string;
  notes_for_reviewer: string;
}

export interface GenerationMetadata {
  knowledge_id?: string;
  llm_model?: string;
  prompt_version?: string;
  generator_version?: string;
  overall_confidence?: number;
  /** component_id -> per-component vision metadata. */
  yolo_metadata?: Record<string, YoloComponentMetadata>;
  generation_notes?: string[];
  validation_warnings?: { code: string; message: string }[];
  [key: string]: unknown;
}

export interface WorkflowDefinition {
  phases: WorkflowPhase[];
  _generation_metadata?: GenerationMetadata;
  [key: string]: unknown;
}
