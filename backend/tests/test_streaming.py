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
