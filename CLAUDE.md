# ToleranceAI — GD&T Copilot for Mechanical Engineers

AI-powered GD&T (Geometric Dimensioning & Tolerancing) copilot that takes part features — from photos, text descriptions, or SolidWorks models via MCP — and generates ASME Y14.5-2018 compliant callouts with reasoning. Built for the Google DeepMind x InstaLILY AI Hackathon.

## Architecture (Mirrors InstaLILY's 5-Layer Stack)

| Layer | Component | Role |
|-------|-----------|------|
| **Teacher** | Gemini 2.5 Pro API | Pre-hackathon synthetic data generation |
| **Student** | Gemma 3n E2B int4 (Ollama) | Visual + text feature extraction, final output generation |
| **Classifier** | Gemma 3 270M (LoRA fine-tuned) | Feature → GD&T symbol/tolerance class/datum requirement |
| **Matcher** | all-MiniLM-L6-v2 (sentence-transformers) | Semantic lookup of ASME Y14.5 sections |
| **Brain** | SQLite + JSON | ASME Y14.5 rules, tolerance tables, datum patterns, process capabilities |
| **Worker** | GD&T InstaWorker pipeline | Orchestrates full analysis → formatted callouts + reasoning |

## Tech Stack

- **Edge models:** Gemma 3n E2B int4 (~2GB) + Gemma 3 270M fine-tuned (~300MB), served via Ollama
- **Matching:** sentence-transformers all-MiniLM-L6-v2 (22M params)
- **Backend:** Python 3.11+ / FastAPI, async SSE streaming
- **Frontend:** React (Vite) + TypeScript
- **Knowledge DB:** SQLite (tolerance tables, datum patterns, ASME rules)
- **Hardware target:** M4 MacBook Air 32GB, zero cloud calls during inference

## Build & Run

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn api.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Models (must be running)
ollama pull gemma3n:e2b
ollama pull gemma3:270m  # or custom fine-tuned tag

# Seed data
python scripts/seed_database.py
python scripts/embed_standards.py
```

## Testing

```bash
cd backend && pytest tests/ -v
python scripts/validate_pipeline.py  # end-to-end smoke test
```

## Project Structure

- `backend/` — FastAPI server, Ollama clients, brain lookups, SSE streaming
- `frontend/` — React UI, feature control frame renderer, streaming display
- `data/` — ASME Y14.5 rules, tolerance tables, embeddings, synthetic training data
- `scripts/` — Gemini data gen, embedding pipeline, DB seeder, validation

## Critical Conventions

- **Edge-first:** Zero cloud calls during inference. ALL processing local. Non-negotiable.
- **ASME Y14.5-2018** is the governing standard. All GD&T output must comply.
- **Feature control frames** use standard notation: `|symbol| tolerance modifier | datum_refs |`
- **Streaming SSE** for all analysis responses — never block on full completion.

## Shared Files (coordinate before editing)

- `backend/api/schemas.py` ↔ `frontend/src/types.ts` — API contract
- `data/standards/asme_y14_5.json` — referenced by backend brain + matcher + scripts

## Agent Routing

Each agent works within its module boundary. Lead agent coordinates cross-module work.
Parallel dispatch when tasks are independent. Sequential when shared files are involved.
