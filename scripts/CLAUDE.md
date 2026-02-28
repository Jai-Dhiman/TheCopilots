# Scripts Agent — CLAUDE.md

> You inherit root `CLAUDE.md`. Don't duplicate — this extends it with scripts-specific context.

## Scope

This module owns pre-hackathon data pipelines: synthetic training data generation via Gemini, embedding computation, database seeding, fine-tuning orchestration, and end-to-end pipeline validation. These scripts run BEFORE hackathon day — they prepare the knowledge base and fine-tuned model.

## Tech Decisions (Already Made)

- **Synthetic data generation:** Gemini 2.5 Pro API via `google-generativeai` Python SDK
- **Embedding computation:** `sentence-transformers` all-MiniLM-L6-v2
- **Fine-tuning:** Unsloth (LoRA on Gemma 270M), targeting Apple Silicon M4
- **Database seeding:** Python → SQLite, loading from JSON files in `data/standards/`
- **Validation:** Python script that runs the full pipeline end-to-end with test inputs

## File Responsibilities

### `generate_synthetic_data.py` — Gemini teacher pipeline

Uses Gemini 2.5 Pro to generate high-quality training pairs:

- Input: parameterized prompts covering all 14 GD&T characteristics, common manufacturing processes, common part types
- Output: JSONL written to `data/synthetic/training_pairs.jsonl`
- Each pair: structured feature input → GD&T classification + full output with reasoning
- Target: 500+ pairs with diverse coverage
- Includes chain-of-thought reasoning (mirrors InstaLILY's teacher labeling approach)

Key generation parameters:

- Vary feature types: hole, boss, surface, slot, groove, shaft, pattern, bend
- Vary manufacturing: CNC milling, turning, injection molding, sheet metal, casting, 3D printing, grinding
- Vary materials: aluminum alloys, steels, stainless, titanium, plastics, cast iron
- Vary complexity: single feature, multi-feature with datum scheme, assembly context
- Include edge cases: ambiguous inputs, features where common mistakes occur

Quality controls:

- Validate each generated pair against ASME Y14.5 rules before saving
- Reject pairs where datum is specified for form controls (invalid)
- Reject pairs where tolerance value is outside manufacturing capability range
- Log rejection rate — if >20%, the Gemini prompt needs tuning

### `embed_standards.py` — Embedding pipeline

Pre-computes 384-dim embeddings for all ASME Y14.5 sections:

- Input: `data/standards/asme_y14_5.json`
- Output: `data/embeddings/standards_embeddings.npz`
- Each section's name + description + rules text → single embedding
- Also embeds common search queries for better retrieval

Process:

1. Load asme_y14_5.json
2. For each section: concatenate name, description, rules, when_to_use
3. Encode with all-MiniLM-L6-v2
4. Save as NPZ with section IDs as keys

### `seed_database.py` — SQLite initialization

Creates and populates the brain database:

- Input: all JSON files in `data/standards/`
- Output: SQLite database (path configured, default `data/brain.db`)
- Tables: `geometric_characteristics`, `tolerance_tables`, `material_properties`, `datum_patterns`
- Includes FTS5 full-text search index on rules text
- Idempotent: drops and recreates tables on each run

### `validate_pipeline.py` — End-to-end smoke test

Runs the full analysis pipeline with test inputs and validates output quality:

- Requires: Ollama running with both models loaded, database seeded, embeddings computed
- Runs the 5 acceptance test scenarios from the PRD
- Checks: correct symbols, appropriate datums, reasonable tolerance values, valid FCF format
- Reports: latency per stage, accuracy on known-good outputs, any failures
- Exit code 0 = all scenarios pass, exit code 1 = failures (with details)

This is the script you run right before the demo to verify everything works.

## Critical Rules

1. **Gemini API calls are PRE-HACKATHON only.** These scripts use cloud APIs for data preparation. The actual product (backend/) makes zero cloud calls.
2. **Training data quality matters more than quantity.** Validate every generated pair. Bad training data = bad fine-tuned model.
3. **Embeddings must be regenerated if standards data changes.** If someone edits `asme_y14_5.json`, run `embed_standards.py` again.
4. **`validate_pipeline.py` is the confidence gate.** If it doesn't pass, you're not ready to demo.
5. **Fine-tuning targets Gemma 3 270M, NOT Gemma 3n E2B.** The 270M model is the classifier. Gemma 3n is used with prompting only.

## Dependencies

```
google-generativeai  # Gemini API client (data gen only)
sentence-transformers
numpy
unsloth  # LoRA fine-tuning
torch  # required by unsloth
datasets  # HuggingFace datasets for training format
tqdm  # progress bars
```

## Fine-Tuning Notes (for the 270M model)

### Training format

Convert JSONL training pairs into instruction-tuning format:

```
<instruction>Given this part feature, classify the appropriate GD&T control.</instruction>
<input>{structured feature JSON}</input>
<output>{classification JSON}</output>
```

### LoRA config (recommended starting point)

- Rank: 16
- Alpha: 32
- Target modules: q_proj, v_proj
- Epochs: 3-5
- Learning rate: 2e-4
- Batch size: 4 (M4 Air memory constrained)

### Evaluation

- Hold out 10% of training data for validation
- Key metrics: symbol accuracy, datum_required accuracy, modifier accuracy
- Compare base vs. fine-tuned on the same held-out set
- Save comparison results — this IS the demo

## Common Pitfalls

- Gemini API has rate limits — add retry logic with exponential backoff
- `sentence-transformers` first run downloads the model (~90MB) — run once before hackathon to cache
- Unsloth on Apple Silicon needs specific torch version — test installation before hackathon night
- SQLite `INSERT OR REPLACE` is your friend for idempotent seeding
- NPZ files can be large — `.claudeignore` already excludes them from agent context
