# Backend Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the FastAPI backend pipeline that takes part feature descriptions (text or image), processes them through 5 local AI layers, and streams GD&T callouts to the frontend via SSE.

**Architecture:** Single Python/FastAPI process. Fixed sequential pipeline: Student (Gemma 3n E4B via mlx-vlm) -> Classifier (Gemma 270M via Ollama) -> Matcher (MiniLM in-process) + Brain (SQLite) in parallel -> Worker (Gemma 3n E4B via mlx-vlm). SSE events emitted after each layer completes. Zero cloud calls.

**Tech Stack:** Python 3.11+, FastAPI, mlx-vlm (Gemma 3n E4B multimodal), httpx (async Ollama client for 270M classifier), sse-starlette, aiosqlite, sentence-transformers, Pydantic v2

**Model Serving:**
- **Gemma 3n E4B** (student + worker): served via mlx-vlm Python API. Handles text AND image input (screen captures from FreeCAD). Model: `mlx-community/gemma-3n-E4B-it-4bit` (~3-4GB). Apple Silicon native via MLX.
- **Gemma 3 270M** (classifier): served via Ollama on localhost:11434. Text-to-text only. Fine-tuned via LoRA on GCP VM pre-hackathon.
- **all-MiniLM-L6-v2** (matcher): loaded in-process via sentence-transformers. ~90MB.

---

## Task 1: Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/models/__init__.py`
- Create: `backend/brain/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

**Step 1: Create directory structure and pyproject.toml**

```toml
# backend/pyproject.toml
[project]
name = "toleranceai-backend"
version = "0.1.0"
description = "GD&T copilot backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]",
    "sse-starlette>=2.0",
    "pydantic>=2.0",
    "aiosqlite",
    "httpx",
    "mlx-vlm",
    "sentence-transformers",
    "numpy",
    "python-multipart",
    "pillow",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "httpx"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

All `__init__.py` files are empty.

```python
# backend/tests/conftest.py
import pytest
```

**Step 2: Install dependencies**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv venv && uv pip install -e ".[dev]"`

**Step 3: Verify install**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run python -c "import fastapi; import httpx; import aiosqlite; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/pyproject.toml backend/__init__.py backend/api/__init__.py backend/models/__init__.py backend/brain/__init__.py backend/tests/__init__.py backend/tests/conftest.py
git commit -m "feat(backend): scaffold project structure with pyproject.toml"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `backend/api/schemas.py`
- Create: `backend/tests/test_schemas.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_schemas.py
from api.schemas import (
    AnalyzeRequest,
    Geometry,
    FeatureRecord,
    GDTClassification,
    DatumLevel,
    DatumScheme,
    GDTCallout,
    AnalysisMetadata,
    WorkerResult,
)


def test_analyze_request_minimal():
    req = AnalyzeRequest(description="12mm boss on mounting face")
    assert req.description == "12mm boss on mounting face"
    assert req.image_base64 is None
    assert req.compare is False


def test_analyze_request_full():
    req = AnalyzeRequest(
        description="boss",
        image_base64="abc123",
        manufacturing_process="cnc_milling",
        material="AL6061-T6",
        compare=True,
    )
    assert req.compare is True
    assert req.manufacturing_process == "cnc_milling"


def test_geometry_defaults():
    g = Geometry()
    assert g.unit == "mm"
    assert g.diameter is None


def test_feature_record():
    rec = FeatureRecord(
        feature_type="boss",
        geometry=Geometry(diameter=12.0, height=8.0),
        material="AL6061-T6",
        manufacturing_process="cnc_milling",
    )
    assert rec.feature_type == "boss"
    assert rec.geometry.diameter == 12.0
    assert rec.mating_condition is None


def test_gdt_classification():
    cls = GDTClassification(
        primary_control="perpendicularity",
        symbol="\u22a5",
        symbol_name="perpendicularity",
        tolerance_class="tight",
        datum_required=True,
        modifier="MMC",
        reasoning_key="bearing_alignment",
        confidence=0.92,
    )
    assert cls.datum_required is True
    assert cls.symbol == "\u22a5"


def test_datum_scheme_no_tertiary():
    scheme = DatumScheme(
        primary=DatumLevel(datum="A", surface="mounting_face", reasoning="largest flat"),
        secondary=DatumLevel(datum="B", surface="locating_hole", reasoning="perpendicular"),
    )
    assert scheme.tertiary is None


def test_gdt_callout():
    callout = GDTCallout(
        feature="boss",
        symbol="\u22a5",
        symbol_name="perpendicularity",
        tolerance_value="\u23000.05",
        unit="mm",
        modifier="MMC",
        modifier_symbol="\u24c2",
        datum_references=["A"],
        feature_control_frame="|\u22a5| \u23000.05 \u24c2 | A |",
        reasoning="Bearing alignment requires perpendicularity",
    )
    assert callout.datum_references == ["A"]


def test_analysis_metadata_defaults():
    meta = AnalysisMetadata(
        total_latency_ms=847,
        student_latency_ms=290,
        classifier_latency_ms=78,
        matcher_latency_ms=42,
        brain_latency_ms=12,
        worker_latency_ms=425,
    )
    assert meta.cloud_calls == 0
    assert meta.connectivity_required is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

**Step 3: Write schemas implementation**

