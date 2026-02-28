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
