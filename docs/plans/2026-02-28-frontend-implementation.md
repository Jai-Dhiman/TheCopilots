# Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the React frontend for the ToleranceAI GD&T copilot — text input, streaming SSE display, feature control frame box renderer, and judge-facing status bar.

**Architecture:** Two-panel layout (input left, results right) with a `useReducer`-based SSE hook driving progressive rendering. CSS Grid for FCF boxes. Zero external libraries beyond React + Tailwind. Dark engineering-tool aesthetic.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS v4, bun

**Design doc:** `docs/plans/2026-02-28-frontend-design.md`

---

### Task 1: Scaffold Vite + React + TypeScript + Tailwind project

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tailwind.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/styles/index.css`

**Step 1: Scaffold with Vite**

```bash
cd /Users/jdhiman/Documents/copilots
bun create vite frontend --template react-ts
```

**Step 2: Install Tailwind CSS v4**

```bash
cd /Users/jdhiman/Documents/copilots/frontend
bun add -D tailwindcss @tailwindcss/vite
```

**Step 3: Configure Vite with Tailwind plugin and API proxy**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 4: Set up Tailwind CSS entry point**

Replace `frontend/src/index.css` (or create `frontend/src/styles/index.css`):

```css
@import "tailwindcss";

@theme {
  --font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, 'DejaVu Sans Mono', monospace;

  --color-gdt-form: #60a5fa;
  --color-gdt-orientation: #4ade80;
  --color-gdt-location: #f87171;
  --color-gdt-profile: #c084fc;
  --color-gdt-runout: #fb923c;

  --color-surface-900: #0f172a;
  --color-surface-800: #1e293b;
  --color-surface-700: #334155;
  --color-surface-600: #475569;
}
```

**Step 5: Update main.tsx to import CSS and render a placeholder**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

Replace `App.tsx` with a dark-themed placeholder:

```typescript
export default function App() {
  return (
    <div className="min-h-screen bg-surface-900 text-slate-200 font-mono">
      <h1 className="text-2xl p-8">ToleranceAI</h1>
    </div>
  )
}
```

**Step 6: Clean up Vite scaffold files**

Delete: `frontend/src/App.css`, `frontend/src/assets/react.svg`, `frontend/public/vite.svg`. If `index.css` was at `src/index.css`, move it to `src/styles/index.css` and update the import in `main.tsx`.

**Step 7: Verify dev server starts**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bun run dev
```

Expected: Vite dev server starts, browser shows dark page with "ToleranceAI" in monospace.

**Step 8: Commit**

```bash
git add frontend/
git commit -m "scaffold: Vite + React + TypeScript + Tailwind v4 frontend"
```

---

### Task 2: Create types.ts (mirrors backend Pydantic schemas)

**Files:**
- Create: `frontend/src/types.ts`

**Step 1: Write all TypeScript interfaces**

```typescript
// frontend/src/types.ts
// Mirrors backend/api/schemas.py — coordinate before changing

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
```

**Step 2: Verify it compiles**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx tsc --noEmit
```

Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add TypeScript types mirroring backend Pydantic schemas"
```

---

### Task 3: Build useSSE hook (reducer + SSE parser + fetch stream)

**Files:**
- Create: `frontend/src/hooks/useSSE.ts`
- Test: `frontend/src/hooks/__tests__/useSSE.test.ts`

**Step 1: Install vitest for testing**

