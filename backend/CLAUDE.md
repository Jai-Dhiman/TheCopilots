# Backend Agent — CLAUDE.md

> You inherit root `CLAUDE.md`. Don't duplicate — this extends it with backend-specific context.

## Scope

This module owns the FastAPI server, Ollama model clients (Gemma 3n + Gemma 270M), sentence-transformers matcher, SQLite brain lookups, and SSE streaming infrastructure. You own the full pipeline from HTTP request to SSE response.

## Tech Decisions (Already Made)

- **Framework:** FastAPI with async/await throughout
- **Model serving:** Ollama HTTP API (localhost:11434) for both Gemma models
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2`, loaded in-process
- **Database:** SQLite via `aiosqlite` for async brain lookups
- **Streaming:** Server-Sent Events via `sse-starlette` or manual `StreamingResponse`
- **Image handling:** Accept multipart/form-data, pass base64 to Ollama multimodal endpoint

## File Responsibilities

### `api/main.py` — FastAPI app setup

- App creation with lifespan (load models on startup, cleanup on shutdown)
- CORS middleware (allow frontend dev server)
- Mount routes from `routes.py`
- Health check endpoint
- DO NOT put business logic here

### `api/schemas.py` — Pydantic models ⚠️ SHARED

- Request/response models for all endpoints
- `AnalyzeRequest`, `FeatureRecord`, `GDTClassification`, `DatumScheme`, `GDTCallout`, `GDTAnalysis`
- These models define the API contract — `frontend/src/types.ts` must mirror them
- **Coordinate with frontend agent before changing any schema**

### `api/routes.py` — Route handlers

- `POST /api/analyze` — main analysis pipeline, returns SSE stream
- `GET /api/standards/{code}` — direct standard section lookup
- `GET /api/standards/search?q=` — semantic search
- `GET /api/tolerances?process=&material=` — tolerance table lookup
- `GET /api/stats` — model status, latency stats
- `GET /api/health` — liveness (Ollama + models loaded?)

### `api/streaming.py` — SSE helpers

- Functions to format SSE events with typed stage names
- Event types: `feature_extraction`, `datum_recommendation`, `gdt_callouts`, `reasoning`, `warnings`, `analysis_complete`
- Error event type for graceful failure

### `models/gemma.py` — Ollama client

- Async client for Ollama HTTP API
- Two model interfaces: `gemma3n_extract()` (vision + text → features) and `gemma3n_generate()` (context → full output)
- Handles both text-only and multimodal (image + text) requests
- Timeout handling: 5s max per inference call
- Model availability check on startup

### `models/embedder.py` — Sentence-transformers matching

- Load `all-MiniLM-L6-v2` on startup
- `match_standards(query, top_k=5)` — cosine similarity against pre-computed ASME embeddings
- `match_tolerance_schemes(features, top_k=3)` — find similar tolerance patterns
- Embeddings loaded from `data/embeddings/standards_embeddings.npz`

### `models/prompts.py` — System prompts and few-shot examples

- System prompt for Gemma 3n feature extraction
- System prompt for Gemma 3n output generation (worker)
- Few-shot examples for GD&T analysis (3-5 gold-standard input → output pairs)
- Prompt templates are the primary tuning lever for Gemma 3n quality

### `brain/database.py` — SQLite connection

- Async connection pool via `aiosqlite`
- Schema creation / migration on startup
- Connection lifecycle management

### `brain/lookup.py` — Standard and datum logic

- `lookup_standard(code)` — fetch ASME Y14.5 section by identifier
- `lookup_datum_pattern(features)` — match features to common datum scheme patterns
- `get_geometric_characteristic(symbol)` — full rule set for a given GD&T symbol

### `brain/manufacturing.py` — Process capability tables

- `get_tolerance_range(process, material, feature_type)` — typical achievable tolerance
- `get_process_capability(process)` — full process capability profile
- `get_material_properties(material)` — machinability, thermal expansion, common processes

## Critical Rules

1. **All Ollama calls are async.** Never block the event loop.
2. **SSE streaming is mandatory** for `/api/analyze`. Never buffer the full response.
3. **Zero cloud calls.** Ollama runs locally. Sentence-transformers runs in-process. SQLite is a file. If you're making an HTTP call to anything other than localhost:11434 (Ollama), you're wrong.
4. **Latency is king.** Measure every layer. Include timing in `analysis_complete` metadata.
5. **Graceful degradation.** If Ollama is down, return a clear error — don't crash. If confidence is low, return alternatives.

## Dependencies

```
fastapi
uvicorn[standard]
sse-starlette
pydantic>=2.0
aiosqlite
httpx  # async HTTP client for Ollama
sentence-transformers
numpy
python-multipart  # for image upload
pillow  # image preprocessing
```

## Common Pitfalls

- Ollama's `/api/generate` vs `/api/chat` endpoints have different schemas — use `/api/chat` for conversation format
- Gemma 3n multimodal expects images as base64 in the `images` field of the message
- `sentence-transformers` model loading is slow (~3s) — load once on startup, not per-request
- SQLite `aiosqlite` connections should be pooled, not created per query
- SSE requires `Cache-Control: no-cache` and `Connection: keep-alive` headers
- CORS must allow the frontend dev server origin (typically `http://localhost:5173`)
