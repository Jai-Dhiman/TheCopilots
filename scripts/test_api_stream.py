#!/usr/bin/env python3
"""API SSE stream test -- no browser needed.

Sends a POST to the running backend's /api/analyze endpoint and
prints each SSE event as it arrives, with timing. Use this to
isolate whether the problem is in the backend SSE plumbing vs
the frontend.

Requires: the backend server running (uvicorn api.main:app)

Usage:
    # Text-only
    python scripts/test_api_stream.py --text "12mm aluminum boss, CNC machined"

    # With a saved image
    python scripts/test_api_stream.py --image screenshot.png --text "identify the main feature"

    # Capture current screen (macOS)
    python scripts/test_api_stream.py --screenshot --text "cylindrical boss"

    # Custom server URL
    python scripts/test_api_stream.py --url http://localhost:8000 --text "12mm boss"
"""

import argparse
import base64
import json
import os
import sys
import time

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: uv pip install httpx")
    sys.exit(1)


def capture_screenshot() -> bytes:
    """Capture the current screen using PIL.ImageGrab (macOS). Returns PNG bytes."""
    try:
        from PIL import ImageGrab
    except ImportError:
        print("ERROR: Pillow is required for --screenshot. Install with: uv pip install Pillow")
        sys.exit(1)

    import io

    print("Capturing screen in 3 seconds... switch to your FreeCAD window!")
    time.sleep(3)

    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    print(f"Screen captured: {img.size[0]}x{img.size[1]}")
    return buf.getvalue()


def load_image_bytes(image_path: str) -> bytes:
    """Read an image file and return raw bytes."""
    with open(image_path, "rb") as f:
        return f.read()


