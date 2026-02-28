# ToleranceAI — Technical Architecture

## System Overview

ToleranceAI is a 5-layer on-device AI pipeline that mirrors InstaLILY's production architecture. All inference is local — zero cloud calls. The system accepts multimodal input (photo, text, or FreeCAD screen captures), processes it through a fine-tuned student model, matches against ASME Y14.5 standards, enriches with manufacturing knowledge, and outputs formatted GD&T callouts with reasoning via SSE streaming.

## The 5-Layer Pipeline

```
INPUT ADAPTERS
  ├── Camera/Photo (Gemma 3n multimodal via mlx-vlm)
  ├── Text description (direct)
  └── FreeCAD screen capture (getDisplayMedia → frame → Gemma 3n via mlx-vlm)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: STUDENT — Feature Extraction                   │
│ Model: Gemma 3n E4B int4 via mlx-vlm (~3-4GB RAM)      │
│ Full multimodal: processes text, images, and video      │
│   frames via MobileNet-v5 encoder                       │
│ Input: raw photo or text                                │
│ Output: structured feature record (JSON)                │
│   { feature_type, geometry, material, process,          │
│     mating_condition, parent_surfaces }                 │
│ Latency target: <300ms                                  │
└────────────────────┬────────────────────────────────────┘
                     │ structured features
                     ▼
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: CLASSIFIER — GD&T Recommendation               │
│ Model: Gemma 3 270M, LoRA fine-tuned (~300MB RAM)       │
│ Input: structured feature record                        │
│ Output: GD&T classification                             │
│   { primary_control, symbol, tolerance_class,           │
│     datum_required, modifier, reasoning_key }           │
│ Latency target: <100ms                                  │
│ This is the fine-tuned model — the "before/after" demo  │
└────────────────────┬────────────────────────────────────┘
                     │ classification
                     ▼
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: MATCHER — Standards Lookup                     │
│ Model: all-MiniLM-L6-v2 (22M params, ~90MB)            │
│ Input: feature description + classification             │
│ Output: top-K relevant ASME Y14.5 sections + similar    │
│         tolerance schemes from the database             │
│ Method: cosine similarity on pre-computed embeddings    │
│ Latency target: <50ms                                   │
└────────────────────┬────────────────────────────────────┘
                     │ standards context
                     ▼
┌─────────────────────────────────────────────────────────┐
│ LAYER 4: BRAIN — Manufacturing Knowledge                │
│ Store: SQLite + JSON files                              │
│ Contents:                                               │
│   - ASME Y14.5-2018 rules (14 geometric characteristics,│
│     modifiers, datum rules, feature control frame rules)│
│   - Tolerance tables by manufacturing process + material│
│   - Datum scheme patterns (when to use which scheme)    │
│   - Material property tables                            │
│   - Company-specific rules (editable — mirrors          │
│     InstaBrain's editable knowledge)                    │
│ Latency target: <20ms                                   │
└────────────────────┬────────────────────────────────────┘
                     │ enriched context
                     ▼
┌─────────────────────────────────────────────────────────┐
│ LAYER 5: WORKER — Output Generation                     │
│ Model: Gemma 3n E4B int4 via mlx-vlm (same as Layer 1)  │
│ Input: features + classification + standards + knowledge│
│ Output: complete GD&T analysis (streamed via SSE)       │
│   - Feature control frames with standard notation       │
│   - Datum scheme with reasoning                         │
│   - Tolerance values with manufacturing justification   │
│   - Warnings and considerations                         │
│ Latency target: <500ms (streaming — first token <200ms) │
└─────────────────────────────────────────────────────────┘

OUTPUT ADAPTERS
  ├── Web UI (React — hackathon demo)
  ├── SolidWorks MCP (future — apply callouts to drawing)
  └── JSON API (integration with other tools)
```

## InstaLILY Architecture Mapping

