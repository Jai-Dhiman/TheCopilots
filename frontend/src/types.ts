// frontend/src/types.ts
// Mirrors backend/api/schemas.py -- coordinate before changing

export interface AnalyzeRequest {
  description: string;
  image?: string; // base64 encoded
  manufacturing_process?: string;
  material?: string;
  context?: {
    assembly_info?: string;
    company_rules?: string;
  };
}

export interface FeatureRecord {
  feature_type: string;
  count?: number;
  geometry: Record<string, string>;
  parent_surface?: string;
  material_detected?: string;
  process_detected?: string;
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

export type AnalysisStatus = 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';

export interface AnalysisState {
  status: AnalysisStatus;
  features: FeatureRecord[] | null;
  datumScheme: DatumScheme | null;
  callouts: GDTCallout[] | null;
  reasoning: ReasoningData | null;
  warnings: string[] | null;
  metadata: AnalysisMetadata | null;
  error: string | null;
}

export type SSEAction =
  | { type: 'connecting' }
  | { type: 'feature_extraction'; payload: { features: FeatureRecord[]; material_detected?: string; process_detected?: string } }
  | { type: 'datum_recommendation'; payload: { datum_scheme: DatumScheme } }
  | { type: 'gdt_callouts'; payload: { callouts: GDTCallout[] } }
  | { type: 'reasoning'; payload: ReasoningData }
  | { type: 'warnings'; payload: { warnings: string[] } }
  | { type: 'analysis_complete'; payload: { analysis_id: string; metadata: AnalysisMetadata } }
  | { type: 'error'; payload: string }
  | { type: 'reset' };
