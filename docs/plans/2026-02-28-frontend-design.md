# Frontend Design: ToleranceAI GD&T Copilot

## Context

Building the React frontend for ToleranceAI, a GD&T copilot demoed at the Google DeepMind x InstaLILY hackathon. The backend streams SSE results through 6 typed stages. The frontend must render progressive results with feature control frame box notation, look like a professional engineering tool (not a chatbot), and prove zero-cloud edge inference via a judge-facing status bar.

## Decisions Made

- **FCF rendering:** CSS Grid (variable column count via `grid-template-columns`)
- **SSE consumption:** `fetch()` + `ReadableStream` + manual SSE parsing (zero deps)
- **State management:** `useReducer` with typed discriminated union actions
- **Theme:** Hardcoded dark (no light mode toggle)
- **Package manager:** bun
- **No external UI library** — all components are custom

## Tech Stack

- React 18+ / TypeScript / Vite
- Tailwind CSS (utility-first, hardcoded dark palette)
- JetBrains Mono (or system monospace fallback) for FCF notation
- Zero external state or SSE libraries

## File Structure

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    types.ts                    # mirrors backend/api/schemas.py
    hooks/
      useSSE.ts                 # fetch + ReadableStream + useReducer
    components/
      FeatureInput.tsx           # left panel: textarea, presets, analyze button
      AnalysisStream.tsx         # right panel: progressive section renderer
      GDTCallout.tsx             # FCF box renderer (CSS Grid)
      DatumScheme.tsx            # A > B > C datum hierarchy (P1)
      ReasoningPanel.tsx         # expandable reasoning + ASME refs
      StatusBar.tsx              # pinned bottom: model, latency, local badge
    styles/
      index.css                 # Tailwind directives + custom FCF styles
```

## Component Tree & Data Flow

```
App.tsx
  Header (inline)
  main (grid: 35% / 65%)
    FeatureInput              props: { onAnalyze, isStreaming }
    AnalysisStream            props: { state: AnalysisState }
      FeaturesSection         (inline — extracted features list)
      DatumScheme             props: { scheme: DatumScheme | null }
      GDTCallout[]            props: { callout: GDTCallout }
      ReasoningPanel          props: { reasoning, refs }
      WarningsSection         (inline — warning cards)
  StatusBar                   props: { status, metadata }
```

Data flow: `App.tsx` calls `useSSE()` to get `{ state, analyze, reset, abort }`. Passes `analyze` down to `FeatureInput`, passes `state` slices to `AnalysisStream` children. Single source of truth via the reducer.

## useSSE Hook

```typescript
interface UseSSEReturn {
  state: AnalysisState;
  analyze: (req: AnalyzeRequest) => void;
  reset: () => void;
  abort: () => void;
}