| InstaLILY Production | ToleranceAI Layer | Mapping Rationale |
|----------------------|-------------------|-------------------|
| Gemini 2.5 Pro (teacher) | Gemini API (pre-hackathon) | Generate gold-standard training data with chain-of-thought |
| Gemma 7B fine-tuned (student) | Gemma 3n E2B + Gemma 270M fine-tuned | Feature extraction + domain classification |
| Distilled BERT 110M (matcher) | all-MiniLM-L6-v2 (22M) | Cosine similarity matching against standards catalog |
| InstaBrain (knowledge) | SQLite + JSON | ASME Y14.5 rules, tolerance tables, process capabilities |
| InstaWorkers (execution) | GD&T Worker pipeline | Autonomous analysis → formatted callouts + reasoning |
| ERP/CRM connectors | FreeCAD screen capture + future SolidWorks MCP | AI sees the engineer's CAD screen via browser screen capture. Production path: MCP connector. |

## API Design

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/analyze` | POST | Main: accept feature description or image, return streaming GD&T analysis |
| `/api/standards/{code}` | GET | Lookup specific ASME Y14.5 section by code |
| `/api/standards/search?q=` | GET | Semantic search across standards database |
| `/api/tolerances?process=&material=` | GET | Lookup typical tolerances for manufacturing process + material |
| `/api/stats` | GET | Model status, standards count, latency stats, uptime |
| `/api/health` | GET | Liveness check — confirms Ollama + models are loaded |

### POST `/api/analyze` — Request

```
Content-Type: multipart/form-data OR application/json

