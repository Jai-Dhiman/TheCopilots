import asyncio
import logging
import time
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from .schemas import AnalyzeRequest, CreateDrawingRequest
from .streaming import sse_event, sse_error, sse_progress
from models.gemma import OllamaUnavailableError, OllamaParseError
from models.mlx_vlm_client import MlxVlmParseError, MlxVlmTimeoutError
from models.freecad_client import FreecadConnectionError
from models.techdraw_generator import generate_techdraw_script

logger = logging.getLogger(__name__)

router = APIRouter()


def _merge_vision_and_cad(vision_features: dict, cad_context: dict | None) -> dict:
    """Merge vision-inferred features with CAD-extracted data.

    CAD exact values override vision guesses where available.
    Priority: CAD exact values > vision inferred values > defaults.
    """
    if not cad_context or cad_context.get("error"):
        return vision_features

    merged = dict(vision_features)

    # Override geometry with CAD exact dimensions
    cad_objects = cad_context.get("objects", [])
    if cad_objects:
        # Use the first object with dimensions as primary feature source
        for obj in cad_objects:
            dims = obj.get("dimensions", {})
            if not dims:
                continue
            geometry = merged.get("geometry", {})
            if isinstance(geometry, dict):
                for key in ("diameter", "radius", "length", "width", "height", "depth", "angle"):
                    if key in dims:
                        geometry[key] = dims[key]
                merged["geometry"] = geometry

            # CAD feature type provides parent context when vision didn't detect one
            if obj.get("parent") and not merged.get("parent_surface"):
                merged["parent_surface"] = obj["parent"]
            break

    # Override material with CAD material assignment
    cad_materials = cad_context.get("materials", [])
    if cad_materials:
        merged["material"] = cad_materials[0].get("material", merged.get("material", "unspecified"))

    # Add constraint data (vision can't see these)
    cad_sketches = cad_context.get("sketches", [])
    if cad_sketches:
        constraints = []
        for sketch in cad_sketches:
            constraints.extend(sketch.get("constraints", []))
        if constraints:
            merged["cad_constraints"] = constraints

    return merged


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
        vlm = getattr(request.app.state, "vlm", None)
        embedder = getattr(request.app.state, "embedder", None)
        manufacturing = getattr(request.app.state, "manufacturing_lookup", None)
        freecad = getattr(request.app.state, "freecad", None)

        if vlm is None:
            yield sse_error("mlx-vlm not loaded", layer="vlm")
            return

        timings = {}

        try:
            # Step 1/5: Feature extraction
            yield sse_progress("student", "Extracting features with Gemma 3n...", 1, 5)
            logger.info("Layer 1 (student): starting feature extraction")
            t0 = time.monotonic()

            async def _extract_vision():
                try:
                    return await vlm.extract_features(
                        text=body.description,
                        image_base64=body.image_base64,
                    )
                except MlxVlmParseError:
                    logger.warning("Layer 1: parse error, retrying with explicit JSON instruction")
                    return await vlm.extract_features(
                        text="Return ONLY valid JSON. " + body.description,
                        image_base64=body.image_base64,
                    )

            async def _extract_cad():
                if freecad is None:
                    return None
                try:
                    return await freecad.extract_cad_context(
                        description_hint=body.description,
                    )
                except (FreecadConnectionError, Exception):
                    return None

            # Use pre-supplied CAD context from request, or fetch live
            if body.cad_context is not None:
                cad_context_raw = body.cad_context.model_dump()
                vision_features = await _extract_vision()
            else:
                vision_features, cad_context_raw = await asyncio.gather(
                    _extract_vision(), _extract_cad()
                )

            timings["student_ms"] = int((time.monotonic() - t0) * 1000)
            logger.info("Layer 1 (student): completed in %dms", timings["student_ms"])

            # Merge vision + CAD
            features = _merge_vision_and_cad(vision_features, cad_context_raw)

            yield sse_event("feature_extraction", {
                "features": [features],
                "material_detected": features.get("material"),
                "process_detected": features.get("manufacturing_process"),
            })

            # Emit CAD context event
            cad_connected = cad_context_raw is not None and not (cad_context_raw or {}).get("error")
            cad_data = cad_context_raw if cad_connected and cad_context_raw else {}
            yield sse_event("cad_context", {
                "connected": cad_connected,
                "document_name": cad_data.get("document_name"),
                "objects": cad_data.get("objects", []),
                "sketches": cad_data.get("sketches", []),
                "materials": cad_data.get("materials", []),
                "bounding_box": cad_data.get("bounding_box"),
                "source": "freecad_rpc",
            })

            # Step 2/5: Classification
            yield sse_progress("classifier", "Classifying GD&T controls...", 2, 5)
            logger.info("Layer 2 (classifier): starting GD&T classification")
            t0 = time.monotonic()
            finetuned_model = "gemma3:1b"
            try:
                classification = await ollama.classify_gdt(features, model=finetuned_model)
            except OllamaParseError:
                logger.warning("Layer 2: parse error, retrying classification")
                classification = await ollama.classify_gdt(features, model=finetuned_model)
            timings["classifier_ms"] = int((time.monotonic() - t0) * 1000)
            logger.info("Layer 2 (classifier): completed in %dms", timings["classifier_ms"])

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
            yield sse_event("datum_recommendation", {"datum_scheme": datum_scheme})

            # Step 3/5: Standards matching
            yield sse_progress("matcher", "Matching ASME Y14.5 standards...", 3, 5)
            logger.info("Layers 3+4 (matcher+brain): starting standards matching")
            t0 = time.monotonic()
            matcher_query = _build_matcher_query(features, classification)
            standards, tolerances = await asyncio.gather(
                _safe_match_standards(embedder, matcher_query),
                _safe_get_tolerances(manufacturing, classification, features),
            )
            timings["matcher_ms"] = int((time.monotonic() - t0) * 1000)
            logger.info("Layers 3+4 (matcher+brain): completed in %dms", timings["matcher_ms"])

            # Step 4/5: Output generation
            yield sse_progress("worker", "Generating GD&T callouts...", 4, 5)
            logger.info("Layer 5 (worker): starting output generation")
            t0 = time.monotonic()
            try:
                worker_result = await vlm.generate_output(
                    features=features,
                    classification=classification,
                    datum_scheme=datum_scheme,
                    standards=standards,
                    tolerances=tolerances,
                )
            except MlxVlmParseError:
                logger.warning("Layer 5: parse error, retrying output generation")
                worker_result = await vlm.generate_output(
                    features=features,
                    classification=classification,
                    datum_scheme=datum_scheme,
                    standards=standards,
                    tolerances=tolerances,
                )
            timings["worker_ms"] = int((time.monotonic() - t0) * 1000)
            logger.info("Layer 5 (worker): completed in %dms", timings["worker_ms"])

            # Step 5/5: Finalizing
            yield sse_progress("finalize", "Finalizing results...", 5, 5)
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

        except MlxVlmTimeoutError as e:
            logger.error("Pipeline timeout: %s", e)
            yield sse_error(str(e), layer="vlm")
        except OllamaUnavailableError as e:
            yield sse_error(str(e), layer="ollama")
        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
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
    freecad = getattr(request.app.state, "freecad", None)
    try:
        tags = await ollama.health_check()
        models = [m["name"] for m in tags.get("models", [])]
        result = {
            "status": "healthy",
            "ollama": "connected",
            "models_loaded": models,
        }
        if freecad is not None:
            result["freecad"] = "connected" if await freecad.health_check() else "not available"
        else:
            result["freecad"] = "not configured"
        return result
    except OllamaUnavailableError as e:
        return {"status": "degraded", "ollama": str(e), "models_loaded": []}


@router.get("/freecad/status")
async def freecad_status(request: Request):
    """Check FreeCAD RPC server connectivity."""
    freecad = getattr(request.app.state, "freecad", None)
    if freecad is None:
        return {"connected": False, "reason": "FreeCAD client not configured"}
    connected = await freecad.health_check()
    return {"connected": connected}


@router.post("/freecad/create-drawing")
async def create_drawing(request: Request, body: CreateDrawingRequest):
    """Create a TechDraw page with GD&T annotations in FreeCAD."""
    freecad = getattr(request.app.state, "freecad", None)
    if freecad is None or freecad._mock_mode:
        raise HTTPException(503, "Drawing creation requires live FreeCAD connection")

    script = generate_techdraw_script(
        document_name=body.document_name,
        callouts=body.callouts,
        datum_scheme=body.datum_scheme,
        features=body.features,
    )
    result = await freecad.execute_python(script)
    return {"status": "created", **result}