```python
# backend/api/schemas.py
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    description: str
    image_base64: str | None = None
    manufacturing_process: str | None = None
    material: str | None = None
    compare: bool = False


class Geometry(BaseModel):
    diameter: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    depth: float | None = None
    angle: float | None = None
    count: int | None = None
    pcd: float | None = None
    unit: str = "mm"


class FeatureRecord(BaseModel):
    feature_type: str
    geometry: Geometry
    material: str
    manufacturing_process: str
    mating_condition: str | None = None
    parent_surface: str | None = None


class GDTClassification(BaseModel):
    primary_control: str
    symbol: str
    symbol_name: str
    tolerance_class: str
    datum_required: bool
    modifier: str | None = None
    reasoning_key: str
    confidence: float


class DatumLevel(BaseModel):
    datum: str
    surface: str
    reasoning: str


class DatumScheme(BaseModel):
    primary: DatumLevel | None = None
    secondary: DatumLevel | None = None
    tertiary: DatumLevel | None = None


class GDTCallout(BaseModel):
    feature: str
    symbol: str
    symbol_name: str
    tolerance_value: str
    unit: str = "mm"
    modifier: str | None = None
    modifier_symbol: str | None = None
    datum_references: list[str] = []
    feature_control_frame: str
    reasoning: str


class AnalysisMetadata(BaseModel):
    inference_device: str = "local"
    total_latency_ms: int
    student_latency_ms: int
    classifier_latency_ms: int
    matcher_latency_ms: int
    brain_latency_ms: int
    worker_latency_ms: int
    cloud_calls: int = 0
    connectivity_required: bool = False


class WorkerResult(BaseModel):
    callouts: list[GDTCallout] = []
    summary: str = ""
    manufacturing_notes: str = ""
    standards_references: list[str] = []
    warnings: list[str] = []
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_schemas.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/api/schemas.py backend/tests/test_schemas.py
git commit -m "feat(backend): add Pydantic schemas for API contract"
```

---

## Task 3: SSE Streaming Helpers

**Files:**
- Create: `backend/api/streaming.py`
- Create: `backend/tests/test_streaming.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_streaming.py
import json
from api.streaming import sse_event, sse_error, SSE_EVENT_TYPES


def test_sse_event_types_defined():
    assert "feature_extraction" in SSE_EVENT_TYPES
    assert "classification_comparison" in SSE_EVENT_TYPES
    assert "datum_recommendation" in SSE_EVENT_TYPES
    assert "gdt_callouts" in SSE_EVENT_TYPES
    assert "reasoning" in SSE_EVENT_TYPES
    assert "warnings" in SSE_EVENT_TYPES
    assert "analysis_complete" in SSE_EVENT_TYPES
    assert "error" in SSE_EVENT_TYPES


def test_sse_event_format():
    event = sse_event("feature_extraction", {"feature_type": "boss"})
    assert event["event"] == "feature_extraction"
    data = json.loads(event["data"])
    assert data["feature_type"] == "boss"


def test_sse_error_format():
    event = sse_error("Ollama not reachable", layer="ollama")
    assert event["event"] == "error"
    data = json.loads(event["data"])
    assert data["error"] == "Ollama not reachable"
    assert data["layer"] == "ollama"


def test_sse_error_no_layer():
    event = sse_error("Unknown failure")
    data = json.loads(event["data"])
    assert "layer" not in data
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_streaming.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write streaming implementation**

```python
# backend/api/streaming.py
import json

SSE_EVENT_TYPES = [
    "feature_extraction",
    "classification_comparison",
    "datum_recommendation",
    "gdt_callouts",
    "reasoning",
    "warnings",
    "analysis_complete",
    "error",
]


def sse_event(event_type: str, data: dict) -> dict:
    """Create a typed SSE event dict for EventSourceResponse."""
    return {
        "event": event_type,
        "data": json.dumps(data),
    }


def sse_error(message: str, layer: str | None = None) -> dict:
    """Create an error SSE event."""
    payload = {"error": message}
    if layer:
        payload["layer"] = layer
    return {
        "event": "error",
        "data": json.dumps(payload),
    }
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_streaming.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/api/streaming.py backend/tests/test_streaming.py
git commit -m "feat(backend): add SSE event formatting helpers"
```

---

## Task 4: System Prompts

**Files:**
- Create: `backend/models/prompts.py`
- Create: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_prompts.py
from models.prompts import (
    FEATURE_EXTRACTION_SYSTEM,
    CLASSIFICATION_SYSTEM,
    WORKER_SYSTEM,
    build_worker_user_prompt,
)


def test_feature_extraction_prompt_has_schema():
    assert "feature_type" in FEATURE_EXTRACTION_SYSTEM
    assert "geometry" in FEATURE_EXTRACTION_SYSTEM
    assert "material" in FEATURE_EXTRACTION_SYSTEM
    assert "JSON" in FEATURE_EXTRACTION_SYSTEM


def test_classification_prompt_has_symbols():
    assert "\u22a5" in CLASSIFICATION_SYSTEM  # perpendicularity
    assert "\u2295" in CLASSIFICATION_SYSTEM  # position
    assert "datum_required" in CLASSIFICATION_SYSTEM


def test_classification_prompt_has_runout_rule():
    assert "runout" in CLASSIFICATION_SYSTEM.lower()
    assert "concentricity" in CLASSIFICATION_SYSTEM.lower()


def test_worker_prompt_has_fcf_format():
    assert "feature_control_frame" in WORKER_SYSTEM
    assert "callouts" in WORKER_SYSTEM
    assert "warnings" in WORKER_SYSTEM


def test_build_worker_user_prompt():
    result = build_worker_user_prompt(
        features={"feature_type": "boss", "geometry": {"diameter": 12.0}},
        classification={"primary_control": "perpendicularity", "symbol": "\u22a5"},
        datum_scheme={"primary": {"datum": "A", "surface": "face"}},
        standards=[{"key": "7.1", "score": 0.9}],
        tolerances={"tolerance_range": {"min_mm": 0.02, "max_mm": 0.1}},
    )
    assert "boss" in result
    assert "perpendicularity" in result
    assert "12.0" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_prompts.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write prompts implementation**

```python
# backend/models/prompts.py
import json

