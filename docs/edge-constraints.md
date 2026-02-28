# Edge Constraints — Zero Cloud Inference

## Non-Negotiable Rule

During inference (the `/api/analyze` pipeline and all related endpoints), the system makes ZERO network calls. All processing is local:

- Gemma 3n E2B int4 → served via Ollama on localhost:11434
- Gemma 3 270M fine-tuned → served via Ollama on localhost:11434
- all-MiniLM-L6-v2 → loaded in-process by sentence-transformers
- SQLite brain → local file on disk
- Pre-computed embeddings → local NPZ file

## What "Zero Cloud" Means

- No HTTP calls to any external API during inference
- No DNS resolution to external hosts
- System must function identically with airplane mode enabled
- The word "cloud" should not appear in any import statement or runtime dependency

## Why This Matters

1. **ITAR compliance:** Defense/aerospace engineering drawings cannot legally leave a secure network
2. **Proprietary IP:** Tolerancing decisions reveal manufacturing capabilities
3. **Shop floor:** Manufacturing environments have unreliable internet
4. **Hackathon scoring:** Judges (especially Sai, CTO) will specifically look for this
5. **InstaLILY alignment:** Demonstrates edge-deployable architecture

## Exceptions (Pre-Hackathon Only)

- `scripts/generate_synthetic_data.py` calls Gemini 2.5 Pro API — this is training data generation, NOT inference
- Downloading models via `ollama pull` requires network — this happens once, before demo
- `pip install` and `npm install` require network — build-time dependency, not runtime

## Verification

Run `scripts/validate_pipeline.py` with network disconnected. If it passes, edge constraints are met. If any step fails due to network dependency, that step must be fixed before demo.

## Hardware Target

- Apple M4 MacBook Air, 32GB RAM
- Gemma 3n E2B int4: ~2GB RAM, 30-50 tok/s with ANE
- Gemma 270M fine-tuned: ~300MB RAM
- MiniLM embedder: ~90MB RAM
- Total model footprint: <3GB
- Must leave >10GB free for OS + SolidWorks (future production use case)

## Latency Budgets

| Component | Budget | Notes |
|-----------|--------|-------|
| Gemma 3n (Student — feature extraction) | 300ms | Includes image processing if multimodal |
| Gemma 270M (Classifier) | 100ms | Fine-tuned, fast on small model |
| MiniLM (Matcher) | 50ms | Pre-computed embeddings, cosine similarity only |
| SQLite (Brain) | 20ms | Single indexed query |
| Gemma 3n (Worker — output generation) | 500ms | Longest step, but streaming starts immediately |
| **Total end-to-end** | **<1000ms** | First SSE token within 300ms |
