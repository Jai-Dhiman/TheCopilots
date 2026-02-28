# ToleranceAI — Product Requirements Document

> NO CODE in this document. Requirements and acceptance criteria only.

## Product Summary

ToleranceAI is an on-device AI copilot that generates ASME Y14.5-2018 compliant GD&T callouts from part feature inputs (photos, text descriptions, or SolidWorks model data). It targets junior-to-mid-level mechanical engineers who lack the 10-20 years of tribal knowledge needed for confident GD&T decisions.

## Requirements Priority Tiers

- **P0 — Must have for hackathon demo.** If this doesn't work, the demo fails.
- **P1 — Should have.** Significantly improves demo quality. Build if time allows after P0 is solid.
- **P2 — Nice to have.** Impressive but not critical. Only if P0 and P1 are polished.
- **P3 — Future / post-hackathon.** Document in architecture, don't build.

---

## Functional Requirements

### FR-1: Feature Extraction from Natural Language (P0)

**Description:** The system accepts a natural language description of a part feature and extracts structured feature data (feature type, geometry, material, manufacturing process, mating conditions).

**Input:** Free-form text string (e.g., "Cylindrical aluminum boss, 12mm diameter, needs to be perpendicular to the mounting face within 0.05mm. CNC machined, mates with a bearing bore.")

**Output:** Structured feature record with: feature_type, geometry (dimensions), material, manufacturing_process, mating_condition, parent_surface.

**Acceptance Criteria:**

- Correctly identifies feature type for the 8 core types: hole, boss, surface, slot, groove, shaft, pattern, bend
- Extracts numeric dimensions with units (mm or inches)
- Identifies material when mentioned (or returns "unspecified")
- Identifies manufacturing process when mentioned (or returns "unspecified")
- Identifies mating/assembly context when mentioned
- Responds within 300ms

### FR-2: Feature Extraction from Image (P0)

**Description:** The system accepts a photo of a part, sketch, or drawing and extracts the same structured feature data as FR-1.

**Input:** JPEG/PNG image file (camera photo or screenshot)

**Output:** Same structured feature record as FR-1.

**Acceptance Criteria:**

- Correctly identifies primary feature type from a clear photo of a simple part (bracket, plate, shaft)
- Estimates approximate dimensions when scale reference is visible
- Handles typical phone camera quality (lighting variation, slight blur, perspective distortion)
- Responds within 500ms
- Gracefully handles ambiguous images with confidence scores and clarifying questions

### FR-3: GD&T Classification (P0)

**Description:** Given structured feature data, the fine-tuned classifier recommends the appropriate geometric characteristic symbol, tolerance class, and whether datums are required.

**Input:** Structured feature record from FR-1 or FR-2.

**Output:** Classification: primary_control (GD&T symbol), tolerance_class (tight/medium/loose), datum_required (bool), modifier_recommendation (MMC/LMC/RFS/none), reasoning_key.

**Acceptance Criteria:**

- Correctly selects the primary geometric characteristic for all 14 ASME Y14.5 symbols
- Correctly identifies when datums are required vs. not (form controls need none; orientation/location controls do)
- Correctly recommends MMC for clearance-fit holes, LMC for minimum-wall-thickness scenarios
- Fine-tuned model outperforms base model on a held-out test set of 50 examples (measurable improvement)
- Responds within 100ms

### FR-4: Datum Scheme Recommendation (P0)

**Description:** The system recommends a datum scheme (primary, secondary, optional tertiary) with reasoning based on the part geometry, assembly context, and manufacturing process.

**Input:** Structured feature data + classification.

**Output:** Datum scheme with: datum letter, surface description, and reasoning for each level (primary/secondary/tertiary).

**Acceptance Criteria:**

- Primary datum is always the largest/most stable surface or the primary assembly contact surface
- Secondary datum is perpendicular to primary and constrains additional degrees of freedom
- Reasoning references ASME Y14.5 datum selection principles
- When assembly mate information is available (SolidWorks path), uses mate data to inform datum selection
- Does not recommend unnecessary tertiary datums for simple parts