FEATURE_EXTRACTION_SYSTEM = """You are a mechanical engineering feature extractor. Given a description or image of a part feature, extract structured data as JSON.

Output ONLY valid JSON matching this exact schema:
{
  "feature_type": "hole|boss|surface|slot|groove|shaft|pattern|bend",
  "geometry": {
    "diameter": null or float,
    "length": null or float,
    "width": null or float,
    "height": null or float,
    "depth": null or float,
    "angle": null or float,
    "count": null or int,
    "pcd": null or float,
    "unit": "mm"
  },
  "material": "string or unspecified",
  "manufacturing_process": "string or unspecified",
  "mating_condition": "string or null",
  "parent_surface": "string or null"
}

Rules:
- feature_type MUST be one of: hole, boss, surface, slot, groove, shaft, pattern, bend
- If information is not mentioned, use "unspecified" for strings or null for optional fields
- Extract numeric dimensions with units. Default to mm if no unit given
- Identify mating/assembly context when mentioned

Examples:

Input: "Cylindrical aluminum boss, 12mm diameter, 8mm tall, CNC machined, mates with a bearing bore"
Output: {"feature_type": "boss", "geometry": {"diameter": 12.0, "height": 8.0, "unit": "mm"}, "material": "AL6061-T6", "manufacturing_process": "cnc_milling", "mating_condition": "bearing_bore_concentric", "parent_surface": null}

Input: "4x M6 threaded holes on a bolt circle, 50mm PCD, sheet metal part"
Output: {"feature_type": "pattern", "geometry": {"diameter": 6.0, "count": 4, "pcd": 50.0, "unit": "mm"}, "material": "unspecified", "manufacturing_process": "sheet_metal", "mating_condition": "bolt_pattern_flange", "parent_surface": "planar_mounting_face"}

Input: "Cast iron base plate, 300mm x 200mm, primary mounting surface"
Output: {"feature_type": "surface", "geometry": {"length": 300.0, "width": 200.0, "unit": "mm"}, "material": "cast_iron", "manufacturing_process": "casting", "mating_condition": null, "parent_surface": null}"""

CLASSIFICATION_SYSTEM = """You are a GD&T classification expert trained on ASME Y14.5-2018. Given a structured feature record, classify the appropriate geometric characteristic.

Output ONLY valid JSON matching this schema:
{
  "primary_control": "string (geometric characteristic name)",
  "symbol": "string (Unicode symbol)",
  "symbol_name": "string",
  "tolerance_class": "tight|medium|loose",
  "datum_required": true or false,
  "modifier": "MMC|LMC|RFS|null",
  "reasoning_key": "string (short key explaining why)",
  "confidence": 0.0 to 1.0
}

The 14 ASME Y14.5-2018 geometric characteristics:

FORM (NO datums ever):
- Flatness \u25b1 - flat surfaces
- Straightness \u2014 - axes or line elements
- Circularity \u25cb - circular cross-sections
- Cylindricity \u232d - cylindrical surfaces

ORIENTATION (ALWAYS require datums):
- Perpendicularity \u22a5 - surfaces/axes 90 deg to datum
- Angularity \u2220 - surfaces/axes at specified angle to datum
- Parallelism // - surfaces/axes parallel to datum

LOCATION (ALWAYS require datums):
- Position \u2295 - hole patterns, features relative to datums
- Concentricity \u25ce - coaxial features (AVOID, use runout instead)
- Symmetry \u2261 - symmetric features about datum plane

PROFILE:
- Profile of a line \u2312 - 2D cross-section shape
- Profile of a surface \u2313 - 3D surface shape

RUNOUT (ALWAYS require datums):
- Circular runout \u2197 - single cross-section radial variation
- Total runout \u2197\u2197 - full-length radial variation

CRITICAL RULES:
1. Form controls (flatness, circularity, cylindricity, straightness) NEVER require datums
2. Orientation and location controls ALWAYS require datums
3. PREFER circular runout over concentricity per modern ASME Y14.5-2018 practice. Concentricity requires derived median points which are expensive to inspect. Runout achieves the same functional result.
4. Use MMC modifier for clearance-fit holes (bonus tolerance as hole departs from MMC)
5. Use LMC modifier for minimum-wall-thickness scenarios
6. RFS is the default per ASME Y14.5-2018 (no symbol needed)

Examples:

Input: {"feature_type": "boss", "geometry": {"diameter": 12.0, "height": 8.0}, "material": "AL6061-T6", "manufacturing_process": "cnc_milling", "mating_condition": "bearing_bore_concentric", "parent_surface": "planar_mounting_face"}
Output: {"primary_control": "perpendicularity", "symbol": "\u22a5", "symbol_name": "perpendicularity", "tolerance_class": "tight", "datum_required": true, "modifier": null, "reasoning_key": "bearing_alignment_perpendicularity", "confidence": 0.92}

Input: {"feature_type": "pattern", "geometry": {"diameter": 6.0, "count": 4, "pcd": 50.0}, "material": "mild_steel", "manufacturing_process": "sheet_metal", "mating_condition": "bolt_pattern_flange"}
Output: {"primary_control": "position", "symbol": "\u2295", "symbol_name": "position", "tolerance_class": "medium", "datum_required": true, "modifier": "MMC", "reasoning_key": "clearance_fit_bolt_pattern", "confidence": 0.95}

Input: {"feature_type": "surface", "geometry": {"length": 300.0, "width": 200.0}, "material": "cast_iron", "manufacturing_process": "casting", "mating_condition": null}
Output: {"primary_control": "flatness", "symbol": "\u25b1", "symbol_name": "flatness", "tolerance_class": "medium", "datum_required": false, "modifier": null, "reasoning_key": "primary_datum_surface_form", "confidence": 0.97}"""

WORKER_SYSTEM = """You are a GD&T output generator following ASME Y14.5-2018. Given extracted features, classification, datum scheme, relevant standards, and tolerance data, generate complete GD&T callouts with reasoning.

Output ONLY valid JSON matching this schema:
{
  "callouts": [
    {
      "feature": "string describing the feature",
      "symbol": "Unicode GD&T symbol",
      "symbol_name": "string name",
      "tolerance_value": "string with diameter symbol if applicable",
      "unit": "mm",
      "modifier": "MMC|LMC|null",
      "modifier_symbol": "\u24c2|\u24c1|null",
      "datum_references": ["A", "B"] or [],
      "feature_control_frame": "|symbol| tolerance modifier | datum_A | datum_B |",
      "reasoning": "string explaining why this control was chosen"
    }
  ],
  "summary": "1-2 sentence overall reasoning summary",
  "manufacturing_notes": "notes about process capability vs specified tolerance",
  "standards_references": ["ASME Y14.5-2018 section references"],
  "warnings": ["potential issues or considerations"]
}

Feature Control Frame format: |symbol| tolerance [modifier] | datum_A | datum_B | datum_C |
- Diameter symbol (\u2300) only for cylindrical tolerance zones
- Modifier follows tolerance value: \u24c2 for MMC, \u24c1 for LMC
- Form controls have NO datum references
- Datum order: primary | secondary | tertiary

Unicode symbols reference:
\u22a5 perpendicularity, \u2295 position, \u25b1 flatness, \u25cb circularity, \u232d cylindricity,
\u2220 angularity, // parallelism, \u2312 profile of line, \u2313 profile of surface,
\u2197 circular runout, \u25ce concentricity, \u2261 symmetry, \u2014 straightness
\u2300 diameter, \u24c2 MMC, \u24c1 LMC"""


