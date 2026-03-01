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

    # Mock mlx-vlm client (PaliGemma 2 -- image description only)
    vlm = AsyncMock()
    vlm.describe_image = AsyncMock(return_value="A cylindrical aluminum boss, 12mm diameter, on a flat mounting face")
    # Mock Ollama client (feature extraction + classifier + worker layers)
    ollama = AsyncMock()
    ollama.extract_features = AsyncMock(return_value={
        "feature_type": "boss",
        "geometry": {"diameter": 12.0, "height": 8.0, "unit": "mm"},
        "material": "AL6061-T6",
        "manufacturing_process": "cnc_milling",
        "mating_condition": "bearing_bore_concentric",
        "parent_surface": "planar_mounting_face",
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
    ollama.health_check = AsyncMock(return_value={"models": [{"name": "gemma3:1b"}]})

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
    app.state.vlm = vlm
    app.state.embedder = embedder
    app.state.brain_lookup = brain_lookup
    app.state.manufacturing_lookup = manufacturing
    app.state.freecad = None  # No FreeCAD by default in tests

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

        assert "progress" in event_types
        assert "feature_extraction" in event_types
        assert "cad_context" in event_types
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
