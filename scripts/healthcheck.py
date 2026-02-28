"""Health check script for ToleranceAI API endpoints.

Hits every endpoint on the running server and reports status.
Requires: uvicorn running on localhost:8000 (default).

Usage:
    python scripts/healthcheck.py
    python scripts/healthcheck.py --base-url http://localhost:9000
    python scripts/healthcheck.py --verbose
"""

import argparse
import asyncio
import json
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

ANALYZE_PAYLOAD = {
    "description": "12mm aluminum boss, CNC machined, mates with a bearing bore",
}

ANALYZE_COMPARE_PAYLOAD = {
    "description": "4x M6 threaded holes on a bolt circle, 50mm PCD, sheet metal part",
    "compare": True,
}

EXPECTED_SSE_EVENTS = [
    "feature_extraction",
    "datum_recommendation",
    "gdt_callouts",
    "reasoning",
    "warnings",
    "analysis_complete",
]


def parse_sse(text: str) -> list[dict]:
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


class Check:
    def __init__(self, name: str):
        self.name = name
        self.status = "SKIP"
        self.latency_ms: float = 0.0
        self.detail = ""
        self.errors: list[str] = []

    def pass_(self, detail: str = ""):
        self.status = "PASS"
        self.detail = detail

    def fail(self, error: str):
        self.status = "FAIL"
        self.errors.append(error)

    def warn(self, msg: str):
        if self.status != "FAIL":
            self.status = "WARN"
        self.detail = msg