def build_worker_user_prompt(
    features: dict,
    classification: dict,
    datum_scheme: dict,
    standards: list[dict],
    tolerances: dict,
) -> str:
    """Assemble the worker input from all pipeline stages."""
    sections = [
        "## Extracted Features",
        json.dumps(features, indent=2),
        "",
        "## GD&T Classification",
        json.dumps(classification, indent=2),
        "",
        "## Datum Scheme",
        json.dumps(datum_scheme, indent=2),
        "",
        "## Relevant ASME Y14.5 Standards",
        json.dumps(standards, indent=2),
        "",
        "## Manufacturing Tolerance Data",
        json.dumps(tolerances, indent=2),
        "",
        "Generate complete GD&T callouts with feature control frames, reasoning, and warnings.",
    ]
    return "\n".join(sections)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_prompts.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/models/prompts.py backend/tests/test_prompts.py
git commit -m "feat(backend): add system prompts and few-shot examples for Gemma models"
```

---

## Task 5: Async Ollama Client

**Files:**
- Create: `backend/models/gemma.py`
- Create: `backend/tests/test_gemma.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_gemma.py
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from models.gemma import OllamaClient, OllamaUnavailableError, OllamaParseError


@pytest.fixture
def ollama():
    return OllamaClient(base_url="http://localhost:11434")


def _mock_chat_response(content: dict) -> httpx.Response:
    """Create a mock Ollama /api/chat response."""
    return httpx.Response(
        200,
        json={
            "model": "gemma3n:e2b",
            "message": {"role": "assistant", "content": json.dumps(content)},
            "done": True,
        },
    )


@pytest.mark.asyncio
async def test_chat_json_parses_response(ollama):
    mock_content = {"feature_type": "boss", "geometry": {"diameter": 12.0}}
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp):
        result = await ollama.chat_json("gemma3n:e2b", [{"role": "user", "content": "test"}])
    assert result["feature_type"] == "boss"


