// frontend/src/types.ts
// Mirrors backend/api/schemas.py -- coordinate before changing

export interface CADContext {
  document_name?: string | null;
  objects: Record<string, unknown>[];
  sketches: Record<string, unknown>[];
  materials: Record<string, unknown>[];
  bounding_box?: Record<string, number> | null;
  source: string;
  connected: boolean;
}

export interface AnalyzeRequest {
  description: string;
  image_base64?: string;
  manufacturing_process?: string;
  material?: string;
  compare?: boolean;
  cad_context?: CADContext | null;
}

export interface FeatureRecord {
  feature_type: string;
  geometry: Record<string, number | string | null>;
  material: string;
  manufacturing_process: string;
  mating_condition?: string | null;
  parent_surface?: string | null;
}

export interface DatumRecord {
  datum: string;
  surface: string;
  reasoning: string;
}

export interface DatumScheme {
  primary: DatumRecord;
  secondary?: DatumRecord;
  tertiary?: DatumRecord;
}

export interface GDTCallout {
  feature: string;
  symbol: string;
  symbol_name: string;
  tolerance_value: string;
  unit: string;
  modifier?: string;
  modifier_symbol?: string;
  datum_references: string[];
  feature_control_frame: string;
  reasoning: string;
}

export interface ReasoningData {
  summary: string;
  manufacturing_notes: string;
  standards_references: string[];
}

export interface AnalysisMetadata {
  analysis_id: string;
  inference_device: string;
  total_latency_ms: number;
  student_latency_ms: number;
  classifier_latency_ms: number;
  matcher_latency_ms: number;
  brain_latency_ms: number;
  worker_latency_ms: number;
  cloud_calls: number;
  connectivity_required: boolean;
}

export interface CreateDrawingRequest {
  document_name: string;
  callouts: Record<string, unknown>[];
  datum_scheme: Record<string, unknown>;
  features: Record<string, unknown>;
}

export type AnalysisStatus = 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';

export interface AnalysisState {
  status: AnalysisStatus;
  features: FeatureRecord[] | null;
  cadContext: CADContext | null;
  datumScheme: DatumScheme | null;
  callouts: GDTCallout[] | null;
  reasoning: ReasoningData | null;
  warnings: string[] | null;
  metadata: AnalysisMetadata | null;
  error: string | null;
  currentStep: number | null;
  currentStepMessage: string | null;
  totalSteps: number | null;
}

export type SSEAction =
  | { type: 'connecting' }
  | { type: 'feature_extraction'; payload: { features: FeatureRecord[]; material_detected?: string | null; process_detected?: string | null } }
  | { type: 'cad_context'; payload: CADContext }
  | { type: 'datum_recommendation'; payload: { datum_scheme: DatumScheme } }
  | { type: 'gdt_callouts'; payload: { callouts: GDTCallout[] } }
  | { type: 'reasoning'; payload: ReasoningData }
  | { type: 'warnings'; payload: { warnings: string[] } }
  | { type: 'analysis_complete'; payload: { analysis_id: string; metadata: AnalysisMetadata } }
  | { type: 'progress'; payload: { layer: string; message: string; step: number; total_steps: number } }
  | { type: 'error'; payload: string }
  | { type: 'reset' };