### FR-5: Tolerance Value Selection (P0)

**Description:** The system selects appropriate tolerance values based on the manufacturing process, material, feature geometry, and desired fit/function.

**Input:** Feature data + classification + datum scheme + manufacturing process.

**Output:** Numeric tolerance value with units and manufacturing justification.

**Acceptance Criteria:**

- Tolerance values fall within the achievable range for the specified manufacturing process (per tolerance tables)
- Provides margin explanation: "Your process can hold ±X, specified tolerance is Y, giving Z margin"
- Defaults to metric (mm) unless input specifies inches
- Does not specify tolerances tighter than the manufacturing process can achieve without flagging it as a warning

### FR-6: Feature Control Frame Generation (P0)

**Description:** The system generates correctly formatted ASME Y14.5 feature control frames for each callout.

**Input:** Symbol + tolerance value + modifier + datum references.

**Output:** Formatted feature control frame string: `|⊕| ∅0.25 Ⓜ | A | B |`

**Acceptance Criteria:**

- Uses correct Unicode symbols for all 14 geometric characteristics
- Includes diameter symbol (∅) for cylindrical tolerance zones
- Includes correct modifier symbols (Ⓜ for MMC, Ⓛ for LMC)
- Datum references appear in correct order (primary | secondary | tertiary)
- Output is valid per ASME Y14.5-2018 §3.4 (Feature Control Frame)

### FR-7: Reasoning and Explanation (P0)

**Description:** For each callout, the system provides a natural language explanation of WHY this specific control, tolerance, and datum scheme were chosen.

**Input:** Complete analysis context.

**Output:** Plain English explanation referencing the specific part geometry, manufacturing process, and assembly requirements.

**Acceptance Criteria:**

- Explains the geometric control choice (why position vs. profile vs. runout, etc.)
- Explains the tolerance value choice (manufacturing capability, margin, fit type)
- Explains datum selection (assembly context, fixture orientation, stability)
- References relevant ASME Y14.5 sections
- Readable by a junior engineer — no unexplained jargon

### FR-8: Warnings and Considerations (P1)

**Description:** The system flags potential issues, edge cases, and manufacturing considerations that an experienced engineer would catch.

**Input:** Complete analysis context.

**Output:** List of warnings with actionable recommendations.

**Acceptance Criteria:**

- Flags when specified tolerance is tighter than the manufacturing process typically achieves
- Flags when a form control might be needed on a datum surface (e.g., flatness on large datum faces)
- Suggests when concentricity should be replaced with runout (per modern Y14.5 practice)
- Warns about surface finish requirements when tolerance is very tight
- Warns about compound tolerance stack-up risks when multiple callouts interact

### FR-9: Streaming SSE Response (P0)

**Description:** Analysis results stream to the frontend via Server-Sent Events, showing progressive results as each pipeline stage completes.

**Input:** Analysis request.

**Output:** SSE stream with typed events: feature_extraction → datum_recommendation → gdt_callouts → reasoning → warnings → analysis_complete.

**Acceptance Criteria:**

- First event (feature_extraction) arrives within 300ms of request
- Each stage streams as soon as it completes — no waiting for full pipeline
- Client can render partial results as stages arrive
- analysis_complete includes full metadata (latency breakdown, device info, zero cloud calls)
- Connection handles graceful error recovery if a stage fails

### FR-10: Standards Lookup API (P1)

**Description:** API endpoints for direct lookup and semantic search of ASME Y14.5 sections.

**Acceptance Criteria:**

- `/api/standards/{code}` returns the specific section with rules, examples, and common mistakes
- `/api/standards/search?q=` performs semantic search and returns top-5 relevant sections with similarity scores
- `/api/tolerances?process=&material=` returns tolerance capability data
- All lookups respond within 50ms

