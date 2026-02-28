# ToleranceAI — Overview

## What This Is

An AI copilot that puts 20 years of senior mechanical engineering GD&T expertise on every engineer's screen. The system takes part features — from a camera photo, natural language description, or a SolidWorks model via MCP — and generates ASME Y14.5-2018 compliant GD&T callouts with full reasoning, entirely on-device.

## Why This Vertical

GD&T (Geometric Dimensioning & Tolerancing) is the universal engineering language for specifying allowable variation in manufactured parts. Every part that gets machined, molded, or printed needs GD&T callouts on its drawing. Getting them right requires 10-20 years of experience. Getting them wrong causes manufacturing rejects, assembly failures, and field recalls.

### The Problem

- Junior engineers spend 2-4 hours per moderately complex part figuring out GD&T callouts
- Senior engineers spend 30-60 minutes reviewing and correcting junior work
- The knowledge of WHY a particular tolerance scheme works for a specific situation is deeply tribal — learned through decades of manufacturing experience, rarely documented
- The skilled ME shortage is acute: experienced engineers are retiring, and GD&T expertise takes years to develop
- GD&T training alone is a $200M+ industry because the standard is that hard to learn

### Why It Fits InstaLILY's Pattern

| InstaLILY Customer DNA | GD&T Vertical Match |
|------------------------|---------------------|
| Large, structured catalogs | ASME Y14.5 = structured catalog of 14 geometric symbols, modifiers, rules |
| Tribal knowledge trapped in veterans' heads | Senior ME knowledge: "use profile here because the vendor's CNC can't hold true position on that curved surface" |
| Field workers making decisions away from desk | Engineers reviewing drawings on shop floor, in manufacturing meetings, at vendor sites |
| Messy unstructured input → structured output | Natural language or photo → formal GD&T callout with datum scheme and tolerances |
| High cost of getting it wrong | Wrong tolerances = parts don't assemble, manufacturing rejects, field failures |
| Compliance-driven | ASME Y14.5 compliance is contractual — drawings are legal documents |

### Market Opportunity

- GD&T is used across ALL manufacturing: aerospace, automotive, medical devices, consumer electronics, industrial equipment
- Every manufacturing company needs this — the knowledge substrate is editable, so each company can add their vendor-specific capabilities and house rules
- The "Desk" concept: engineers live in SolidWorks 8 hours/day — the AI copilot should execute inside their CAD environment via MCP, not in a separate app

## The "Desk" Concept

The product's north star is the engineer's desk — specifically, their SolidWorks environment. ToleranceAI is designed to be a native copilot that lives where engineers work.

### Three Input Paths (One Pipeline)

1. **FreeCAD screen capture** (hackathon demo path) — Engineer opens FreeCAD with a part model. ToleranceAI captures the CAD window via browser screen share, extracts features from the rendered view using Gemma 3n E4B's MobileNet-v5 encoder. Entirely local — the screen capture never leaves the machine.
2. **Camera/Photo** (alternative visual path) — Engineer photographs a part, sketch, or drawing. Same Gemma 3n E4B multimodal pipeline.
3. **Text description** — Engineer types a natural language description. Simplest input path. Always available as fallback.
4. **SolidWorks MCP** (production path) — AI reads the feature tree, assembly mates, material properties directly from the live CAD model. Richest data. Future integration.

All three paths normalize into the same feature input format and feed the identical Student → Classifier → Matcher → Brain → Worker pipeline.

### Why On-Device (The Real Argument)

This isn't "it's faster locally." The on-device story is:

- **ITAR/Export control:** Defense and aerospace engineering drawings legally cannot leave a secure network. A cloud GD&T tool is illegal for ~40% of the US manufacturing market.
- **Proprietary IP:** Tolerancing decisions reveal manufacturing capabilities to competitors. Drawings are trade secrets.
- **Shop floor:** Manufacturing environments have unreliable internet. Engineers review drawings at the CNC machine, in the QC lab, at supplier sites.
- **SolidWorks is already local:** The CAD tool is a desktop app. The MCP server is local. The AI should be local. The entire loop stays on one machine.

## Demo Script (2 Minutes)

### Setup (0:00–0:15)

"Every manufactured part needs GD&T callouts — the language that tells a machine shop what tolerances to hold. Get it wrong and parts don't assemble, rejects spike, or worse — field failures. The problem: it takes 10-20 years of experience to get consistently good at GD&T. And those experienced engineers are retiring."

### Problem (0:15–0:30)

"Today, a junior engineer stares at a part for hours trying to figure out: What datum scheme? Which geometric control? How tight? They guess, a senior engineer corrects it. The tribal knowledge — 'use profile here because your vendor can't hold true position on that curved surface' — lives in people's heads."

### Live Demo — The "Oh Shit" Moment (0:30–1:15)

**The desk demo:** Open FreeCAD with a bracket model on screen. Connect ToleranceAI to the FreeCAD window via screen capture.

"Let me show you this with a real CAD model. Here's a bracket in FreeCAD — it has mounting holes, a flat contact surface, and a bend. I connect the copilot to the CAD window..."