{
  "description": "string — natural language feature description",
  "image": "file — optional photo/sketch (multipart)",
  "manufacturing_process": "string — optional override (cnc_milling, injection_molding, etc.)",
  "material": "string — optional override (AL6061-T6, steel_4140, etc.)",
  "context": {
    "assembly_info": "string — optional mating/assembly context",
    "company_rules": "string — optional company-specific tolerancing rules"
  }
}
```

For SolidWorks MCP input (future), a separate adapter normalizes MCP feature data into this same schema.

### POST `/api/analyze` — Response (SSE Stream)

Server-Sent Events stream with typed stages:

**Stage 1: `feature_extraction`**

```
event: feature_extraction
data: {
  "features": [
    {
      "feature_type": "hole_pattern",
      "count": 4,
      "geometry": {"diameter": "6.0mm", "pattern": "bolt_circle", "pcd": "50mm"},
      "parent_surface": "planar_mounting_face"
    }
  ],
  "material_detected": "mild_steel",
  "process_detected": "sheet_metal_laser_cut"
}
```

**Stage 2: `datum_recommendation`**

```
event: datum_recommendation
data: {
  "datum_scheme": {
    "primary": {"datum": "A", "surface": "mounting_face", "reasoning": "Largest flat surface, primary assembly contact, 3 points of constraint"},
    "secondary": {"datum": "B", "surface": "locating_hole", "reasoning": "Perpendicular to A, constrains 2 DOF, aligns with assembly locating pin"},
    "tertiary": {"datum": "C", "surface": "edge", "reasoning": "Optional — constrains rotation, only needed if hole pattern orientation matters"}
  }
}
```

**Stage 3: `gdt_callouts`**

```
event: gdt_callouts
data: {
  "callouts": [
    {
      "feature": "4x M6 bolt holes",
      "symbol": "⊕",
      "symbol_name": "position",
      "tolerance_value": "∅0.25",
      "unit": "mm",
      "modifier": "MMC",
      "modifier_symbol": "Ⓜ",
      "datum_references": ["A", "B"],
      "feature_control_frame": "|⊕| ∅0.25 Ⓜ | A | B |",
      "reasoning": "Position control for bolt pattern. MMC modifier appropriate for clearance-fit fastener holes — allows bonus tolerance as holes depart from MMC size."
    },
    {
      "feature": "mounting face",
      "symbol": "▱",
      "symbol_name": "flatness",
      "tolerance_value": "0.1",
      "unit": "mm",
      "modifier": null,
      "datum_references": [],
      "feature_control_frame": "|▱| 0.1 |",
      "reasoning": "Flatness on primary datum surface ensures proper seating. Form control — no datum reference needed."
    }
  ]
}
```

**Stage 4: `reasoning`**

```
event: reasoning
data: {
  "summary": "This part requires position control on the bolt pattern for assembly alignment, with flatness on the datum face for proper seating...",
  "manufacturing_notes": "Sheet metal laser cutting typically holds ±0.1mm on hole position. Specified ∅0.25mm position tolerance provides 2.5x margin.",
  "standards_references": ["ASME Y14.5-2018 §7.2 — Position", "ASME Y14.5-2018 §5.4 — Flatness"]
}
```

**Stage 5: `warnings`**

```
event: warnings
data: {
  "warnings": [
    "Consider adding perpendicularity callout on bolt holes if thread engagement depth is critical",
    "Laser-cut holes may need reaming if position tolerance is tighter than ±0.1mm"
  ]
}
```

**Stage 6: `analysis_complete`**

```
event: analysis_complete
data: {
  "analysis_id": "uuid",
  "metadata": {
    "inference_device": "local — Gemma 3n E2B int4 + Gemma 270M fine-tuned",
    "total_latency_ms": 847,
    "student_latency_ms": 290,
    "classifier_latency_ms": 78,
    "matcher_latency_ms": 42,
    "brain_latency_ms": 12,
    "worker_latency_ms": 425,
    "cloud_calls": 0,
    "connectivity_required": false
  }
}
```

## Data Model

### GDTAnalysis (Core Output Object)

```
GDTAnalysis:
  id: str (uuid)
  input_description: str
  input_image_hash: str | null
  features_extracted:
    - feature_type: enum (hole, boss, surface, slot, groove, shaft, pattern, bend)
    - geometry: dict (dimensions — diameter, length, width, depth, angle, count, pcd)
    - material: str
    - manufacturing_process: str
    - mating_condition: str | null
    - parent_surface: str | null
  datum_scheme:
    primary: {datum: str, surface: str, reasoning: str}
    secondary: {datum: str, surface: str, reasoning: str} | null
    tertiary: {datum: str, surface: str, reasoning: str} | null
  callouts:
    - feature: str
    - symbol: str (⊥, ⊕, ⌓, ▱, ○, ⌭, ∠, //, ◎, ≡, ↗, etc.)
    - symbol_name: str
    - tolerance_value: str
    - unit: str (mm or in)
    - modifier: str | null (MMC, LMC, RFS)
    - modifier_symbol: str | null (Ⓜ, Ⓛ)
    - datum_references: list[str]
    - feature_control_frame: str (formatted: |⊕| ∅0.25 Ⓜ | A | B |)
    - reasoning: str
  warnings: list[str]
  reasoning_summary: str
  manufacturing_notes: str
  standards_references: list[str]
  metadata:
    inference_device: str
    total_latency_ms: int
    cloud_calls: 0 (always)
    connectivity_required: false (always)
```

### ASME Y14.5 Knowledge Schema

```
GeometricCharacteristic:
  symbol: str
  name: str
  category: enum (form, orientation, location, profile, runout)
  datum_required: bool
  datum_optional: bool
  applicable_modifiers: list[str]
  applicable_feature_types: list[str]
  rules: list[str]  # ASME Y14.5 section references
  common_mistakes: list[str]
  when_to_use: str
  when_NOT_to_use: str

ToleranceTable:
  manufacturing_process: str
  material_class: str
  feature_type: str
  typical_range_mm: {min: float, max: float}
  achievable_best_mm: float
  notes: str

DatumPattern:
  pattern_name: str
  description: str
  primary_surface_type: str
  secondary_surface_type: str
  tertiary_surface_type: str | null
  when_to_use: list[str]
  example_parts: list[str]
  common_mistakes: list[str]
```

## Performance Targets

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| End-to-end latency | < 1 second | First input to `analysis_complete` |
| First token (streaming) | < 300ms | First SSE event sent |
| Gemma 3n inference | via mlx-vlm, ~80-120 tok/s on M4 | Student + Worker combined |
| Gemma 270M classification | < 100ms | Classifier layer |
| Standards matching | < 50ms | Embedding cosine similarity |
| Brain lookup | < 20ms | SQLite query |
| Cloud calls during inference | 0 | Always |
| Model RAM (total) | < 5GB | Gemma 3n E4B + 270M + MiniLM |
| Cold start (first inference) | < 10s | Model loading via Ollama |

## FreeCAD Screen Capture Integration (Hackathon Demo)

### How It Works

The browser's `getDisplayMedia()` API captures the FreeCAD window as a live video stream. Frames are extracted and sent to Gemma 3n E4B for visual feature extraction.

Flow:
1. User opens FreeCAD with a part model in a separate window
2. In the web app, user clicks "Connect to CAD" → browser `getDisplayMedia()` picker
3. User selects the FreeCAD window
4. Live preview thumbnail appears in the left panel
5. P0 — Snapshot: User clicks "Capture & Analyze" → single frame extracted → JPEG → POST /api/analyze
6. P1 — Watch mode: Auto-capture every 3s, pixel-diff change detection, auto-trigger analysis on significant changes

### Why FreeCAD

- Free, open-source, runs locally on macOS
- No subscription required (unlike SolidWorks, OnShape)
- Fully offline — no cloud dependency
- Rich enough UI to look like a real CAD tool in demo
- Python API available for future deeper integration

### On-Device Story

The screen capture stays entirely local. The captured frames are processed by Gemma 3n E4B running on the same machine via mlx-vlm. No frame data ever leaves the device. This is critical for ITAR-controlled engineering drawings.

## SolidWorks MCP Integration (Production Path)

### Input Adapter: SolidWorks → Normalized Features

The SolidWorks MCP server (Python + C#, Windows) exposes:

- **Feature tree:** Every boss, hole, pocket, fillet — typed and dimensioned
- **Assembly mates:** Which faces contact, concentric relationships, parallel constraints
- **Material properties:** From SolidWorks material library
- **Custom properties:** Often includes manufacturing notes, part number, revision

The MCP adapter normalizes this into the same feature input format used by the text/image paths:

```
SolidWorks MCP data:
  Feature: Boss-Extrude3
  Type: cylinder
  Diameter: 12.00mm
  Height: 8.00mm
  Parent face: Face<mounting_surface>
  Material: AL6061-T6 (from SW material)
  Assembly mate: concentric with BearingBore@Housing

        ↓ normalize ↓

Pipeline input:
  feature_type: "boss"
  geometry: {diameter: 12.0, height: 8.0, unit: "mm"}
  material: "AL6061-T6"
  mating_condition: "concentric_bearing_bore"
  parent_surface: "planar_mounting_face"
```

Assembly mates are especially valuable — they directly inform datum selection:

- Planar mate → likely primary datum (largest contact surface)
- Concentric mate → bearing/shaft relationship → runout or position control
- Coincident mate → alignment requirement → position or profile control

### Output Adapter: Results → SolidWorks Drawing

In production, the Worker output can be pushed back to SolidWorks via MCP:

- Add annotation notes with feature control frames
- Suggest datum feature symbols on appropriate surfaces
- Create dimension callouts with tolerance values

This is the "InstaWorker executing inside the enterprise tool" pattern.

## Optional: NanoClaw Orchestration (P2)

NanoClaw (Anthropic Agent SDK, containerized, ~500 LOC) could serve as the outer orchestration layer:

- Spawn parallel agents: `feature_scanner`, `standard_lookup`, `tolerance_calc`, `callout_gen`
- Each agent calls Gemma/MiniLM/SQLite as tools
- NanoClaw manages agent coordination and result assembly
- Runs in Apple Container on macOS (M4 compatible)

This maps to InstaLILY's worker swarm concept and adds an impressive "agentic behavior" demo. However, it adds a dependency on Claude/Anthropic SDK alongside Gemma, so it's P2 — designed for but not required in the hackathon demo.

## Deployment

### Hackathon (M4 MacBook Air 32GB)

```
Ollama (local)
  └── gemma3:270m-finetuned (LoRA, ~300MB) — classifier only

mlx-vlm (local, Apple Silicon native)
  └── gemma-3n-E4B-it-4bit (~3-4GB) — student + worker, full multimodal

Python process (FastAPI)
  ├── sentence-transformers (MiniLM, ~90MB)
  ├── SQLite (brain DB, <10MB)
  └── SSE streaming server

Node process (Vite dev server)
  └── React frontend

Total RAM: ~4.5GB for all models + services
```

### Production (Engineer's Workstation)

```
Same as above, plus:
  └── SolidWorks MCP server (Python + C#, Windows)
      ├── Reads: feature tree, mates, materials
      └── Writes: GD&T annotations to drawing
```

### Fine-Tuning (GCP VM — Pre-Hackathon)

```
NVIDIA RTX PRO 6000 Blackwell (102GB VRAM)
  ├── LoRA fine-tune Gemma 3 270M on GD&T classification
  ├── Generate synthetic training data evaluation
  └── Pre-compute standard embeddings

VM: 104.197.52.110 (hackathon user)
Not used during demo — training artifacts deployed to M4 laptop.
```