### FR-11: SolidWorks MCP Input Adapter (P3 — Architecture Only)

**Description:** An input adapter that reads SolidWorks model data via MCP and normalizes it into the pipeline's feature input format.

**Acceptance Criteria (design-level, not implementation):**

- Reads feature tree (feature types, dimensions)
- Reads assembly mates (contact faces, concentric relationships)
- Reads material properties from SolidWorks material library
- Normalizes all data into the same schema used by text/image paths
- Operates entirely locally (MCP server runs on same machine as SolidWorks)

### FR-12: SolidWorks MCP Output Adapter (P3 — Architecture Only)

**Description:** An output adapter that pushes GD&T callouts back to a SolidWorks drawing via MCP.

**Acceptance Criteria (design-level, not implementation):**

- Adds feature control frame annotations to the active drawing
- Places datum feature symbols on appropriate model surfaces
- Adds dimension callouts with tolerance values
- Does not overwrite existing GD&T — only adds new callouts

---

## Non-Functional Requirements

### NFR-1: Zero Cloud Inference (P0)

All model inference, standards matching, and knowledge lookups must execute locally. Zero network calls during the analysis pipeline. The system must function identically with airplane mode enabled.

**Verification:** Disconnect network, run full analysis, verify identical results and latency.

### NFR-2: Latency (P0)

End-to-end analysis completes in under 1 second on M4 MacBook Air 32GB. First streaming event within 300ms.

**Verification:** Measure wall-clock time from request to `analysis_complete` event across 10 test inputs. 95th percentile must be < 1000ms.

### NFR-3: Model Memory (P0)

Total model RAM usage under 3GB (Gemma 3n ~2GB + Gemma 270M ~300MB + MiniLM ~90MB).

**Verification:** Monitor RSS memory during inference. Must leave >10GB free on 32GB system for SolidWorks (future) and OS overhead.

### NFR-4: ASME Y14.5-2018 Compliance (P0)

All GD&T output must comply with ASME Y14.5-2018. No mixing of ISO 1101 conventions. Feature control frame format must be valid per §3.4.

**Verification:** Acceptance test scenarios (below) verified by the ASME rules encoded in the brain database.

### NFR-5: Graceful Degradation (P1)

If Ollama is not running or a model fails to load, the system must display a clear error state rather than crashing. If classification confidence is low, the system should present alternatives rather than a single recommendation.

**Verification:** Kill Ollama process, verify UI shows "Model offline" status. Feed ambiguous input, verify multiple options are presented.

### NFR-6: Fine-Tuning Improvement (P0 — Hackathon Scoring)

The fine-tuned Gemma 270M must demonstrably outperform base Gemma 270M on GD&T classification tasks. This is a core hackathon judging criterion.

**Verification:** Run the same 50-example test set through base model and fine-tuned model. Report accuracy improvement. Must show meaningful improvement on at least symbol selection and datum requirement classification.

---

## Acceptance Test Scenarios

### Scenario 1: Perpendicular Boss (P0)

**Input:** "Cylindrical aluminum boss, 12mm diameter, needs to be perpendicular to the mounting face within 0.05mm. CNC machined, mates with a bearing bore."

**Expected Output:**

- Features: cylindrical boss (d=12mm), mounting face, bearing interface
- Datum scheme: Datum A = mounting face (primary, largest flat surface)
- Callouts:
  - Perpendicularity ⊥ ∅0.05 | A on the boss
  - Position ⊕ with MMC on bearing bore (suggested)
- Reasoning: references CNC capability on AL6061, bearing alignment, perpendicularity vs. position distinction
- Warning: may suggest position callout for the bearing bore in addition to perpendicularity

### Scenario 2: Hole Pattern (P0)

**Input:** "4x M6 threaded holes on a bolt circle, 50mm PCD, need to line up with a mating flange. Sheet metal part, laser cut then tapped."

**Expected Output:**