type AnalysisState = {
  status: 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';
  features: FeatureRecord[] | null;
  datumScheme: DatumScheme | null;
  callouts: GDTCallout[] | null;
  reasoning: ReasoningData | null;
  warnings: string[] | null;
  metadata: AnalysisMetadata | null;
  error: string | null;
};
```

Mechanics:
- `analyze()` resets state, creates AbortController, POSTs to `/api/analyze`
- Reads stream via `response.body.getReader()` + `TextDecoder`
- Splits buffer on `\n\n`, parses `event:` and `data:` lines
- Each parsed event dispatches to reducer (event type = action type)
- Aborts on unmount via useEffect cleanup
- No retry logic (hackathon scope)

Transitions: `idle -> connecting -> streaming -> complete | error`

## GDTCallout Component (Core Visual)

CSS Grid FCF box renderer:

```
grid-template-columns: auto auto repeat(datum_count, auto)
```

Cell layout:
- Cell 1: geometric symbol (color-coded by category)
- Cell 2: tolerance value + modifier symbol
- Cells 3+: datum references (0-3 cells)

Color coding by category:
- Blue (`text-blue-400`): form (flatness, circularity, cylindricity, straightness)
- Green (`text-green-400`): orientation (perpendicularity, angularity, parallelism)
- Red (`text-red-400`): location (position, concentricity, symmetry)
- Purple (`text-purple-400`): profile (profile of surface, profile of line)
- Orange (`text-orange-400`): runout (circular runout, total runout)

Below each FCF box: text label with symbol name + feature name (e.g., "Position | 4x M6 bolt holes") for judges who don't know GD&T notation.

Font: JetBrains Mono / monospace. Border: 2px solid. Title attributes on all Unicode symbols.

## FeatureInput Component

Left panel (~35% width):
- `<textarea>` with monospace font, placeholder "Describe your part feature..."
- Row of preset buttons: "Perpendicular Boss", "Hole Pattern", "Flat Surface", "Shaft", "Bracket Photo"
- Each preset populates textarea with acceptance test input text
- "Analyze" button — disabled + loading state during streaming
- P1: image upload zone with preview

## AnalysisStream Component

Right panel (~65% width), renders sections top-to-bottom:
1. Features section (extracted features list)
2. Datum scheme (A > B > C hierarchy)
3. Callouts (array of GDTCallout components)
4. Reasoning (expandable panel)
5. Warnings (yellow warning cards)

Stages with `null` data: render shimmer skeleton (pulsing gray bars, `animate-pulse`).
Stages with data: fade-in via `transition: opacity 300ms`.
When `status === 'idle'`: empty state message.

## StatusBar Component

Fixed bottom bar:
- Left: model names ("Gemma 3n E2B int4 + Gemma 3 270M FT")
- Center: per-layer latency when metadata arrives ("Student: 290ms | Classifier: 78ms | Matcher: 42ms | Worker: 425ms | Total: 847ms")
- Right: green dot + "Local" + "0 cloud calls"

Always visible, pinned to viewport bottom.

## DatumScheme Component (P1)

Three horizontal cards: A (primary) -> B (secondary) -> C (tertiary).
Each card: large datum letter, surface name, one-line reasoning.
Connected by arrows. Tertiary only renders if present.

## ReasoningPanel Component

Collapsed by default, toggle with chevron:
- Summary paragraph
- Manufacturing notes
- ASME section references as styled badges (e.g., "SS 7.2 -- Position")

## types.ts

Mirrors backend Pydantic schemas exactly:

```typescript
interface AnalyzeRequest {
  description: string;
  image?: File;
  manufacturing_process?: string;
  material?: string;
  context?: { assembly_info?: string; company_rules?: string };
}

interface FeatureRecord {
  feature_type: string;
  geometry: Record<string, string>;
  material_detected?: string;
  process_detected?: string;
}

interface DatumRecord {
  datum: string;
  surface: string;
  reasoning: string;
}

interface DatumScheme {
  primary: DatumRecord;
  secondary?: DatumRecord;
  tertiary?: DatumRecord;
}

interface GDTCallout {
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

interface ReasoningData {
  summary: string;
  manufacturing_notes: string;
  standards_references: string[];
}

interface AnalysisMetadata {
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
```

## Tailwind Config

Custom extensions:
- `fontFamily.mono`: `['JetBrains Mono', 'ui-monospace', 'monospace']`
- Colors for GD&T categories: `gdt.form`, `gdt.orientation`, `gdt.location`, `gdt.profile`, `gdt.runout`
- Dark background palette: slate-900 (app bg), slate-800 (panels), slate-700 (inputs)

No dark mode toggle — everything uses dark colors directly.

## Vite Config

Dev proxy: `/api` -> `http://localhost:8000` (FastAPI backend)

## Priority Tiers

P0 (must work for demo):
- Text input -> streaming results with FCF boxes
- StatusBar with "local, zero cloud"
- Preset buttons for quick demo clicks
- Dark theme, professional look

P1 (if time):
- Image upload with preview
- DatumScheme visual hierarchy
- Per-layer latency breakdown in StatusBar
- Warnings section
- ASME reference badges in ReasoningPanel

## Verification

1. `bun install` completes without errors
2. `bun run dev` starts Vite dev server
3. Preset button click populates textarea
4. Analyze button sends POST to `/api/analyze` (verify via browser Network tab or mock)
5. SSE events render progressively — shimmer for pending, fade-in for arrived
6. FCF boxes render with correct Unicode symbols, color coding, and borders
7. StatusBar shows model info and "0 cloud calls"
8. All renders correctly on macOS Chrome and Safari
