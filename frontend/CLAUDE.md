# Frontend Agent — CLAUDE.md

> You inherit root `CLAUDE.md`. Don't duplicate — this extends it with frontend-specific context.

## Scope

This module owns the React UI: feature input (text + image upload), SSE streaming display, feature control frame visual renderer, datum scheme visualization, reasoning panel, and system status. The frontend is a demo UI — optimized for the 2-minute hackathon presentation, not a production application.

## Tech Decisions (Already Made)

- **Framework:** React 18+ with TypeScript, scaffolded by Vite
- **Styling:** Tailwind CSS (utility-first, fast to iterate)
- **State:** React hooks (`useState`, `useReducer`) — no external state library
- **Streaming:** Native `EventSource` API for SSE consumption
- **Build:** Vite dev server for hackathon, `vite build` for production bundle
- **No component library.** Custom components — the GD&T rendering is domain-specific and no library covers it.

## File Responsibilities

### `src/App.tsx` — Root layout

- Two-panel layout: input panel (left) + results panel (right)
- Status bar at top or bottom (model status, latency, offline indicator)
- Manages top-level analysis state
- Triggers analysis via the `useSSE` hook

### `src/types.ts` — TypeScript types ⚠️ SHARED

- Mirrors `backend/api/schemas.py` exactly
- Types: `AnalyzeRequest`, `FeatureRecord`, `GDTClassification`, `DatumScheme`, `GDTCallout`, `GDTAnalysis`, `SSEEvent`
- **Coordinate with backend agent before changing any type**

### `src/components/FeatureInput.tsx` — Input panel

- Text area for natural language part description
- Image upload button (drag-and-drop or click) for photo input
- Image preview when uploaded
- "Analyze" button that triggers the SSE request
- Example inputs (clickable presets for demo: "Perpendicular boss", "Hole pattern", "Sealing surface")
- Manufacturing process and material dropdowns (optional overrides)

### `src/components/AnalysisStream.tsx` — Streaming results container

- Renders SSE events as they arrive, stage by stage
- Shows a progress indicator: which stages are complete, which are pending
- Each stage section expands as data arrives (feature extraction → datum → callouts → reasoning → warnings)
- Loading shimmer for pending stages

### `src/components/GDTCallout.tsx` — Feature control frame renderer

- Renders a single feature control frame in visual box notation:

  ```
  ┌───┬──────────┬───┬───┬───┐
  │ ⊕ │ ∅0.25 Ⓜ │ A │ B │ C │
  └───┴──────────┴───┴───┴───┘
  ```

- Each cell is a styled box with proper borders
- Geometric symbol in first cell, tolerance + modifier in second, datum refs in subsequent cells
- Must handle variable number of datum references (0 for form, 1-3 for others)
- Unicode symbols must render correctly: ⊕ ⊥ ▱ ○ ⌭ ∠ // ⌓ ⌒ ↗ ◎ ≡ Ⓜ Ⓛ ∅

### `src/components/DatumScheme.tsx` — Datum scheme display

- Shows the recommended datum scheme as a simple visual:
  - Datum A (primary): surface name + reasoning
  - Datum B (secondary): surface name + reasoning
  - Datum C (tertiary, if applicable): surface name + reasoning
- Visual hierarchy: A > B > C (size or emphasis)
- Each datum shows its reasoning on hover or in-line

### `src/components/ReasoningPanel.tsx` — Explanation display

- Renders the reasoning text for the full analysis
- Also renders per-callout reasoning (expandable)
- Manufacturing notes section
- ASME Y14.5 section references (clickable → `/api/standards/{code}` lookup)

### `src/components/StatusBar.tsx` — System status

- Model status: "Gemma 3n loaded ✓" / "Gemma 270M (fine-tuned) loaded ✓"
- Inference device: "local — M4 MacBook Air"
- Last analysis latency: "847ms (0 cloud calls)"
- Offline indicator: "🔒 Fully offline — ITAR safe"
- This bar is critical for the demo — judges need to SEE that it's local and fast

### `src/hooks/useSSE.ts` — SSE consumer hook

- Custom React hook that connects to `/api/analyze` SSE endpoint
- Manages connection lifecycle (open, message, error, close)
- Parses typed SSE events and dispatches to state
- Returns: `{ data, stage, isStreaming, error, startAnalysis }`
- Handles reconnection on error
- Abort capability (cancel in-flight analysis)

### `src/styles/` — Tailwind config + custom styles

- Tailwind config with custom colors for GD&T symbols (blue for form, green for orientation, red for location)
- Custom CSS for feature control frame box rendering (borders, cells)
- Responsive layout (but optimize for laptop screen — that's the demo device)

## Critical Rules

1. **Demo-first design.** Every component must look good in a 2-minute presentation. Favor visual impact over features.
2. **Streaming feel.** Results must appear progressively — never show a loading spinner for 1 second then dump everything. The streaming is the demo.
3. **Feature control frames must look professional.** These are the visual artifact that engineers recognize. If the FCF rendering is sloppy, the whole demo loses credibility.
4. **Status bar is always visible.** The judges need to see "local, zero cloud, fast" at all times.
5. **No loading states longer than 300ms without visual feedback.** Skeleton screens, shimmer effects, or stage progress indicators.
6. **Unicode GD&T symbols must render correctly.** Test on macOS Chrome and Safari. If a symbol doesn't render, use a fallback SVG/image.

## Design Principles

- Dark theme (engineering tools are typically dark — SolidWorks, Mastercam, etc.)
- Monospace font for feature control frames and tolerance values
- Clean sans-serif for reasoning text
- Generous whitespace — don't cram. Let the GD&T callouts breathe.
- Color coding: blue = form controls, green = orientation, red = location, purple = profile, orange = runout

## Common Pitfalls

- `EventSource` doesn't support POST — use `fetch()` with `ReadableStream` for POST + SSE, or have the analyze endpoint return an analysis ID that the EventSource connects to
- SSE events need `\n\n` delimiters — if streaming looks broken, check the backend event format
- Unicode rendering varies by font — test that ⊕ ⊥ ▱ ⌓ Ⓜ Ⓛ render correctly in your chosen typeface
- Vite dev server proxy config needed to forward `/api/*` to FastAPI backend (avoid CORS issues in dev)
- Image upload: convert to base64 client-side before sending to API (or use multipart/form-data)
- Don't over-animate — this is an engineering tool, not a consumer app. Subtle transitions, no bounce effects.