- Features: hole pattern (4x, M6, PCD=50mm)
- Datum scheme: Datum A = flange face, Datum B = one locating feature
- Callouts: Position ⊕ ∅ tolerance Ⓜ | A | B
- Reasoning: MMC appropriate for clearance-fit fastener holes, laser cut tolerance capability, bonus tolerance explanation
- Tolerance value: within laser cutting + tapping capability range

### Scenario 3: Sealing Surface (P1)

**Input:** "O-ring groove on a hydraulic manifold face. The groove is 2mm wide, 1.5mm deep. Needs to seal at 200 bar. Aluminum 6061-T6, CNC milled."

**Expected Output:**

- Features: groove (w=2mm, d=1.5mm), sealing face
- Callouts: Profile of a surface ⌓ on groove geometry, tight flatness on sealing face
- Reasoning: profile controls groove cross-section, flatness ensures seal integrity, references hydraulic sealing requirements
- Warning: surface finish callout needed for sealing face (Ra value)

### Scenario 4: Large Flat Surface (P0)

**Input:** "Cast iron base plate, 300mm x 200mm, needs to be flat within 0.1mm. This is the primary mounting surface for the assembly."

**Expected Output:**

- Features: flat surface (300x200mm)
- Callouts: Flatness ▱ 0.1 (NO datum reference — form control)
- Reasoning: form controls do not require datums, casting typically requires machining for this tolerance
- Warning: cast surfaces typically need machining to achieve 0.1mm flatness — raw casting is 0.5-1mm

### Scenario 5: Shaft Concentricity (P0)

**Input:** "Turned steel shaft with two bearing journals, 25mm diameter, spaced 100mm apart. Journals need to be concentric within 0.02mm. Lathe turned."

**Expected Output:**

- Features: shaft with 2 bearing journals (d=25mm, spacing=100mm)
- Callouts: Circular runout ↗ 0.02 | A (NOT concentricity)
- Reasoning: "Runout is preferred over concentricity per modern ASME Y14.5-2018 practice. Concentricity requires derived median points which are expensive to inspect. Runout achieves the same functional result — controlling radial variation relative to the datum axis — and is directly measurable with an indicator."
- Datum: Datum A = one journal (establishes the axis)
- This scenario specifically tests that the system recommends runout over concentricity — a key tribal knowledge indicator.

### Scenario 6: Photo Input — Desk Bracket (P0)

**Input:** Photo of a metal bracket (L-shaped, with mounting holes and a bend)

**Expected Output:**

- Features extracted from image: mounting holes, flat surfaces, bend angle
- Reasonable datum scheme based on visible geometry
- Appropriate callouts for the identified features
- Reasoning accounts for visible manufacturing method (stamped, machined, etc.)
- May request clarification on material/process if not determinable from image

### Scenario 7: Ambiguous Input (P1)

**Input:** "A round thing that goes into another round thing"

**Expected Output:**

- System identifies this as ambiguous
- Presents possible interpretations: shaft-into-bore? Pin-into-hole? Bearing journal?
- Asks clarifying questions rather than guessing
- If forced to recommend, provides multiple alternatives with confidence scores

### Scenario 8: Fine-Tuning Comparison (P0 — Demo Moment)

**Input:** Same input to base Gemma 270M and fine-tuned Gemma 270M

**Expected Output:**

- Base model: vague or incorrect GD&T recommendation (wrong symbol, missing datums, inappropriate modifier)
- Fine-tuned model: correct symbol, appropriate datums, correct modifier, reasonable tolerance value
- The delta must be visually obvious in the demo

---

## Out of Scope (Explicitly)

- Tolerance stack-up analysis (multi-part assembly tolerance chain calculation)
- GD&T validation of existing drawings (checking if callouts are correct)
- Drawing generation (creating full 2D drawings from 3D models)
- ISO 1101 support (ASME Y14.5-2018 only for hackathon)
- Voice input/output (optional P2 if time allows)
- Multi-language support
- User accounts or persistence
- Cost estimation based on tolerances