The system — running locally on this laptop — instantly:

1. **Extracts features:** 4 mounting holes, planar mounting surface, 90° bend
2. **Recommends datum scheme:** Datum A = mounting face (largest flat, primary contact), Datum B = locating hole
3. **Suggests GD&T callouts:** Position ⊕ ∅0.25 Ⓜ | A | B for the hole pattern, flatness ▱ 0.1 on the mounting face, angularity ∠ 0.3 | A on the bend
4. **Explains reasoning:** "Position with MMC on the bolt holes because these are clearance fits — bonus tolerance as the holes depart from MMC. Flatness on the mounting face because this is the primary datum and needs to be within 0.1mm for proper seating. Your sheet metal stamping process typically holds ±0.15mm on bends, so 0.3mm angularity gives comfortable margin."
5. **Flags issues:** "Consider adding a profile callout if the bend radius is critical for clearance with adjacent components."

All under 1 second. No internet. No cloud API. Running on this MacBook.

**Before/after fine-tuning comparison:** "Watch what base Gemma says vs. our fine-tuned model for the same input." Base model gives vague or incorrect GD&T. Fine-tuned model nails symbol selection, tolerance values, and datum logic.

### Architecture Reveal (1:15–1:45)

"This runs InstaLILY's exact architecture — teacher-student distillation with Gemini generating training data and Gemma running inference at the edge. An editable knowledge brain with ASME Y14.5 rules and manufacturing process capabilities. An autonomous worker that generates complete callouts with reasoning. The copilot watches the engineer's CAD screen — entirely on-device. Gemma 3n E4B with MobileNet-v5 processes the visual input via mlx-vlm on Apple Silicon. In production, this plugs directly into SolidWorks via MCP — the AI reads the actual CAD model, no description needed."

### Market + Close (1:45–2:00)

"GD&T training is a $200M+ industry because it's that hard to learn. Every manufacturing company needs it — aerospace, automotive, medical devices. The knowledge substrate is editable per company. And because it's on-device, it works for ITAR-controlled designs where cloud is literally illegal. This is the next InstaWorker vertical."

## User Journey

### Persona: Alex, Junior ME (2 years experience)

**Without ToleranceAI:**

1. Alex designs a bracket in SolidWorks
2. Switches to 2D drawing, stares at features
3. Opens the ASME Y14.5 standard PDF, Ctrl+F's for relevant sections
4. Guesses datum scheme based on limited experience
5. Picks tolerance values from a chart, unsure if they're appropriate for the manufacturing process
6. Submits drawing for review
7. Senior engineer marks up 6 corrections, explains reasoning
8. Alex fixes, resubmits. 4+ hours total.

**With ToleranceAI:**

1. Alex designs a bracket in SolidWorks
2. Connects ToleranceAI to their FreeCAD window — the AI sees the model on screen
3. System identifies features, recommends datum scheme, generates callouts with reasoning
4. Alex reads the reasoning: "Oh, THAT'S why you use profile instead of position on a curved surface"
5. Alex applies callouts to drawing, submits
6. Senior engineer: "Looks good." 30 minutes total.
7. Alex learned something — each interaction builds GD&T intuition.

## Hackathon Judge Optimization

| Judge | Role | What Impresses Them |
|-------|------|---------------------|
| **Dhiraj** | CEO, distillation expert | Teacher-student architecture. "Gemini generated training data, Gemma runs inference at the edge." Show you understand their core IP. |
| **Sai** | CTO, inference optimization | Latency numbers. Zero cloud calls. Model size. Edge optimization on M4. |
| **Iris & Logan** | Backend/AI engineers | Full pipeline working end-to-end. Clean API design, real data flowing. Production engineering. |
| **Maya** | Applied ML + Full-stack | Complete product, not a notebook. Real UI, real user flow. Product sense. |

## Pre-Hackathon vs. Hackathon Day

### Pre-Hackathon (Night Before)

1. Structure ASME Y14.5 rules into `asme_y14_5.json`
2. Build tolerance tables by manufacturing process + material
3. Build datum scheme pattern database
4. Generate 500+ synthetic training pairs via Gemini 2.5 Pro
5. LoRA fine-tune Gemma 3 270M on feature → GD&T classification
6. Pre-compute embeddings for all standard sections
7. Download and test Gemma 3n E2B int4 via Ollama
8. Scaffold project skeleton + all documentation

### Hackathon Day (8 Hours)

| Hour | Task | Agent |
|------|------|-------|
| 0-1 | Backend scaffold + schemas + Ollama client | Backend |
| 0-1 | Frontend scaffold + feature input + SSE hooks | Frontend |
| 1-3 | Gemma prompt engineering for GD&T analysis | Backend |
| 1-3 | Streaming UI + callout renderer + datum display | Frontend |
| 3-4 | Brain integration (tolerance tables, datum logic) | Backend |
| 3-4 | Validate embeddings + matching accuracy | Data |
| 4-6 | Integration: frontend <> backend end-to-end | Lead |
| 6-7 | Polish: error handling, edge cases, demo prep | All |
| 7-8 | Demo rehearsal + offline verification | Lead |
