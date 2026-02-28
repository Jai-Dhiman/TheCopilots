import asyncio
import time
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from .schemas import AnalyzeRequest
from .streaming import sse_event, sse_error
from models.gemma import OllamaUnavailableError, OllamaParseError

router = APIRouter()


def _derive_datum_scheme(classification: dict, features: dict) -> dict:
    """Derive datum scheme from classification and features.

    Form controls -> no datums. Location/orientation -> need datums.
    """
    if not classification.get("datum_required", False):
        return {"primary": None, "secondary": None, "tertiary": None}

    primary = {
        "datum": "A",
        "surface": features.get("parent_surface") or "primary mounting surface",
        "reasoning": "Largest flat surface, primary assembly contact, maximum stability",
    }
    secondary = None
    feature_type = features.get("feature_type", "")
    if feature_type in ("hole", "pattern", "boss", "slot"):
        secondary = {
            "datum": "B",
            "surface": "locating feature",
            "reasoning": "Perpendicular to primary datum, constrains additional degrees of freedom",
        }

    return {"primary": primary, "secondary": secondary, "tertiary": None}


def _build_matcher_query(features: dict, classification: dict) -> str:
    """Build a natural language query for semantic matching."""
    parts = []
    for key in ["feature_type", "mating_condition"]:
        if features.get(key):
            parts.append(str(features[key]))
    for key in ["primary_control", "symbol_name"]:
        if classification.get(key):
            parts.append(str(classification[key]))
    return " ".join(parts) if parts else "geometric dimensioning and tolerancing"


async def _safe_match_standards(embedder, query: str) -> list[dict]:
    """Match standards with graceful degradation."""
    try:
        if embedder is None:
            return []
        return embedder.match_standards(query, top_k=5)
    except Exception:
        return []


async def _safe_get_tolerances(manufacturing, classification: dict, features: dict) -> dict:
    """Get tolerances with graceful degradation."""
    try:
        if manufacturing is None:
            return {"tolerance_range": None, "material_properties": None}
        process = features.get("manufacturing_process", "unspecified")
        material = features.get("material", "unspecified")
        feature_type = features.get("feature_type", "unspecified")

        tol_range = await manufacturing.get_tolerance_range(process, material, feature_type)
        mat_props = await manufacturing.get_material_properties(material)

        return {"tolerance_range": tol_range, "material_properties": mat_props}
    except Exception:
        return {"tolerance_range": None, "material_properties": None}