@pytest.mark.asyncio
async def test_chat_json_raises_on_invalid_json(ollama):
    bad_resp = httpx.Response(
        200,
        json={
            "model": "gemma3n:e2b",
            "message": {"role": "assistant", "content": "not valid json {{{"},
            "done": True,
        },
    )
    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=bad_resp):
        with pytest.raises(OllamaParseError):
            await ollama.chat_json("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_on_connection_error(ollama):
    with patch.object(
        ollama.client, "post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.chat("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_raises_on_timeout(ollama):
    with patch.object(
        ollama.client, "post", new_callable=AsyncMock, side_effect=httpx.ReadTimeout("timeout")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.chat("gemma3n:e2b", [{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_extract_features_calls_correct_model(ollama):
    mock_content = {
        "feature_type": "boss",
        "geometry": {"diameter": 12.0},
        "material": "AL6061-T6",
        "manufacturing_process": "cnc_milling",
        "mating_condition": None,
        "parent_surface": None,
    }
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await ollama.extract_features("12mm aluminum boss")
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["model"] == "gemma3n:e2b"
        assert call_payload["format"] == "json"


@pytest.mark.asyncio
async def test_extract_features_with_image(ollama):
    mock_content = {"feature_type": "boss", "geometry": {}}
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await ollama.extract_features("describe this part", image_base64="base64data")
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["messages"][-1]["images"] == ["base64data"]


@pytest.mark.asyncio
async def test_classify_gdt_uses_specified_model(ollama):
    mock_content = {
        "primary_control": "perpendicularity",
        "symbol": "\u22a5",
        "symbol_name": "perpendicularity",
        "tolerance_class": "tight",
        "datum_required": True,
        "modifier": None,
        "reasoning_key": "test",
        "confidence": 0.9,
    }
    mock_resp = _mock_chat_response(mock_content)

    with patch.object(ollama.client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        await ollama.classify_gdt({"feature_type": "boss"}, model="gemma3:1b-gdt-ft")
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["model"] == "gemma3:1b-gdt-ft"


@pytest.mark.asyncio
async def test_health_check_success(ollama):
    mock_resp = httpx.Response(200, json={"models": [{"name": "gemma3n:e2b"}]})
    with patch.object(ollama.client, "get", new_callable=AsyncMock, return_value=mock_resp):
        result = await ollama.health_check()
        assert "models" in result


@pytest.mark.asyncio
async def test_health_check_ollama_down(ollama):
    with patch.object(
        ollama.client, "get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")
    ):
        with pytest.raises(OllamaUnavailableError):
            await ollama.health_check()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_gemma.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write Ollama client implementation**

```python
# backend/models/gemma.py
import json
import httpx


class OllamaUnavailableError(Exception):
    """Raised when Ollama server is not reachable."""
    pass


class OllamaParseError(Exception):
    """Raised when Ollama returns non-JSON or unparseable output."""
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    async def health_check(self) -> dict:
        """GET /api/tags -- verify Ollama is running and list loaded models."""
        try:
            resp = await self.client.get("/api/tags")
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise OllamaUnavailableError(
                f"Ollama not reachable at {self.base_url}: {e}"
            ) from e

    async def chat(
        self,
        model: str,
        messages: list[dict],
        format: str = "json",
        images: list[str] | None = None,
    ) -> dict:
        """Send a chat completion request to Ollama /api/chat."""
        if images:
            messages[-1]["images"] = images

        payload = {
            "model": model,
            "messages": messages,
            "format": format,
            "stream": False,
        }

        try:
            resp = await self.client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise OllamaUnavailableError(str(e)) from e
        except httpx.TimeoutException as e:
            raise OllamaUnavailableError(
                f"Ollama timed out on model {model}"
            ) from e

        return resp.json()

    async def chat_json(self, model: str, messages: list[dict], **kwargs) -> dict:
        """Chat and parse the response content as JSON."""
        result = await self.chat(model, messages, format="json", **kwargs)
        content = result["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise OllamaParseError(
                f"Model {model} returned invalid JSON: {content[:200]}"
            ) from e

    async def extract_features(
        self, text: str, image_base64: str | None = None
    ) -> dict:
        """Layer 1: Student -- Gemma 3n feature extraction."""
        from .prompts import FEATURE_EXTRACTION_SYSTEM

        messages = [
            {"role": "system", "content": FEATURE_EXTRACTION_SYSTEM},
            {"role": "user", "content": text},
        ]
        images = [image_base64] if image_base64 else None
        return await self.chat_json("gemma3n:e2b", messages, images=images)

    async def classify_gdt(
        self, features: dict, model: str = "gemma3:1b"
    ) -> dict:
        """Layer 2: Classifier -- Gemma GD&T classification."""
        from .prompts import CLASSIFICATION_SYSTEM

        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM},
            {"role": "user", "content": json.dumps(features)},
        ]
        return await self.chat_json(model, messages)

    async def generate_output(
        self,
        features: dict,
        classification: dict,
        datum_scheme: dict,
        standards: list[dict],
        tolerances: dict,
    ) -> dict:
        """Layer 5: Worker -- Gemma 3n output generation."""
        from .prompts import WORKER_SYSTEM, build_worker_user_prompt

        messages = [
            {"role": "system", "content": WORKER_SYSTEM},
            {
                "role": "user",
                "content": build_worker_user_prompt(
                    features, classification, datum_scheme, standards, tolerances
                ),
            },
        ]
        return await self.chat_json("gemma3n:e2b", messages)

    async def close(self):
        await self.client.aclose()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_gemma.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/models/gemma.py backend/tests/test_gemma.py
git commit -m "feat(backend): add async Ollama HTTP client with error handling"
```

---

## Task 6: Brain Database

**Files:**
- Create: `backend/brain/database.py`
- Create: `backend/tests/test_database.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_database.py
import pytest
import aiosqlite
from brain.database import Database


@pytest.fixture
async def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE geometric_characteristics (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                datum_required INTEGER NOT NULL,
                rules TEXT,
                when_to_use TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("\u22a5", "perpendicularity", "orientation", 1, '["7.2"]', "axis control", '["forgetting datum"]'),
        )
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("\u25b1", "flatness", "form", 0, '["5.4"]', "flat surfaces", '["adding datums"]'),
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_connect_missing_db():
    with pytest.raises(FileNotFoundError):
        await Database.connect("/nonexistent/path/brain.db")


@pytest.mark.asyncio
async def test_fetchone(test_db):
    row = await test_db.fetchone(
        "SELECT * FROM geometric_characteristics WHERE symbol = ?", ("\u22a5",)
    )
    assert row is not None
    assert row["name"] == "perpendicularity"
    assert row["datum_required"] == 1


@pytest.mark.asyncio
async def test_fetchone_missing(test_db):
    row = await test_db.fetchone(
        "SELECT * FROM geometric_characteristics WHERE symbol = ?", ("FAKE",)
    )
    assert row is None


@pytest.mark.asyncio
async def test_fetchall(test_db):
    rows = await test_db.fetchall("SELECT * FROM geometric_characteristics")
    assert len(rows) == 2
    names = [r["name"] for r in rows]
    assert "perpendicularity" in names
    assert "flatness" in names
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_database.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write database implementation**

```python
# backend/brain/database.py
import aiosqlite
from pathlib import Path


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None

    @classmethod
    async def connect(cls, path: str) -> "Database":
        db_path = Path(path)
        if not db_path.exists():
            raise FileNotFoundError(
                f"Brain database not found at {path}. "
                f"Run 'python scripts/seed_database.py' first."
            )
        db = cls()
        db.conn = await aiosqlite.connect(str(db_path))
        db.conn.row_factory = aiosqlite.Row
        await db.conn.execute("PRAGMA journal_mode=WAL")
        return db

    async def fetchone(self, query: str, params: tuple = ()) -> dict | None:
        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    async def fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def close(self):
        if self.conn:
            await self.conn.close()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_database.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/brain/database.py backend/tests/test_database.py
git commit -m "feat(backend): add async SQLite database layer"
```

---

## Task 7: Brain Lookups

**Files:**
- Create: `backend/brain/lookup.py`
- Create: `backend/tests/test_lookup.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_lookup.py
import pytest
import aiosqlite
from brain.database import Database
from brain.lookup import BrainLookup


@pytest.fixture
async def brain(tmp_path):
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE geometric_characteristics (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                datum_required INTEGER NOT NULL,
                applicable_modifiers TEXT,
                applicable_features TEXT,
                rules TEXT,
                when_to_use TEXT,
                when_not_to_use TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO geometric_characteristics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "\u22a5", "perpendicularity", "orientation", 1,
                '["MMC", "LMC"]', '["boss", "hole"]',
                '["7.2"]', "axis perpendicular to datum",
                "not for form control", '["forgetting datum"]',
            ),
        )
        await conn.execute("""
            CREATE TABLE datum_patterns (
                pattern_name TEXT PRIMARY KEY,
                description TEXT,
                primary_type TEXT,
                secondary_type TEXT,
                tertiary_type TEXT,
                example_parts TEXT,
                common_mistakes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO datum_patterns VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "boss_on_plate", "Boss perpendicular to flat plate",
                "planar", "cylindrical", None,
                '["bracket", "housing"]', '["wrong datum order"]',
            ),
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield BrainLookup(db)
    await db.close()


@pytest.mark.asyncio
async def test_lookup_standard_by_symbol(brain):
    result = await brain.lookup_standard("\u22a5")
    assert result is not None
    assert result["name"] == "perpendicularity"


@pytest.mark.asyncio
async def test_lookup_standard_by_name(brain):
    result = await brain.lookup_standard("perpendicularity")
    assert result is not None
    assert result["symbol"] == "\u22a5"


@pytest.mark.asyncio
async def test_lookup_standard_missing(brain):
    result = await brain.lookup_standard("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_geometric_characteristic_parses_json_fields(brain):
    result = await brain.get_geometric_characteristic("\u22a5")
    assert result is not None
    assert result["applicable_modifiers"] == ["MMC", "LMC"]
    assert result["applicable_features"] == ["boss", "hole"]
    assert result["rules"] == ["7.2"]


@pytest.mark.asyncio
async def test_lookup_datum_pattern(brain):
    result = await brain.lookup_datum_pattern("boss")
    assert result is not None
    assert result["pattern_name"] == "boss_on_plate"
    assert result["example_parts"] == ["bracket", "housing"]


@pytest.mark.asyncio
async def test_search_standards(brain):
    results = await brain.search_standards("perpendicular")
    assert len(results) >= 1
    assert results[0]["name"] == "perpendicularity"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_lookup.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write lookup implementation**

```python
# backend/brain/lookup.py
import json
from .database import Database


JSON_FIELDS = [
    "applicable_modifiers",
    "applicable_features",
    "rules",
    "common_mistakes",
    "example_parts",
]


def _parse_json_fields(row: dict | None) -> dict | None:
    """Parse JSON string fields in a database row."""
    if row is None:
        return None
    for field in JSON_FIELDS:
        if field in row and row[field] and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except json.JSONDecodeError:
                pass
    return row


class BrainLookup:
    def __init__(self, db: Database):
        self.db = db

    async def lookup_standard(self, code: str) -> dict | None:
        """Fetch ASME Y14.5 section by symbol or name."""
        return await self.db.fetchone(
            "SELECT * FROM geometric_characteristics WHERE symbol = ? OR name = ?",
            (code, code),
        )

    async def get_geometric_characteristic(self, symbol: str) -> dict | None:
        """Full rule set for a given GD&T symbol with parsed JSON fields."""
        row = await self.db.fetchone(
            "SELECT * FROM geometric_characteristics WHERE symbol = ?",
            (symbol,),
        )
        return _parse_json_fields(row)

    async def lookup_datum_pattern(self, feature_type: str) -> dict | None:
        """Match features to common datum scheme patterns."""
        row = await self.db.fetchone(
            "SELECT * FROM datum_patterns WHERE pattern_name LIKE ?",
            (f"%{feature_type}%",),
        )
        return _parse_json_fields(row)

    async def search_standards(self, query: str) -> list[dict]:
        """Search across standards by name or usage text."""
        return await self.db.fetchall(
            "SELECT * FROM geometric_characteristics WHERE name LIKE ? OR when_to_use LIKE ?",
            (f"%{query}%", f"%{query}%"),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_lookup.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/brain/lookup.py backend/tests/test_lookup.py
git commit -m "feat(backend): add ASME standard and datum pattern lookups"
```

---

## Task 8: Manufacturing Lookups

**Files:**
- Create: `backend/brain/manufacturing.py`
- Create: `backend/tests/test_manufacturing.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_manufacturing.py
import pytest
import aiosqlite
from brain.database import Database
from brain.manufacturing import ManufacturingLookup


@pytest.fixture
async def mfg(tmp_path):
    db_path = tmp_path / "test_brain.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE tolerance_tables (
                id INTEGER PRIMARY KEY,
                process TEXT NOT NULL,
                material TEXT NOT NULL,
                feature_type TEXT NOT NULL,
                min_mm REAL,
                max_mm REAL,
                achievable_best_mm REAL,
                notes TEXT
            )
        """)
        await conn.execute(
            "INSERT INTO tolerance_tables VALUES (1, 'cnc_milling', 'AL6061-T6', 'position', 0.02, 0.1, 0.01, 'tight with fixturing')"
        )
        await conn.execute(
            "INSERT INTO tolerance_tables VALUES (2, 'cnc_milling', 'steel_4140', 'position', 0.03, 0.15, 0.02, 'harder material')"
        )
        await conn.execute("""
            CREATE TABLE material_properties (
                material_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                common_processes TEXT,
                machinability TEXT,
                thermal_expansion_ppm_c REAL
            )
        """)
        await conn.execute(
            """INSERT INTO material_properties VALUES (
                'AL6061-T6', 'Aluminum 6061-T6', 'aluminum',
                '["cnc_milling", "turning", "sheet_metal"]', 'excellent', 23.6
            )"""
        )
        await conn.commit()
    db = await Database.connect(str(db_path))
    yield ManufacturingLookup(db)
    await db.close()


@pytest.mark.asyncio
async def test_get_tolerance_range(mfg):
    result = await mfg.get_tolerance_range("cnc_milling", "AL6061-T6", "position")
    assert result is not None
    assert result["min_mm"] == 0.02
    assert result["max_mm"] == 0.1


@pytest.mark.asyncio
async def test_get_tolerance_range_missing(mfg):
    result = await mfg.get_tolerance_range("casting", "bronze", "position")
    assert result is None


@pytest.mark.asyncio
async def test_get_process_capability(mfg):
    results = await mfg.get_process_capability("cnc_milling")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_get_material_properties(mfg):
    result = await mfg.get_material_properties("AL6061-T6")
    assert result is not None
    assert result["name"] == "Aluminum 6061-T6"
    assert result["common_processes"] == ["cnc_milling", "turning", "sheet_metal"]


@pytest.mark.asyncio
async def test_get_material_properties_by_partial_name(mfg):
    result = await mfg.get_material_properties("Aluminum")
    assert result is not None
    assert result["material_id"] == "AL6061-T6"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_manufacturing.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write manufacturing implementation**

```python
# backend/brain/manufacturing.py
import json
from .database import Database


class ManufacturingLookup:
    def __init__(self, db: Database):
        self.db = db

    async def get_tolerance_range(
        self, process: str, material: str, feature_type: str
    ) -> dict | None:
        """Lookup typical achievable tolerance for a process/material/feature combo."""
        return await self.db.fetchone(
            """SELECT * FROM tolerance_tables
               WHERE process = ? AND material = ? AND feature_type = ?""",
            (process, material, feature_type),
        )

    async def get_process_capability(self, process: str) -> list[dict]:
        """Full process capability profile across all materials."""
        return await self.db.fetchall(
            "SELECT * FROM tolerance_tables WHERE process = ?",
            (process,),
        )

    async def get_material_properties(self, material: str) -> dict | None:
        """Material properties relevant to tolerancing."""
        row = await self.db.fetchone(
            "SELECT * FROM material_properties WHERE material_id = ? OR name LIKE ?",
            (material, f"%{material}%"),
        )
        if row and row.get("common_processes") and isinstance(row["common_processes"], str):
            try:
                row["common_processes"] = json.loads(row["common_processes"])
            except json.JSONDecodeError:
                pass
        return row
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_manufacturing.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/brain/manufacturing.py backend/tests/test_manufacturing.py
git commit -m "feat(backend): add manufacturing tolerance and material lookups"
```

---

## Task 9: Embedder (Sentence-Transformers)

**Files:**
- Create: `backend/models/embedder.py`
- Create: `backend/tests/test_embedder.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_embedder.py
import numpy as np
import pytest
from pathlib import Path
from models.embedder import Embedder


@pytest.fixture
def fake_embeddings(tmp_path):
    """Create a fake NPZ file with pre-computed embeddings."""
    keys = ["flatness", "perpendicularity", "position", "circular_runout"]
    rng = np.random.default_rng(42)
    embeddings = rng.random((4, 384)).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    npz_path = tmp_path / "standards_embeddings.npz"
    np.savez(
        str(npz_path),
        embeddings=embeddings,
        keys=np.array(keys),
    )
    return str(npz_path)


@pytest.fixture
def embedder(fake_embeddings):
    e = Embedder()
    e.load(embeddings_path=fake_embeddings)
    return e


def test_load_creates_model(embedder):
    assert embedder.model is not None


def test_load_reads_embeddings(embedder):
    assert embedder.standard_embeddings is not None
    assert embedder.standard_embeddings.shape == (4, 384)
    assert len(embedder.standard_keys) == 4


def test_match_standards_returns_results(embedder):
    results = embedder.match_standards("flat surface control", top_k=2)
    assert len(results) == 2
    assert "key" in results[0]
    assert "score" in results[0]


def test_match_standards_respects_top_k(embedder):
    results = embedder.match_standards("position", top_k=1)
    assert len(results) == 1


def test_match_standards_no_embeddings():
    e = Embedder()
    e.model = True  # fake to avoid NotReady
    e.standard_embeddings = None
    results = e.match_standards("test", top_k=3)
    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_embedder.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write embedder implementation**

```python
# backend/models/embedder.py
import numpy as np
from pathlib import Path


class Embedder:
    def __init__(self):
        self.model = None
        self.standard_embeddings: np.ndarray | None = None
        self.standard_keys: list[str] = []

    def load(self, embeddings_path: str = "data/embeddings/standards_embeddings.npz"):
        """Load the sentence-transformer model and pre-computed embeddings.

        Called during startup. Takes ~3 seconds for model load.
        """
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        emb_path = Path(embeddings_path)
        if emb_path.exists():
            data = np.load(str(emb_path))
            self.standard_embeddings = data["embeddings"]
            self.standard_keys = data["keys"].tolist()

    def match_standards(self, query: str, top_k: int = 5) -> list[dict]:
        """Find top-K ASME Y14.5 sections most relevant to the query."""
        if self.standard_embeddings is None:
            return []

        query_embedding = self.model.encode(query, normalize_embeddings=True)
        similarities = np.dot(self.standard_embeddings, query_embedding)
        top_k = min(top_k, len(self.standard_keys))
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "key": self.standard_keys[idx],
                "score": float(similarities[idx]),
            })
        return results
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_embedder.py -v`
Expected: All PASS (first run downloads MiniLM model ~90MB)

**Step 5: Commit**

```bash
git add backend/models/embedder.py backend/tests/test_embedder.py
git commit -m "feat(backend): add sentence-transformers embedder for standards matching"
```

---

## Task 10: Routes + Pipeline Orchestration

**Files:**
- Create: `backend/api/routes.py`
- Create: `backend/tests/test_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_routes.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from api.routes import router


def _make_app():
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    # Mock Ollama client
    ollama = AsyncMock()
    ollama.extract_features = AsyncMock(return_value={
        "feature_type": "boss",
        "geometry": {"diameter": 12.0, "height": 8.0, "unit": "mm"},
        "material": "AL6061-T6",
        "manufacturing_process": "cnc_milling",
        "mating_condition": "bearing_bore_concentric",
        "parent_surface": "planar_mounting_face",
    })
    ollama.classify_gdt = AsyncMock(return_value={
        "primary_control": "perpendicularity",
        "symbol": "\u22a5",
        "symbol_name": "perpendicularity",
        "tolerance_class": "tight",
        "datum_required": True,
        "modifier": None,
        "reasoning_key": "bearing_alignment",
        "confidence": 0.92,
    })
    ollama.generate_output = AsyncMock(return_value={
        "callouts": [{
            "feature": "boss",
            "symbol": "\u22a5",
            "symbol_name": "perpendicularity",
            "tolerance_value": "\u23000.05",
            "unit": "mm",
            "modifier": None,
            "modifier_symbol": None,
            "datum_references": ["A"],
            "feature_control_frame": "|\u22a5| \u23000.05 | A |",
            "reasoning": "Bearing alignment",
        }],
        "summary": "Perpendicularity for bearing alignment",
        "manufacturing_notes": "CNC can hold this tolerance",
        "standards_references": ["ASME Y14.5-2018 7.2"],
        "warnings": ["Consider position callout for bore"],
    })
    ollama.health_check = AsyncMock(return_value={"models": [{"name": "gemma3n:e2b"}]})

    # Mock embedder
    embedder = MagicMock()
    embedder.match_standards = MagicMock(return_value=[
        {"key": "7.2", "score": 0.89}
    ])

    # Mock brain
    brain_lookup = AsyncMock()
    brain_lookup.lookup_standard = AsyncMock(return_value={"name": "perpendicularity"})
    brain_lookup.search_standards = AsyncMock(return_value=[{"name": "perpendicularity"}])

    # Mock manufacturing
    manufacturing = AsyncMock()
    manufacturing.get_tolerance_range = AsyncMock(return_value={
        "min_mm": 0.02, "max_mm": 0.1, "achievable_best_mm": 0.01,
    })
    manufacturing.get_material_properties = AsyncMock(return_value={
        "name": "AL6061-T6", "machinability": "excellent",
    })
    manufacturing.get_process_capability = AsyncMock(return_value=[
        {"process": "cnc_milling", "material": "AL6061-T6", "min_mm": 0.02},
    ])

    app.state.ollama = ollama
    app.state.embedder = embedder
    app.state.brain_lookup = brain_lookup
    app.state.manufacturing_lookup = manufacturing

    return app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_analyze_returns_sse_stream():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={"description": "12mm aluminum boss, CNC machined"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse(resp.text)
        event_types = [e["event"] for e in events]

        assert "feature_extraction" in event_types
        assert "datum_recommendation" in event_types
        assert "gdt_callouts" in event_types
        assert "reasoning" in event_types
        assert "warnings" in event_types
        assert "analysis_complete" in event_types


@pytest.mark.asyncio
async def test_analyze_with_compare_flag():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={"description": "12mm boss", "compare": True},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        event_types = [e["event"] for e in events]
        assert "classification_comparison" in event_types


@pytest.mark.asyncio
async def test_analyze_metadata_has_zero_cloud_calls():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={"description": "12mm boss"},
        )
        events = _parse_sse(resp.text)
        complete_events = [e for e in events if e.get("event") == "analysis_complete"]
        assert len(complete_events) == 1
        data = json.loads(complete_events[0]["data"])
        assert data["metadata"]["cloud_calls"] == 0
        assert data["metadata"]["connectivity_required"] is False


@pytest.mark.asyncio
async def test_standards_lookup():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/standards/\u22a5")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_standards_search():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/standards/search?q=perpendicular")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tolerances_lookup():
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tolerances?process=cnc_milling&material=AL6061-T6")
        assert resp.status_code == 200


def _parse_sse(text: str) -> list[dict]:
    """Parse raw SSE text into a list of {event, data} dicts."""
    events = []
    current = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_routes.py -v`
Expected: FAIL with `ImportError`

**Step 3: Write routes implementation**

```python
# backend/api/routes.py
import asyncio
import time
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from .schemas import AnalyzeRequest
from .streaming import sse_event, sse_error
from ..models.gemma import OllamaUnavailableError, OllamaParseError

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


@router.get("/standards/search")
async def search_standards(request: Request, q: str = Query(...)):
    """Semantic search across standards database."""
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        return {"results": []}
    results = embedder.match_standards(q, top_k=5)
    return {"results": results}


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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/test_routes.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/api/routes.py backend/tests/test_routes.py
git commit -m "feat(backend): add pipeline orchestration and API routes"
```

---

## Task 11: FastAPI App Entry Point

**Files:**
- Create: `backend/api/main.py`

**Step 1: Write main app implementation**

```python
# backend/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from ..models.gemma import OllamaClient
from ..models.embedder import Embedder
from ..brain.database import Database
from ..brain.lookup import BrainLookup
from ..brain.manufacturing import ManufacturingLookup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    app.state.ollama = OllamaClient()

    app.state.embedder = Embedder()
    try:
        app.state.embedder.load()
    except Exception as e:
        print(f"WARNING: Embedder failed to load: {e}")
        app.state.embedder = None

    try:
        db = await Database.connect("data/brain.db")
        app.state.brain_lookup = BrainLookup(db)
        app.state.manufacturing_lookup = ManufacturingLookup(db)
        app.state.db = db
    except FileNotFoundError as e:
        print(f"WARNING: {e}")
        app.state.brain_lookup = None
        app.state.manufacturing_lookup = None
        app.state.db = None

    try:
        await app.state.ollama.health_check()
        print("Ollama connected, models available")
    except Exception as e:
        print(f"WARNING: Ollama not available: {e}")

    yield

    # --- Shutdown ---
    await app.state.ollama.close()
    if getattr(app.state, "db", None):
        await app.state.db.close()


app = FastAPI(
    title="ToleranceAI",
    description="AI-powered GD&T copilot for mechanical engineers",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
```

**Step 2: Run full test suite**

Run: `cd /Users/jdhiman/Documents/copilots/backend && uv run pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/api/main.py
git commit -m "feat(backend): add FastAPI app with lifespan, CORS, and route mounting"
```

---

## Task 12: Integration Smoke Test

**Step 1: Start the server (requires Ollama running)**

Run: `cd /Users/jdhiman/Documents/copilots && uv run --project backend uvicorn backend.api.main:app --reload --port 8000`

If Ollama is not running, expect WARNING messages but the server should still start.

**Step 2: Test health endpoint**

Run: `curl http://localhost:8000/api/health`
Expected: JSON with status "healthy" or "degraded"

**Step 3: Test SSE stream (requires Ollama + gemma3n:e2b model)**

Run:
```bash
curl -N -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"description": "Cylindrical aluminum boss, 12mm diameter, needs to be perpendicular to the mounting face within 0.05mm. CNC machined, mates with a bearing bore."}'
```

Expected: SSE events streaming in order: feature_extraction, datum_recommendation, gdt_callouts, reasoning, warnings, analysis_complete

**Step 4: Test comparison mode**

Run:
```bash
curl -N -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"description": "12mm boss on mounting face", "compare": true}'
```

Expected: SSE stream includes `classification_comparison` event

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(backend): complete backend pipeline - all tests passing"
```

---

## Verification Checklist

- [ ] `uv run pytest tests/ -v` -- all tests pass
- [ ] Server starts without Ollama (graceful degradation, warnings printed)
- [ ] `/api/health` returns JSON
- [ ] With Ollama running: `/api/analyze` streams SSE events
- [ ] SSE events arrive in order: feature_extraction -> datum_recommendation -> gdt_callouts -> reasoning -> warnings -> analysis_complete
- [ ] `compare=true` produces classification_comparison event
- [ ] analysis_complete metadata shows cloud_calls: 0
- [ ] CORS allows requests from http://localhost:5173