def truncate(s: str, max_len: int = 200) -> str:
    """Truncate a string for display."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"... ({len(s)} chars total)"


def parse_sse_lines(lines: list[str]) -> list[dict]:
    """Parse raw SSE text into events. Each event has 'event' and 'data' keys."""
    events = []
    current_event = None
    current_data_lines = []

    for line in lines:
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data_lines.append(line[len("data:"):].strip())
        elif line.strip() == "":
            # Blank line = end of event
            if current_event is not None or current_data_lines:
                data_str = "\n".join(current_data_lines)
                events.append({
                    "event": current_event or "message",
                    "data": data_str,
                })
                current_event = None
                current_data_lines = []

    # Handle trailing event without final blank line
    if current_event is not None or current_data_lines:
        data_str = "\n".join(current_data_lines)
        events.append({
            "event": current_event or "message",
            "data": data_str,
        })

    return events


def main():
    parser = argparse.ArgumentParser(
        description="Test the /api/analyze SSE stream (server must be running)"
    )
    parser.add_argument(
        "--text", "-t",
        default="Table made up of a rectangular surface and 4 legs that are press fit at each corner. The rectangular surface is 350x700x50 mm, with 4 holes in each corner where the legs are press fit. Each leg is 100 mm in diameter and 700 mm in length. Each leg has a cylindrical piece of diameter 60 mm at the top (50 mm tall).",
        help="Text description of the part feature",
    )
    parser.add_argument(
        "--image", "-i",
        help="Path to an image file (PNG/JPEG) to send",
    )
    parser.add_argument(
        "--screenshot", "-s",
        action="store_true",
        help="Capture the current screen (macOS) after a 3-second delay",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend server base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)",
    )
    args = parser.parse_args()

    if args.image and args.screenshot:
        print("ERROR: Use --image or --screenshot, not both.")
        sys.exit(1)

    # -- Prepare image --
    image_base64 = None
    if args.screenshot:
        image_bytes = capture_screenshot()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    elif args.image:
        if not os.path.isfile(args.image):
            print(f"ERROR: Image file not found: {args.image}")
            sys.exit(1)
        image_bytes = load_image_bytes(args.image)
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # -- Build request payload --
    payload = {
        "description": args.text,
        "image_base64": image_base64,
    }

    analyze_url = f"{args.url.rstrip('/')}/api/analyze"

    print("=" * 60)
    print("TEST: API SSE Stream")
    print("=" * 60)
    print(f"Server:      {args.url}")
    print(f"Endpoint:    POST {analyze_url}")
    print(f"Text:        {args.text}")
    print(f"Image:       {'yes' if image_base64 else 'no'}" + (f" ({len(image_base64)} base64 chars)" if image_base64 else ""))
    print(f"Timeout:     {args.timeout}s")
    print()

    # -- Step 1: Health check --
    print("--- HEALTH CHECK ---")
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{args.url.rstrip('/')}/api/health")
            print(f"  Status:       {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', '?')}")
            health = resp.json()
            print(f"  Ollama:       {health.get('ollama', '?')}")
            print(f"  Models:       {health.get('models_loaded', '?')}")
            if health.get("status") != "healthy":
                print(f"  WARNING: Server reports status={health.get('status')}")
    except httpx.ConnectError:
        print(f"  ERROR: Cannot connect to {args.url}")
        print(f"  Is the server running? Start with: cd backend && uvicorn api.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"  ERROR: Health check failed: {e}")
        sys.exit(1)
    print()

    # -- Step 2: Send analyze request and stream SSE --
    print("--- SSE STREAM ---")
    t_start = time.monotonic()
    t_last_event = t_start
    event_count = 0
    events_received = []

    try:
        with httpx.Client(timeout=httpx.Timeout(args.timeout, connect=10)) as client:
            with client.stream(
                "POST",
                analyze_url,
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as response:
                print(f"  HTTP Status:  {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type', '?')}")
                print()

                if response.status_code != 200:
                    # Read full body on error
                    body = response.read().decode("utf-8", errors="replace")
                    print(f"  ERROR: Non-200 response")
                    print(f"  Body: {truncate(body, 500)}")
                    sys.exit(1)

                # Accumulate lines and parse SSE events as they arrive
                line_buffer = []
                for line in response.iter_lines():
                    line_buffer.append(line)

                    # A blank line signals end of an SSE event
                    if line.strip() == "":
                        events = parse_sse_lines(line_buffer)
                        for evt in events:
                            now = time.monotonic()
                            delta_from_start = now - t_start
                            delta_from_last = now - t_last_event
                            t_last_event = now
                            event_count += 1

                            event_type = evt["event"]
                            data_str = evt["data"]

                            # Try to parse data as JSON for prettier display
                            try:
                                data_obj = json.loads(data_str)
                                data_display = json.dumps(data_obj, indent=2)
                            except (json.JSONDecodeError, TypeError):
                                data_display = data_str

                            print(f"  [{event_count}] event: {event_type}  (+{delta_from_last:.1f}s, total {delta_from_start:.1f}s)")
                            # Indent the data for readability
                            for data_line in data_display.split("\n"):
                                print(f"       {data_line}")
                            print()

                            events_received.append({
                                "event": event_type,
                                "data": data_str,
                                "time_from_start": delta_from_start,
                                "time_from_last": delta_from_last,
                            })

                        line_buffer = []

    except httpx.ConnectError:
        print(f"  ERROR: Cannot connect to {analyze_url}")
        print(f"  Is the server running? Start with: cd backend && uvicorn api.main:app --reload")
        sys.exit(1)
    except httpx.ReadTimeout:
        elapsed = time.monotonic() - t_start
        print(f"  ERROR: Read timeout after {elapsed:.1f}s (limit: {args.timeout}s)")
        print(f"  Events received before timeout: {event_count}")
    except Exception as e:
        elapsed = time.monotonic() - t_start
        print(f"  ERROR: {type(e).__name__}: {e}")
        print(f"  Events received before error: {event_count}")

    t_total = time.monotonic() - t_start

    # -- Summary --
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total time:       {t_total:.1f}s")
    print(f"  Events received:  {event_count}")

    if events_received:
        event_types = [e["event"] for e in events_received]
        print(f"  Event types:      {', '.join(event_types)}")

        # Check for expected pipeline events
        expected = {"feature_extraction", "datum_recommendation", "gdt_callouts", "reasoning", "analysis_complete"}
        received_set = set(event_types)
        missing = expected - received_set
        if missing:
            print(f"  MISSING events:   {', '.join(sorted(missing))}")
        else:
            print(f"  Pipeline:         COMPLETE (all expected events received)")

        # Check for errors
        error_events = [e for e in events_received if e["event"] == "error"]
        if error_events:
            print(f"  ERRORS:")
            for err in error_events:
                print(f"    {err['data']}")
    else:
        print(f"  WARNING: No events received!")
        print(f"  Possible causes:")
        print(f"    - mlx-vlm model not loaded (check server startup logs)")
        print(f"    - Inference timeout (model taking too long)")
        print(f"    - SSE connection dropped before first event")
    print()


if __name__ == "__main__":
    main()
