/** Versioned procedure draft contract. Unknown extension fields remain round-trippable. */
export type PhaseType = string;

export type ValidationMethod =
  | "visual_observation" | "measurement" | "human_confirmation"
  | "sensor_signal" | "combined_evidence" | "not_defined";

export interface StepVerification {
  method: ValidationMethod | string;
  criteria?: string[];
  required_evidence?: string[];
  instrument_refs?: string[];
  indeterminate_when?: string[];
  candidate_prompts?: string[];
  [key: string]: unknown;
}
export type StepValidation = StepVerification;

export interface WorkflowStep {
  step_id: string;
  sequence: number;
  instruction: string;
  component_ref?: string | null;
  component_refs?: string[];
  fact_refs?: string[];
  evidence_refs?: { source_id: string; page?: number; quote?: string }[];
  preconditions?: string[];
  depends_on?: string[];
  expected_result?: string;
  rationale?: string;
  basis?: string;
  unresolved_conditions?: string[];
  safety_note?: string;
  rollback_instruction?: string;
  warnings?: string[];
  validation?: StepValidation;
  verification?: StepVerification;
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
  phase_type: PhaseType;
  sequence: number;
  title: string;
  description?: string;
  stages: WorkflowStage[];
  [key: string]: unknown;
}

export interface InvariantFeature {
  feature_type: "symbol" | "pictogram" | "marking" | "local_geometry" | "fixed_text" | "color_pattern" | string;
  description: string;
  details?: string;
  source_ref?: string;
  [key: string]: unknown;
}

export interface VerifiableState {
  state_name: string;
  physical_rule: string;
  supported_by_unity?: boolean;
  candidate_prompt?: string;
  requires_human_confirmation?: boolean;
  [key: string]: unknown;
}

export interface WorkflowComponent {
  component_id: string;
  component_name?: string;
  internal_id?: string;
  source_tag?: string;
  canonical_name?: string;
  label: string;
  description?: string;
  component_type?: string;
  unity_class_id?: string;
  invariant_features?: InvariantFeature[];
  verifiable_states?: VerifiableState[];
  relations?: string[];
  clarification_needed?: boolean;
  clarification_note?: string;
  [key: string]: unknown;
}

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
  yolo_metadata?: Record<string, YoloComponentMetadata>;
  generation_notes?: string[];
  validation_warnings?: { code: string; message: string }[];
  [key: string]: unknown;
}

export interface WorkflowDefinition {
  schema_version?: string;
  revision_id?: string;
  machine_id?: string;
  machine_name?: string;
  maintenance_objective?: string;
  expected_final_state?: string;
  source_documents?: Record<string, unknown>[];
  components?: WorkflowComponent[];
  technical_facts?: Record<string, unknown>[];
  inferences?: Record<string, unknown>[];
  visual_observations?: Record<string, unknown>[];
  unknowns?: Record<string, unknown>[];
  contradictions?: Record<string, unknown>[];
  phases: WorkflowPhase[];
  clarifications_required?: Record<string, unknown>[];
  validation_diagnostics?: { code: string; category: string; severity: string; message: string; entity_id?: string }[];
  review?: Record<string, unknown>;
  _generation_metadata?: GenerationMetadata;
  [key: string]: unknown;
}
