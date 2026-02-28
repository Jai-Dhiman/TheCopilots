import { useReducer, useRef, useCallback } from 'react';
import type { AnalysisState, SSEAction, AnalyzeRequest } from '../types';

export const initialState: AnalysisState = {
  status: 'idle',
  features: null,
  cadContext: null,
  datumScheme: null,
  callouts: null,
  reasoning: null,
  warnings: null,
  metadata: null,
  error: null,
  currentStep: null,
  currentStepMessage: null,
  totalSteps: null,
};

export function analysisReducer(state: AnalysisState, action: SSEAction): AnalysisState {
  switch (action.type) {
    case 'reset':
      return initialState;
    case 'connecting':
      return { ...initialState, status: 'connecting' };
    case 'feature_extraction':
      return { ...state, status: 'streaming', features: action.payload.features };
    case 'cad_context':
      return { ...state, status: 'streaming', cadContext: action.payload };
    case 'datum_recommendation':
      return { ...state, status: 'streaming', datumScheme: action.payload.datum_scheme };
    case 'gdt_callouts':
      return { ...state, status: 'streaming', callouts: action.payload.callouts };
    case 'reasoning':
      return { ...state, status: 'streaming', reasoning: action.payload };
    case 'warnings':
      return { ...state, status: 'streaming', warnings: action.payload.warnings };
    case 'analysis_complete':
      return { ...state, status: 'complete', metadata: action.payload.metadata, currentStep: null, currentStepMessage: null, totalSteps: null };
    case 'progress':
      return { ...state, status: 'streaming', currentStep: action.payload.step, currentStepMessage: action.payload.message, totalSteps: action.payload.total_steps };
    case 'error':
      return { ...state, status: 'error', error: action.payload };
  }
}

export function parseSSEFrame(frame: string): { type: string; data: unknown } | null {
  const lines = frame.split('\n');
  let eventType = '';
  let dataStr = '';

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      dataStr += line.slice(6);
    } else if (line.startsWith(':')) {
      continue;
    }
  }

  if (!eventType || !dataStr) return null;

  try {
    return { type: eventType, data: JSON.parse(dataStr) };
  } catch {
    return null;
  }
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = reader.result as string;
      // Strip the "data:image/jpeg;base64," prefix
      const base64 = dataUrl.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export function useSSE() {
  const [state, dispatch] = useReducer(analysisReducer, initialState);
  const abortRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const reset = useCallback(() => {
    abort();
    dispatch({ type: 'reset' });
  }, [abort]);

  const analyze = useCallback(async (request: AnalyzeRequest, imageBlob?: Blob) => {
    abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'connecting' });

    try {
      const body: AnalyzeRequest = { ...request };
      if (imageBlob) {
        body.image_base64 = await blobToBase64(imageBlob);
      }

      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop()!;

        for (const frame of frames) {
          const parsed = parseSSEFrame(frame);
          if (parsed) {
            if (parsed.type === 'error') {
              const errorData = parsed.data as Record<string, unknown>;
              const message = typeof errorData.error === 'string' ? errorData.error : JSON.stringify(errorData);
              dispatch({ type: 'error', payload: message });
            } else {
              dispatch({ type: parsed.type, payload: parsed.data } as SSEAction);
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      dispatch({ type: 'error', payload: err instanceof Error ? err.message : 'Unknown error' });
    }
  }, [abort]);

  return { state, analyze, reset, abort };
}
