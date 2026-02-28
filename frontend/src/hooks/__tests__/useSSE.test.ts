import { describe, it, expect } from 'vitest';
import { analysisReducer, initialState, parseSSEFrame } from '../useSSE';

describe('analysisReducer', () => {
  it('returns idle initial state', () => {
    expect(initialState.status).toBe('idle');
    expect(initialState.features).toBeNull();
    expect(initialState.callouts).toBeNull();
  });

  it('sets status to connecting', () => {
    const state = analysisReducer(initialState, { type: 'connecting' });
    expect(state.status).toBe('connecting');
  });

  it('handles feature_extraction event', () => {
    const features = [{ feature_type: 'boss', geometry: { diameter: '12mm' } }];
    const state = analysisReducer(
      { ...initialState, status: 'connecting' },
      { type: 'feature_extraction', payload: { features } }
    );
    expect(state.status).toBe('streaming');
    expect(state.features).toEqual(features);
  });

  it('handles gdt_callouts event', () => {
    const callouts = [{
      feature: '4x M6 holes',
      symbol: '\u2295',
      symbol_name: 'position',
      tolerance_value: '\u22050.25',
      unit: 'mm',
      modifier: 'MMC',
      modifier_symbol: '\u24C2',
      datum_references: ['A', 'B'],
      feature_control_frame: '|\u2295| \u22050.25 \u24C2 | A | B |',
      reasoning: 'Position for bolt pattern'
    }];
    const state = analysisReducer(
      { ...initialState, status: 'streaming' },
      { type: 'gdt_callouts', payload: { callouts } }
    );
    expect(state.callouts).toEqual(callouts);
  });

  it('handles datum_recommendation event', () => {
    const datum_scheme = {
      primary: { datum: 'A', surface: 'mounting_face', reasoning: 'Largest flat surface' },
      secondary: { datum: 'B', surface: 'locating_hole', reasoning: 'Constrains 2 DOF' },
    };
    const state = analysisReducer(
      { ...initialState, status: 'streaming' },
      { type: 'datum_recommendation', payload: { datum_scheme } }
    );
    expect(state.datumScheme).toEqual(datum_scheme);
  });

  it('handles analysis_complete event and clears step fields', () => {
    const metadata = {
      analysis_id: 'test-123',
      inference_device: 'local',
      total_latency_ms: 847,
      student_latency_ms: 290,
      classifier_latency_ms: 78,
      matcher_latency_ms: 42,
      brain_latency_ms: 12,
      worker_latency_ms: 425,
      cloud_calls: 0,
      connectivity_required: false
    };
    const state = analysisReducer(
      { ...initialState, status: 'streaming', currentStep: 4, currentStepMessage: 'Generating...', totalSteps: 5 },
      { type: 'analysis_complete', payload: { analysis_id: 'test-123', metadata } }
    );
    expect(state.status).toBe('complete');
    expect(state.metadata).toEqual(metadata);
    expect(state.currentStep).toBeNull();
    expect(state.currentStepMessage).toBeNull();
    expect(state.totalSteps).toBeNull();
  });

  it('handles progress event', () => {
    const state = analysisReducer(
      { ...initialState, status: 'connecting' },
      { type: 'progress', payload: { layer: 'student', message: 'Extracting features...', step: 1, total_steps: 5 } }
    );
    expect(state.status).toBe('streaming');
    expect(state.currentStep).toBe(1);
    expect(state.currentStepMessage).toBe('Extracting features...');
    expect(state.totalSteps).toBe(5);
  });

  it('handles error', () => {
    const state = analysisReducer(
      { ...initialState, status: 'streaming' },
      { type: 'error', payload: 'Connection failed' }
    );
    expect(state.status).toBe('error');
    expect(state.error).toBe('Connection failed');
  });

  it('resets to initial state', () => {
    const dirty = {
      ...initialState,
      status: 'complete' as const,
      features: [{ feature_type: 'boss', geometry: {} }],
    };
    const state = analysisReducer(dirty, { type: 'reset' });
    expect(state).toEqual(initialState);
  });
});

describe('parseSSEFrame', () => {
  it('parses event and data lines', () => {
    const frame = 'event: feature_extraction\ndata: {"features":[]}';
    const result = parseSSEFrame(frame);
    expect(result).toEqual({ type: 'feature_extraction', data: { features: [] } });
  });

  it('returns null for empty frame', () => {
    expect(parseSSEFrame('')).toBeNull();
  });

  it('returns null for comment-only frames', () => {
    expect(parseSSEFrame(': keep-alive')).toBeNull();
  });
});