```bash
cd /Users/jdhiman/Documents/copilots/frontend
bun add -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

Add to `vite.config.ts` (inside `defineConfig`):

```typescript
test: {
  environment: 'jsdom',
  globals: true,
},
```

**Step 2: Write the failing test for the reducer**

Create `frontend/src/hooks/__tests__/useSSE.test.ts`:

```typescript
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

  it('handles analysis_complete event', () => {
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
      { ...initialState, status: 'streaming' },
      { type: 'analysis_complete', payload: { analysis_id: 'test-123', metadata } }
    );
    expect(state.status).toBe('complete');
    expect(state.metadata).toEqual(metadata);
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
```

**Step 3: Run test to verify it fails**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run src/hooks/__tests__/useSSE.test.ts
```

Expected: FAIL — `analysisReducer` and `parseSSEFrame` not found.

**Step 4: Implement useSSE hook**

Create `frontend/src/hooks/useSSE.ts`:

```typescript
import { useReducer, useRef, useCallback } from 'react';
import type { AnalysisState, SSEAction, AnalyzeRequest } from '../types';

export const initialState: AnalysisState = {
  status: 'idle',
  features: null,
  datumScheme: null,
  callouts: null,
  reasoning: null,
  warnings: null,
  metadata: null,
  error: null,
};

export function analysisReducer(state: AnalysisState, action: SSEAction): AnalysisState {
  switch (action.type) {
    case 'reset':
      return initialState;
    case 'connecting':
      return { ...initialState, status: 'connecting' };
    case 'feature_extraction':
      return { ...state, status: 'streaming', features: action.payload.features };
    case 'datum_recommendation':
      return { ...state, status: 'streaming', datumScheme: action.payload.datum_scheme };
    case 'gdt_callouts':
      return { ...state, status: 'streaming', callouts: action.payload.callouts };
    case 'reasoning':
      return { ...state, status: 'streaming', reasoning: action.payload };
    case 'warnings':
      return { ...state, status: 'streaming', warnings: action.payload.warnings };
    case 'analysis_complete':
      return { ...state, status: 'complete', metadata: action.payload.metadata };
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
      // Comment line — ignore
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

  const analyze = useCallback(async (request: AnalyzeRequest) => {
    abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'connecting' });

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
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
            dispatch({ type: parsed.type, payload: parsed.data } as SSEAction);
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
```

**Step 5: Run tests to verify they pass**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run src/hooks/__tests__/useSSE.test.ts
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add frontend/src/hooks/ frontend/vite.config.ts frontend/package.json frontend/bun.lock
git commit -m "feat: useSSE hook with reducer, SSE parser, and fetch stream"
```

---

### Task 4: Build GDTCallout component (FCF box renderer)

**Files:**
- Create: `frontend/src/components/GDTCallout.tsx`
- Test: `frontend/src/components/__tests__/GDTCallout.test.tsx`

**Step 1: Write the failing test**

Create `frontend/src/components/__tests__/GDTCallout.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GDTCallout } from '../GDTCallout';
import type { GDTCallout as GDTCalloutType } from '../../types';

const positionCallout: GDTCalloutType = {
  feature: '4x M6 bolt holes',
  symbol: '\u2295',
  symbol_name: 'position',
  tolerance_value: '\u22050.25',
  unit: 'mm',
  modifier: 'MMC',
  modifier_symbol: '\u24C2',
  datum_references: ['A', 'B'],
  feature_control_frame: '|\u2295| \u22050.25 \u24C2 | A | B |',
  reasoning: 'Position control for bolt pattern',
};

const flatnessCallout: GDTCalloutType = {
  feature: 'mounting face',
  symbol: '\u25B1',
  symbol_name: 'flatness',
  tolerance_value: '0.1',
  unit: 'mm',
  datum_references: [],
  feature_control_frame: '|\u25B1| 0.1 |',
  reasoning: 'Flatness on primary datum surface',
};

