# Demo Priorities — Hackathon Time Management

## Priority Tiers

### P0 — Demo Fails Without This (Hours 0-4)

These must work perfectly. If any P0 item is broken, stop everything else and fix it.

1. **Gemma 3n processes text input → structured features** (backend)
2. **Gemma 270M fine-tuned classifies features → GD&T recommendation** (backend)
   - AND: base vs. fine-tuned comparison is visually clear
3. **Brain lookup returns correct tolerance values and datum patterns** (backend)
4. **SSE streaming sends progressive results** (backend)
5. **Frontend renders streaming results with feature control frames** (frontend)
6. **Feature control frames render correctly with Unicode symbols** (frontend)
7. **Status bar shows "local, zero cloud, latency"** (frontend)
8. **End-to-end: type description → see GD&T callouts with reasoning** (integration)

### P1 — Significantly Better Demo (Hours 4-6)

Build these after ALL P0 items are solid and tested.

1. **Image input path** — photo of desk bracket → feature extraction → GD&T
2. **Warnings and considerations** — "your process can hold X, consider adding Y"
3. **Example input presets** — clickable buttons for demo scenarios (perpendicular boss, hole pattern, etc.)
4. **Standards search** — semantic lookup of ASME Y14.5 sections
5. **Datum scheme visualization** — visual display of A/B/C datum hierarchy
6. **Latency breakdown** — show per-layer timing in metadata

### P2 — Impressive If Time Allows (Hours 6-7)

Only if P0 and P1 are polished and demo-rehearsed.

1. **NanoClaw orchestration** — agent swarm for parallel processing
2. **Manufacturing process selector** — dropdown overrides with visual process capability chart
3. **Multiple callout comparison** — show alternative GD&T approaches with tradeoffs
4. **Standards reference linking** — click ASME section reference → see full rule text
5. **Dark theme polish** — professional engineering-tool aesthetic

### P3 — Architecture Only, Don't Build (Document in ARCHITECTURE.md)

1. SolidWorks MCP input adapter
2. SolidWorks MCP output adapter (apply callouts to drawing)
3. Voice input via Gemma 3n native audio
4. Company-specific rule editing UI
5. Tolerance stack-up analysis
6. Drawing validation (check existing GD&T)

## Hour-by-Hour Plan

| Hour | Focus | Checkpoint |
|------|-------|------------|
| 0-1 | Backend scaffold + Ollama client + schemas | Can call Gemma and get response |
| 0-1 | Frontend scaffold + input component + SSE hook | Can send request and see events |
| 1-2 | Gemma 3n prompt engineering for feature extraction | Text → structured features works |
| 1-2 | Feature control frame renderer | FCF boxes render with correct Unicode |
| 2-3 | Gemma 270M integration (classifier) + Brain lookups | Full pipeline: text → classification → tolerance values |
| 2-3 | Streaming display + reasoning panel | Progressive results appear in UI |
| 3-4 | Integration: frontend ↔ backend end-to-end | Complete flow works with real models |
| 4-5 | Image input path (P1) | Photo → features → GD&T works |
| 5-6 | Polish: warnings, example presets, datum display | All P1 items |
| 6-7 | Edge cases, error handling, demo rehearsal | `validate_pipeline.py` passes |
| 7-8 | Demo rehearsal x3, offline verification, backup plan | Ready to present |

## Demo Rehearsal Checklist (Hour 7-8)

- [ ] Airplane mode ON — everything still works
- [ ] Run all 5 acceptance test scenarios — all produce correct output
- [ ] Photo of desk bracket produces reasonable GD&T
- [ ] Base vs. fine-tuned comparison is visually obvious
- [ ] Latency < 1 second on all scenarios
- [ ] Status bar shows "local, zero cloud" throughout
- [ ] No console errors in browser dev tools
- [ ] Presenter knows the 2-minute script cold
- [ ] Backup: if live demo fails, have screenshots of working output ready

## What to Cut If Behind Schedule

If at hour 4 you don't have end-to-end working:

- Drop image input (P1) — text-only demo is still strong
- Drop warnings (P1) — core callouts are enough
- Drop standards search (P1) — not needed for main demo flow
- Focus ALL remaining time on making the core text → GD&T flow bulletproof

If at hour 6 you don't have image input:

- That's fine. Text input + fine-tuning comparison + streaming UI + reasoning = strong demo
- Mention image capability in the architecture reveal: "Gemma 3n is natively multimodal — the image path is built, we're showing text for clarity"

## Judge-Specific Demo Notes

**For Dhiraj (CEO):** Explicitly name the layers: "This is the Teacher output [show training data]. This is the Student [Gemma 3n]. This is the Matcher [embedding lookup]. This is the Brain [tolerance tables]. This is the Worker [output]."

**For Sai (CTO):** Show the latency breakdown. Say the numbers: "847 milliseconds end-to-end. 290ms student, 78ms classifier, 42ms matcher, 425ms worker. Zero cloud calls. 2.3GB total model footprint."

**For Iris & Logan (Engineers):** Show the API design. Show real JSON flowing. Mention SSE streaming. They want to see it's not a hack — it's engineered.

**For Maya (ML + Full-stack):** Show the full product loop. Input → processing → output → reasoning. Show the UI responding to real data. She wants product sense, not just ML.