async def check_health(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("GET /api/health")
    t0 = time.monotonic()
    try:
        resp = await client.get(f"{base_url}/api/health")
        c.latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()
        if verbose:
            print(f"    Response: {json.dumps(data, indent=2)}")

        status = data.get("status")
        if status == "healthy":
            models = data.get("models_loaded", [])
            c.pass_(f"ollama=connected, models={models}")
        elif status == "degraded":
            c.warn(f"degraded: {data.get('ollama', 'unknown')}")
        else:
            c.fail(f"unexpected status: {status}")
    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    except httpx.HTTPStatusError as e:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail(f"HTTP {e.response.status_code}")
    return c


async def check_analyze(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("POST /api/analyze (SSE)")
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{base_url}/api/analyze",
            json=ANALYZE_PAYLOAD,
            timeout=120.0,
        )
        c.latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            c.fail(f"expected text/event-stream, got {content_type}")
            return c

        events = parse_sse(resp.text)
        event_types = [e.get("event") for e in events]
        if verbose:
            print(f"    Events received: {event_types}")
            for ev in events:
                print(f"      {ev['event']}: {ev.get('data', '')[:120]}")

        # Check for error events
        error_events = [e for e in events if e.get("event") == "error"]
        if error_events:
            error_data = error_events[0].get("data", "")
            try:
                error_parsed = json.loads(error_data)
                error_layer = error_parsed.get("layer", "")
            except (json.JSONDecodeError, AttributeError):
                error_layer = ""
            # Infrastructure errors (Ollama/VLM not loaded) are warnings, not failures
            if error_layer in ("ollama", "vlm"):
                c.warn(f"infra: {error_data}")
                return c
            c.fail(f"pipeline error: {error_data}")
            return c

        # Verify all expected event types present
        missing = [e for e in EXPECTED_SSE_EVENTS if e not in event_types]
        if missing:
            c.fail(f"missing SSE events: {missing}")
            return c

        # Validate analysis_complete metadata
        complete = [e for e in events if e.get("event") == "analysis_complete"]
        if complete:
            meta = json.loads(complete[0]["data"])
            cloud_calls = meta.get("metadata", {}).get("cloud_calls")
            total_ms = meta.get("metadata", {}).get("total_latency_ms", 0)
            if cloud_calls != 0:
                c.fail(f"cloud_calls={cloud_calls}, expected 0")
                return c
            c.pass_(f"all events received, pipeline={total_ms}ms")
        else:
            c.fail("analysis_complete event missing")

    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    except httpx.ReadTimeout:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("request timed out (120s)")
    except httpx.HTTPStatusError as e:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail(f"HTTP {e.response.status_code}")
    return c


async def check_analyze_compare(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("POST /api/analyze (compare)")
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{base_url}/api/analyze",
            json=ANALYZE_COMPARE_PAYLOAD,
            timeout=120.0,
        )
        c.latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()

        events = parse_sse(resp.text)
        event_types = [e.get("event") for e in events]
        if verbose:
            print(f"    Events received: {event_types}")

        error_events = [e for e in events if e.get("event") == "error"]
        if error_events:
            error_data = error_events[0].get("data", "")
            try:
                error_parsed = json.loads(error_data)
                error_layer = error_parsed.get("layer", "")
            except (json.JSONDecodeError, AttributeError):
                error_layer = ""
            if error_layer in ("ollama", "vlm"):
                c.warn(f"infra: {error_data}")
                return c
            c.fail(f"pipeline error: {error_data}")
            return c

        if "classification_comparison" not in event_types:
            c.fail("classification_comparison event missing with compare=true")
            return c

        c.pass_("comparison event present")

    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    except httpx.ReadTimeout:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("request timed out (120s)")
    except httpx.HTTPStatusError as e:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail(f"HTTP {e.response.status_code}")
    return c


async def check_standards_search(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("GET /api/standards/search")
    t0 = time.monotonic()
    try:
        resp = await client.get(
            f"{base_url}/api/standards/search",
            params={"q": "perpendicularity"},
        )
        c.latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()
        if verbose:
            print(f"    Response: {json.dumps(data, indent=2)[:300]}")

        results = data.get("results", [])
        if len(results) > 0:
            c.pass_(f"{len(results)} results returned")
        else:
            c.warn("0 results (embedder may not be loaded)")

    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    except httpx.HTTPStatusError as e:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail(f"HTTP {e.response.status_code}")
    return c


async def check_standards_lookup(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("GET /api/standards/{code}")
    t0 = time.monotonic()
    try:
        resp = await client.get(f"{base_url}/api/standards/perpendicularity")
        c.latency_ms = (time.monotonic() - t0) * 1000

        if resp.status_code == 200:
            data = resp.json()
            if verbose:
                print(f"    Response: {json.dumps(data, indent=2)[:300]}")
            c.pass_(f"found standard entry")
        elif resp.status_code == 404:
            c.warn("standard not found (db may not be seeded)")
        elif resp.status_code == 503:
            c.warn("brain database not available")
        else:
            c.fail(f"HTTP {resp.status_code}")

    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    return c


async def check_tolerances(client: httpx.AsyncClient, base_url: str, verbose: bool) -> Check:
    c = Check("GET /api/tolerances")
    t0 = time.monotonic()
    try:
        resp = await client.get(
            f"{base_url}/api/tolerances",
            params={"process": "cnc_milling", "material": "AL6061-T6"},
        )
        c.latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()
        if verbose:
            print(f"    Response: {json.dumps(data, indent=2)[:300]}")

        tols = data.get("tolerances", [])
        if len(tols) > 0:
            c.pass_(f"{len(tols)} tolerance entries")
        else:
            c.warn("0 results (manufacturing lookup may not be loaded)")

    except httpx.ConnectError:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail("server not reachable")
    except httpx.HTTPStatusError as e:
        c.latency_ms = (time.monotonic() - t0) * 1000
        c.fail(f"HTTP {e.response.status_code}")
    return c


async def run_all(base_url: str, verbose: bool, skip_slow: bool) -> list[Check]:
    async with httpx.AsyncClient() as client:
        # Always run health first -- if server is down, skip the rest
        health = await check_health(client, base_url, verbose)
        results = [health]

        if health.status == "FAIL":
            print(f"\n  Server not reachable at {base_url} -- skipping remaining checks.\n")
            return results

        # Fast endpoints (can run in parallel)
        fast_checks = await asyncio.gather(
            check_standards_search(client, base_url, verbose),
            check_standards_lookup(client, base_url, verbose),
            check_tolerances(client, base_url, verbose),
        )
        results.extend(fast_checks)

        # Slow endpoints (model inference, run sequentially)
        if not skip_slow:
            results.append(await check_analyze(client, base_url, verbose))
            results.append(await check_analyze_compare(client, base_url, verbose))

        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="ToleranceAI API health check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Server base URL")
    parser.add_argument("--verbose", action="store_true", help="Print response bodies")
    parser.add_argument("--skip-slow", action="store_true", help="Skip /analyze endpoints (model inference)")
    args = parser.parse_args()

    print(f"ToleranceAI Health Check")
    print(f"Target: {args.base_url}\n")

    results = asyncio.run(run_all(args.base_url, args.verbose, args.skip_slow))

    # Summary table
    status_icon = {"PASS": "+", "FAIL": "X", "WARN": "~", "SKIP": "-"}
    print(f"{'='*70}")
    print(f"  {'Endpoint':<35} {'Status':<8} {'Latency':>10}  Detail")
    print(f"  {'-'*66}")
    for r in results:
        icon = status_icon.get(r.status, "?")
        detail = r.detail or (r.errors[0] if r.errors else "")
        latency_str = f"{r.latency_ms:.0f} ms" if r.latency_ms > 0 else "--"
        print(f"  [{icon}] {r.name:<32} {r.status:<8} {latency_str:>8}  {detail}")
    print(f"{'='*70}")

    passed = sum(1 for r in results if r.status == "PASS")
    warned = sum(1 for r in results if r.status == "WARN")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)

    print(f"\n  {passed}/{total} passed", end="")
    if warned:
        print(f", {warned} warnings", end="")
    if failed:
        print(f", {failed} FAILED", end="")
    print()

    if failed:
        sys.exit(1)
    elif warned:
        sys.exit(0)
    else:
        print("  All endpoints healthy.")
        sys.exit(0)


if __name__ == "__main__":
    main()