describe('GDTCallout', () => {
  it('renders the geometric symbol', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByTitle('position')).toHaveTextContent('\u2295');
  });

  it('renders tolerance value with modifier', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText(/\u22050\.25/)).toBeInTheDocument();
    expect(screen.getByText(/\u24C2/)).toBeInTheDocument();
  });

  it('renders datum references', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders feature label below the frame', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText(/Position/i)).toBeInTheDocument();
    expect(screen.getByText(/4x M6 bolt holes/)).toBeInTheDocument();
  });

  it('renders form control without datum cells', () => {
    render(<GDTCallout callout={flatnessCallout} />);
    expect(screen.getByTitle('flatness')).toHaveTextContent('\u25B1');
    expect(screen.queryByText('A')).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run src/components/__tests__/GDTCallout.test.tsx
```

Expected: FAIL — module not found.

**Step 3: Implement GDTCallout component**

Create `frontend/src/components/GDTCallout.tsx`:

```tsx
import type { GDTCallout as GDTCalloutType } from '../types';

const SYMBOL_COLORS: Record<string, string> = {
  // Form — blue
  flatness: 'text-gdt-form',
  circularity: 'text-gdt-form',
  cylindricity: 'text-gdt-form',
  straightness: 'text-gdt-form',
  // Orientation — green
  perpendicularity: 'text-gdt-orientation',
  angularity: 'text-gdt-orientation',
  parallelism: 'text-gdt-orientation',
  // Location — red
  position: 'text-gdt-location',
  concentricity: 'text-gdt-location',
  symmetry: 'text-gdt-location',
  // Profile — purple
  profile_surface: 'text-gdt-profile',
  profile_line: 'text-gdt-profile',
  // Runout — orange
  circular_runout: 'text-gdt-runout',
  total_runout: 'text-gdt-runout',
};

function getSymbolColor(symbolName: string): string {
  return SYMBOL_COLORS[symbolName] ?? 'text-slate-300';
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

interface Props {
  callout: GDTCalloutType;
}

export function GDTCallout({ callout }: Props) {
  const color = getSymbolColor(callout.symbol_name);
  const datumCount = callout.datum_references.length;

  return (
    <div className="mb-4">
      <div
        className="inline-grid border-2 border-slate-400 rounded-sm font-mono text-lg"
        style={{
          gridTemplateColumns: `auto auto${datumCount > 0 ? ` repeat(${datumCount}, auto)` : ''}`,
        }}
      >
        {/* Symbol cell */}
        <div
          className={`px-3 py-2 border-r-2 border-slate-400 flex items-center justify-center ${color}`}
          title={callout.symbol_name}
        >
          {callout.symbol}
        </div>

        {/* Tolerance + modifier cell */}
        <div
          className={`px-3 py-2 flex items-center justify-center text-slate-200 ${datumCount > 0 ? 'border-r-2 border-slate-400' : ''}`}
        >
          {callout.tolerance_value}
          {callout.modifier_symbol && (
            <span className="ml-1">{callout.modifier_symbol}</span>
          )}
        </div>

        {/* Datum reference cells */}
        {callout.datum_references.map((datum, i) => (
          <div
            key={datum}
            className={`px-3 py-2 flex items-center justify-center text-slate-200 ${i < datumCount - 1 ? 'border-r-2 border-slate-400' : ''}`}
          >
            {datum}
          </div>
        ))}
      </div>

      {/* Label below frame */}
      <div className="mt-1 text-sm text-slate-400">
        <span className={color}>{capitalizeFirst(callout.symbol_name)}</span>
        <span className="mx-2">|</span>
        <span>{callout.feature}</span>
      </div>
    </div>
  );
}
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run src/components/__tests__/GDTCallout.test.tsx
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add frontend/src/components/GDTCallout.tsx frontend/src/components/__tests__/
git commit -m "feat: GDTCallout component with CSS Grid FCF box and color-coded symbols"
```

---

### Task 5: Build StatusBar component

**Files:**
- Create: `frontend/src/components/StatusBar.tsx`

**Step 1: Implement StatusBar**

```tsx
import type { AnalysisMetadata, AnalysisStatus } from '../types';

interface Props {
  status: AnalysisStatus;
  metadata: AnalysisMetadata | null;
}

export function StatusBar({ status, metadata }: Props) {
  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-surface-800 border-t border-surface-600 px-4 py-2 flex items-center justify-between text-xs text-slate-400 font-mono z-50">
      {/* Left: model info */}
      <div>
        Gemma 3n E2B int4 + Gemma 3 270M FT
      </div>

      {/* Center: latency breakdown */}
      <div className="flex gap-3">
        {metadata ? (
          <>
            <span>Student: {metadata.student_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Classifier: {metadata.classifier_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Matcher: {metadata.matcher_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Worker: {metadata.worker_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span className="text-slate-200 font-semibold">Total: {metadata.total_latency_ms}ms</span>
          </>
        ) : (
          <span>
            {status === 'streaming' ? 'Analyzing...' : 'Ready'}
          </span>
        )}
      </div>

      {/* Right: local badge */}
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
        <span>Local</span>
        <span className="text-surface-600">|</span>
        <span>{metadata ? metadata.cloud_calls : 0} cloud calls</span>
      </div>
    </footer>
  );
}
```

**Step 2: Verify it compiles**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/StatusBar.tsx
git commit -m "feat: StatusBar component with model info, latency, and local badge"
```

---

### Task 6: Build FeatureInput component

**Files:**
- Create: `frontend/src/components/FeatureInput.tsx`

**Step 1: Implement FeatureInput**

```tsx
import { useState } from 'react';

const PRESETS: { label: string; description: string }[] = [
  {
    label: 'Perpendicular Boss',
    description: 'Cylindrical aluminum boss, 12mm diameter, needs to be perpendicular to the mounting face within 0.05mm. CNC machined, mates with a bearing bore.',
  },
  {
    label: 'Hole Pattern',
    description: '4x M6 threaded holes on a bolt circle, 50mm PCD, need to line up with a mating flange. Sheet metal part, laser cut then tapped.',
  },
  {
    label: 'Flat Surface',
    description: 'Cast iron base plate, 300mm x 200mm, needs to be flat within 0.1mm. This is the primary mounting surface for the assembly.',
  },
  {
    label: 'Shaft',
    description: 'Turned steel shaft with two bearing journals, 25mm diameter, spaced 100mm apart. Journals need to be concentric within 0.02mm. Lathe turned.',
  },
];

interface Props {
  onAnalyze: (description: string) => void;
  isStreaming: boolean;
}

export function FeatureInput({ onAnalyze, isStreaming }: Props) {
  const [description, setDescription] = useState('');

  const handleSubmit = () => {
    const text = description.trim();
    if (!text) return;
    onAnalyze(text);
  };

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      <h2 className="text-lg font-semibold text-slate-200">Feature Description</h2>

      <textarea
        className="flex-1 bg-surface-700 border border-surface-600 rounded-lg p-4 text-slate-200 font-mono text-sm resize-none placeholder:text-slate-500 focus:outline-none focus:border-slate-400 min-h-[160px]"
        placeholder="Describe your part feature..."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit();
        }}
      />

      {/* Preset buttons */}
      <div>
        <p className="text-xs text-slate-500 mb-2">Quick examples:</p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              className="px-3 py-1.5 text-xs bg-surface-700 border border-surface-600 rounded-md text-slate-400 hover:text-slate-200 hover:border-slate-400 transition-colors"
              onClick={() => setDescription(preset.description)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <button
        className="w-full py-3 rounded-lg font-semibold transition-colors bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        onClick={handleSubmit}
        disabled={isStreaming || !description.trim()}
      >
        {isStreaming ? 'Analyzing...' : 'Analyze'}
      </button>
    </div>
  );
}
```

**Step 2: Verify it compiles**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/FeatureInput.tsx
git commit -m "feat: FeatureInput component with textarea, presets, and analyze button"
```

---

### Task 7: Build AnalysisStream component

**Files:**
- Create: `frontend/src/components/AnalysisStream.tsx`

**Step 1: Implement AnalysisStream with shimmer skeletons**

```tsx
import type { AnalysisState } from '../types';
import { GDTCallout } from './GDTCallout';

interface Props {
  state: AnalysisState;
}

function Shimmer({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-4 bg-surface-700 rounded animate-pulse"
          style={{ width: `${70 + Math.random() * 30}%` }}
        />
      ))}
    </div>
  );
}

function Section({
  title,
  show,
  children,
  pending,
}: {
  title: string;
  show: boolean;
  children: React.ReactNode;
  pending: boolean;
}) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
        {title}
      </h3>
      <div
        className="transition-opacity duration-300"
        style={{ opacity: show ? 1 : pending ? 0.5 : 0 }}
      >
        {show ? children : pending ? <Shimmer /> : null}
      </div>
    </div>
  );
}

export function AnalysisStream({ state }: Props) {
  if (state.status === 'idle') {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Enter a feature description to begin analysis
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="p-6">
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300 text-sm">
          {state.error}
        </div>
      </div>
    );
  }

  const isActive = state.status === 'streaming' || state.status === 'connecting';

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Features */}
      <Section
        title="Extracted Features"
        show={state.features !== null}
        pending={isActive && state.features === null}
      >
        {state.features && (
          <div className="space-y-2">
            {state.features.map((f, i) => (
              <div key={i} className="bg-surface-700 rounded-lg p-3 text-sm">
                <span className="text-slate-200 font-semibold">{f.feature_type}</span>
                {f.count && <span className="text-slate-400 ml-2">x{f.count}</span>}
                <div className="text-slate-400 mt-1 font-mono text-xs">
                  {Object.entries(f.geometry).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Datum Scheme */}
      <Section
        title="Datum Scheme"
        show={state.datumScheme !== null}
        pending={isActive && state.datumScheme === null && state.features !== null}
      >
        {state.datumScheme && (
          <div className="flex gap-3">
            {[state.datumScheme.primary, state.datumScheme.secondary, state.datumScheme.tertiary]
              .filter(Boolean)
              .map((d) => (
                <div key={d!.datum} className="bg-surface-700 rounded-lg p-3 flex-1">
                  <div className="text-xl font-bold text-slate-200">{d!.datum}</div>
                  <div className="text-sm text-slate-300 mt-1">{d!.surface}</div>
                  <div className="text-xs text-slate-500 mt-1">{d!.reasoning}</div>
                </div>
              ))}
          </div>
        )}
      </Section>

      {/* GDT Callouts */}
      <Section
        title="GD&T Callouts"
        show={state.callouts !== null}
        pending={isActive && state.callouts === null && state.datumScheme !== null}
      >
        {state.callouts?.map((callout, i) => (
          <GDTCallout key={i} callout={callout} />
        ))}
      </Section>

      {/* Reasoning */}
      <Section
        title="Reasoning"
        show={state.reasoning !== null}
        pending={isActive && state.reasoning === null && state.callouts !== null}
      >
        {state.reasoning && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-300">{state.reasoning.summary}</p>
            <div className="bg-surface-700 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase mb-1">Manufacturing Notes</h4>
              <p className="text-slate-300">{state.reasoning.manufacturing_notes}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {state.reasoning.standards_references.map((ref) => (
                <span key={ref} className="px-2 py-1 bg-surface-700 rounded text-xs text-slate-400 font-mono">
                  {ref}
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* Warnings */}
      <Section
        title="Warnings"
        show={state.warnings !== null && state.warnings.length > 0}
        pending={isActive && state.warnings === null && state.reasoning !== null}
      >
        {state.warnings?.map((warning, i) => (
          <div key={i} className="bg-yellow-950/30 border border-yellow-800/50 rounded-lg p-3 mb-2 text-sm text-yellow-200">
            {warning}
          </div>
        ))}
      </Section>
    </div>
  );
}
```

**Step 2: Verify it compiles**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/AnalysisStream.tsx
git commit -m "feat: AnalysisStream with progressive rendering and shimmer skeletons"
```

---

### Task 8: Wire everything together in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Implement the two-panel layout**

```tsx
import { useSSE } from './hooks/useSSE';
import { FeatureInput } from './components/FeatureInput';
import { AnalysisStream } from './components/AnalysisStream';
import { StatusBar } from './components/StatusBar';

export default function App() {
  const { state, analyze, reset } = useSSE();

  const handleAnalyze = (description: string) => {
    analyze({ description });
  };

  const isStreaming = state.status === 'connecting' || state.status === 'streaming';

  return (
    <div className="h-screen flex flex-col bg-surface-900 text-slate-200">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-700">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ToleranceAI</h1>
          <p className="text-xs text-slate-500">GD&T Copilot — ASME Y14.5-2018</p>
        </div>
        {state.status !== 'idle' && (
          <button
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            onClick={reset}
          >
            New Analysis
          </button>
        )}
      </header>

      {/* Two-panel main */}
      <main className="flex-1 grid grid-cols-[35%_65%] min-h-0">
        <div className="border-r border-surface-700 overflow-y-auto">
          <FeatureInput onAnalyze={handleAnalyze} isStreaming={isStreaming} />
        </div>
        <div className="overflow-y-auto">
          <AnalysisStream state={state} />
        </div>
      </main>

      {/* Status bar */}
      <StatusBar status={state.status} metadata={state.metadata} />
    </div>
  );
}
```

**Step 2: Verify the dev server renders correctly**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bun run dev
```

Open `http://localhost:5173` in Chrome. Expected:
- Dark background, "ToleranceAI" header
- Left panel with textarea, preset buttons, Analyze button
- Right panel with "Enter a feature description to begin analysis"
- Status bar pinned to bottom

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire App.tsx with two-panel layout, useSSE, and StatusBar"
```

---

### Task 9: Add vitest setup and testing-library config

**Files:**
- Create: `frontend/src/test-setup.ts`

**Step 1: Create test setup file**

```typescript
import '@testing-library/jest-dom/vitest';
```

**Step 2: Update vite.config.ts to reference setup file**

Add to the `test` config in `vite.config.ts`:

```typescript
test: {
  environment: 'jsdom',
  globals: true,
  setupFiles: ['./src/test-setup.ts'],
},
```

**Step 3: Run all tests**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run
```

Expected: All tests pass (useSSE reducer tests + GDTCallout render tests).

**Step 4: Commit**

```bash
git add frontend/src/test-setup.ts frontend/vite.config.ts
git commit -m "chore: add vitest setup with testing-library/jest-dom"
```

---

### Task 10: End-to-end verification

**Step 1: Run all tests**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx vitest run
```

Expected: All pass.

**Step 2: Run type check**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bunx tsc --noEmit
```

Expected: No errors.

**Step 3: Start dev server and verify visual rendering**

```bash
cd /Users/jdhiman/Documents/copilots/frontend && bun run dev
```

Manual checks:
1. Dark theme renders correctly
2. Preset buttons populate textarea
3. "Analyze" button is disabled when textarea is empty
4. Status bar shows model info and "0 cloud calls" at bottom
5. Font is monospace in textarea and status bar

**Step 4: Verify all critical files exist**

```
frontend/src/types.ts
frontend/src/hooks/useSSE.ts
frontend/src/hooks/__tests__/useSSE.test.ts
frontend/src/components/GDTCallout.tsx
frontend/src/components/__tests__/GDTCallout.test.tsx
frontend/src/components/FeatureInput.tsx
frontend/src/components/AnalysisStream.tsx
frontend/src/components/StatusBar.tsx
frontend/src/App.tsx
```