@router.post("/analyze")
async def analyze(request: Request, body: AnalyzeRequest):
    """Main analysis pipeline. Returns an SSE stream."""

    async def event_generator():
        ollama = request.app.state.ollama
        embedder = getattr(request.app.state, "embedder", None)
        manufacturing = getattr(request.app.state, "manufacturing_lookup", None)

        timings = {}

        try:
            # Layer 1: Student (Gemma 3n) -- Feature Extraction
            t0 = time.monotonic()
            try:
                features = await ollama.extract_features(
                    text=body.description,
                    image_base64=body.image_base64,
                )
            except OllamaParseError:
                features = await ollama.extract_features(
                    text="Return ONLY valid JSON. " + body.description,
                    image_base64=body.image_base64,
                )
            timings["student_ms"] = int((time.monotonic() - t0) * 1000)
            yield sse_event("feature_extraction", features)

            # Layer 2: Classifier (Gemma 270M) -- GD&T Classification
            t0 = time.monotonic()
            finetuned_model = "gemma3:1b"
            try:
                classification = await ollama.classify_gdt(features, model=finetuned_model)
            except OllamaParseError:
                classification = await ollama.classify_gdt(features, model=finetuned_model)
            timings["classifier_ms"] = int((time.monotonic() - t0) * 1000)

            # Fine-tuning comparison mode
            if body.compare:
                try:
                    base_classification = await ollama.classify_gdt(features, model="gemma3:1b")
                    yield sse_event("classification_comparison", {
                        "base_model": base_classification,
                        "finetuned_model": classification,
                    })
                except Exception as e:
                    yield sse_event("classification_comparison", {
                        "error": f"Base model comparison failed: {e}",
                        "finetuned_model": classification,
                    })

            # Derive datum scheme
            datum_scheme = _derive_datum_scheme(classification, features)
            yield sse_event("datum_recommendation", datum_scheme)

            # Layers 3+4: Matcher + Brain (parallel)
            t0 = time.monotonic()
            matcher_query = _build_matcher_query(features, classification)
            standards, tolerances = await asyncio.gather(
                _safe_match_standards(embedder, matcher_query),
                _safe_get_tolerances(manufacturing, classification, features),
            )
            timings["matcher_ms"] = int((time.monotonic() - t0) * 1000)

            # Layer 5: Worker (Gemma 3n) -- Output Generation
            t0 = time.monotonic()
            try:
                worker_result = await ollama.generate_output(
                    features=features,
                    classification=classification,
                    datum_scheme=datum_scheme,
                    standards=standards,
                    tolerances=tolerances,
                )
            except OllamaParseError:
                worker_result = await ollama.generate_output(
                    features=features,
                    classification=classification,
                    datum_scheme=datum_scheme,
                    standards=standards,
                    tolerances=tolerances,
                )
            timings["worker_ms"] = int((time.monotonic() - t0) * 1000)

            yield sse_event("gdt_callouts", {
                "callouts": worker_result.get("callouts", []),
            })
            yield sse_event("reasoning", {
                "summary": worker_result.get("summary", ""),
                "manufacturing_notes": worker_result.get("manufacturing_notes", ""),
                "standards_references": worker_result.get("standards_references", []),
            })
            yield sse_event("warnings", {
                "warnings": worker_result.get("warnings", []),
            })

            total_ms = sum(timings.values())
            yield sse_event("analysis_complete", {
                "analysis_id": str(uuid4()),
                "metadata": {
                    "inference_device": "local",
                    "total_latency_ms": total_ms,
                    "student_latency_ms": timings.get("student_ms", 0),
                    "classifier_latency_ms": timings.get("classifier_ms", 0),
                    "matcher_latency_ms": timings.get("matcher_ms", 0),
                    "brain_latency_ms": timings.get("matcher_ms", 0),
                    "worker_latency_ms": timings.get("worker_ms", 0),
                    "cloud_calls": 0,
                    "connectivity_required": False,
                },
            })

        except OllamaUnavailableError as e:
            yield sse_error(str(e), layer="ollama")
        except Exception as e:
            yield sse_error(f"Pipeline error: {e}", layer="unknown")

    return EventSourceResponse(event_generator())


@router.get("/standards/search")
async def search_standards(request: Request, q: str = Query(...)):
    """Semantic search across standards database."""
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        return {"results": []}
    results = embedder.match_standards(q, top_k=5)
    return {"results": results}


@router.get("/standards/{code}")
async def get_standard(code: str, request: Request):
    """Lookup specific ASME Y14.5 section by code."""
    brain = getattr(request.app.state, "brain_lookup", None)
    if brain is None:
        raise HTTPException(503, "Brain database not available")
    result = await brain.lookup_standard(code)
    if not result:
        raise HTTPException(404, f"Standard '{code}' not found")
    return result


@router.get("/tolerances")
async def get_tolerances(
    request: Request,
    process: str = Query(...),
    material: str = Query(...),
):
    """Lookup tolerance capability data."""
    mfg = getattr(request.app.state, "manufacturing_lookup", None)
    if mfg is None:
        return {"tolerances": []}
    results = await mfg.get_process_capability(process)
    return {"tolerances": results}


@router.get("/health")
async def health(request: Request):
    """Liveness check -- confirms Ollama + models are loaded."""
    ollama = request.app.state.ollama
    try:
        tags = await ollama.health_check()
        models = [m["name"] for m in tags.get("models", [])]
        return {
            "status": "healthy",
            "ollama": "connected",
            "models_loaded": models,
        }
    except OllamaUnavailableError as e:
        return {"status": "degraded", "ollama": str(e), "models_loaded": []}
