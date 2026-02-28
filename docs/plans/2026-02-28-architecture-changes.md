# Architecture Changes: Screen Capture + mlx-vlm

> Summary of changes from the original design. Each section targets one agent.

---

## Backend Agent Changes

### What changed

1. **Gemma 3n serving: Ollama -> mlx-vlm.** Ollama does not support Gemma 3n vision (text-only). We now use `mlx-vlm` (Apple Silicon native MLX) to serve Gemma 3n E4B with full multimodal support (images + video frames via MobileNet-v5 encoder).

2. **Model upgrade: E2B -> E4B.** Gemma 3n E4B (~3-4GB int4) replaces E2B (~2GB). Better accuracy, still fits in 32GB M4 MacBook. Model ID: `mlx-community/gemma-3n-E4B-it-4bit`.

3. **Dual model serving.** Two different serving backends:
   - `mlx-vlm` Python API for Gemma 3n E4B (student + worker layers) — handles text AND image input
   - Ollama `localhost:11434` for Gemma 3 270M (classifier layer) — text-to-text only, unchanged

4. **Image input from screen capture.** The `/api/analyze` endpoint already accepts image input (multipart). No API change needed. The frontend sends JPEG blobs captured from the FreeCAD screen — the backend treats them identically to camera photos.

5. **New dependency:** `mlx-vlm` added to `pyproject.toml`.

### What did NOT change

- API contract (`/api/analyze` request/response) — unchanged
- SSE streaming stages — unchanged
- Classifier (270M via Ollama) — unchanged
- Matcher (MiniLM in-process) — unchanged
- Brain (SQLite) — unchanged
- All schemas — unchanged

### Key implementation detail

```python
# mlx-vlm usage pattern for image input
from mlx_vlm import load, generate

model, processor = load("mlx-community/gemma-3n-E4B-it-4bit")
output = generate(model, processor, image=frame_path, prompt=prompt, max_tokens=500)
```

Replace the Ollama httpx calls in the student and worker layers with mlx-vlm calls. Keep Ollama for the classifier layer only.

---

## Frontend Agent Changes

### What changed

1. **New tab in FeatureInput: "CAD Capture".** The left panel gets a tabbed interface:
   - Tab 1: "Text" — existing textarea + presets (unchanged)
   - Tab 2: "CAD Capture" — screen capture from FreeCAD

2. **New hook: `useScreenCapture.ts`.** Manages the `getDisplayMedia()` lifecycle:
   - `connect()` — triggers browser screen share picker, attaches stream to `<video>` element
   - `captureFrame()` — draws video frame to hidden `<canvas>`, exports as JPEG blob (quality 0.85)
   - `disconnect()` — stops MediaStream tracks
   - Returns: `{ status, videoRef, connect, captureFrame, disconnect }`

3. **New component: `ScreenCapture.tsx`.** Renders inside the "CAD Capture" tab:
   - Disconnected: "Connect to CAD" button
   - Connected: live `<video>` preview of FreeCAD window + "Capture & Analyze" button + "Disconnect" button
   - P2: "Auto-analyze" toggle with pixel-diff change detection (3s cooldown)

4. **StatusBar model name update:** "Gemma 3n E4B int4 (mlx-vlm) + Gemma 3 270M FT"

### What did NOT change

- AnalysisStream, GDTCallout, DatumScheme, ReasoningPanel — all unchanged
- useSSE hook — unchanged (still receives JPEG blob from FeatureInput, sends to `/api/analyze`)
- types.ts — unchanged (AnalyzeRequest already has `image?: File`)
- All styling/theme — unchanged

### Frame capture flow (the core ~40 lines)

```
User clicks "Connect to CAD"
  -> getDisplayMedia({ video: true })
  -> user picks FreeCAD window
  -> stream attached to <video> element (live preview)

User clicks "Capture & Analyze"
  -> canvas.drawImage(video, 0, 0)
  -> canvas.toBlob('image/jpeg', 0.85)
  -> blob passed to onAnalyze(blob) -> useSSE.analyze({ image: blob })
  -> normal SSE flow from here
```

---

## Data Agent Changes

### What changed

1. **Fine-tuning moves to GCP VM.** The VM at `104.197.52.110` has:
   - NVIDIA RTX PRO 6000 Blackwell, 102GB VRAM
   - PyTorch 2.7.1+cu128 pre-installed
   - 176GB RAM, 48 CPU cores, 170GB disk
   - SSH: `sshpass -p '7937da6a' ssh hackathon@104.197.52.110`

2. **VM is for pre-hackathon only.** Use it for:
   - LoRA fine-tuning Gemma 3 270M on GD&T classification data
   - Evaluating synthetic training data quality
   - Pre-computing standard embeddings (can also run locally)
   - NOT used during inference or demo

3. **Model artifacts flow:** Fine-tune on VM -> export LoRA adapter weights -> download to M4 laptop -> load via Ollama (270M) or mlx-vlm (if fine-tuning E4B).

### What did NOT change

- ASME Y14.5 knowledge base (SQLite + JSON) — unchanged
- Embedding pipeline (all-MiniLM-L6-v2) — unchanged
- Synthetic data generation scripts — unchanged
- Tolerance tables, datum patterns — unchanged

### VM setup for fine-tuning

```bash
# SSH in
sshpass -p '7937da6a' ssh hackathon@104.197.52.110

# Install fine-tuning deps (not pre-installed)
pip install transformers accelerate bitsandbytes peft datasets

# PyTorch + CUDA already available
python -c "import torch; print(torch.cuda.is_available())"  # True
```

---

## Summary of all file changes

| File | Status |
|------|--------|
| `CLAUDE.md` | Updated — E4B, mlx-vlm, bun, VM, screen capture |
| `docs/Architecture.md` | Updated — all layers, input adapters, deployment, new FreeCAD section |
| `docs/PRD.md` | Updated — FR-2, new FR-11a (screen capture P1), NFR-3 memory |
| `docs/edge-constraints.md` | Updated — mlx-vlm, screen capture, VM section, E4B memory |
| `docs/demo-priorities.md` | Updated — screen capture in P1, watch mode in P2, judge notes |
| `docs/Overview.md` | Updated — input paths, demo script, architecture reveal, user journey |
| `docs/plans/2026-02-28-frontend-design.md` | Updated — tabs, useScreenCapture, ScreenCapture component, priorities |
| `docs/plans/2026-02-28-backend-pipeline.md` | Updated — mlx-vlm serving, dual model setup, deps |
| `docs/GDT-formatting.md` | No changes needed |
