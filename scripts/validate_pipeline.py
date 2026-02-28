"""End-to-end pipeline validation against the live GD&T classifier in Ollama.

Runs 5 acceptance test scenarios, validates responses against expected controls
and ASME Y14.5-2018 rules. This is the confidence gate before demo.

Requires:
- Ollama running with gemma3-270m-gdt model loaded
- data/brain.db seeded
- data/embeddings/standards_embeddings.npz present
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "brain.db"
EMBEDDINGS_PATH = BASE_DIR / "data" / "embeddings" / "standards_embeddings.npz"

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "gemma3-270m-gdt"

# --- Test Scenarios ---

SCENARIOS = [
    {
        "name": "Perpendicular boss",
        "input": {
            "feature_type": "boss",
            "geometry": {"diameter": 12.0, "height": 8.0, "unit": "mm"},
            "material": "AL6061-T6",
            "manufacturing_process": "cnc_milling",
            "mating_condition": "bearing_bore_concentric",
            "parent_surface": "planar_mounting_face",
        },
        "expected": {
            "primary_control": "perpendicularity",
            "datum_required": True,
        },
    },
    {
        "name": "Hole pattern MMC",
        "input": {
            "feature_type": "pattern",
            "geometry": {"diameter": 6.35, "count": 4, "bolt_circle_diameter": 50.0, "unit": "mm"},
            "material": "Steel_1018",
            "manufacturing_process": "cnc_milling",
            "mating_condition": "bolt_clearance_pattern",
            "parent_surface": "flat_plate_face",
        },
        "expected": {
            "primary_control": "position",
            "datum_required": True,
            "modifier": "MMC",
        },
    },
    {
        "name": "Large flat surface",
        "input": {
            "feature_type": "surface",
            "geometry": {"length": 200.0, "width": 150.0, "unit": "mm"},
            "material": "Gray_Cast_Iron",
            "manufacturing_process": "die_casting",
            "mating_condition": "gasket_sealing_surface",
            "parent_surface": "housing_body",
        },
        "expected": {
            "primary_control": "flatness",
            "datum_required": False,
        },
    },
    {
        "name": "Shaft runout",
        "input": {
            "feature_type": "shaft",
            "geometry": {"diameter": 25.0, "length": 80.0, "unit": "mm"},
            "material": "Steel_4140",
            "manufacturing_process": "cnc_turning",
            "mating_condition": "bearing_journal_rotation",
            "parent_surface": "shaft_shoulder",
        },
        "expected": {
            "primary_control": "circular_runout",
            "datum_required": True,
            # Must NOT be concentricity
            "must_not_be": "concentricity",
        },
    },
    {
        "name": "Bracket hole",
        "input": {
            "feature_type": "hole",
            "geometry": {"diameter": 8.0, "depth": 15.0, "unit": "mm"},
            "material": "AL6061-T6",
            "manufacturing_process": "cnc_milling",
            "mating_condition": "dowel_pin_press_fit",
            "parent_surface": "bracket_face",
        },
        "expected": {
            "primary_control": "position",
            "datum_required": True,
        },
    },
]


# --- Prerequisites Check ---


def check_prerequisites() -> list[str]:
    """Check all prerequisites are met. Returns list of errors."""
    errors = []

    if not DB_PATH.exists():
        errors.append(f"brain.db not found: {DB_PATH}")

    if not EMBEDDINGS_PATH.exists():
        errors.append(f"Embeddings not found: {EMBEDDINGS_PATH}")

    return errors


async def check_ollama(client: httpx.AsyncClient) -> list[str]:
    """Check Ollama is running and model is loaded."""
    errors = []

    try:
        resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
        errors.append(f"Ollama not reachable at {OLLAMA_BASE_URL}: {exc}")
        return errors

    data = resp.json()
    model_names = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
    if MODEL_NAME not in model_names:
        errors.append(
            f"Model '{MODEL_NAME}' not found in Ollama. "
            f"Available: {model_names}. Run: ollama create {MODEL_NAME} -f Modelfile"
        )

    return errors


# --- Scenario Runner ---


async def run_scenario(client: httpx.AsyncClient, scenario: dict,
                       verbose: bool = False) -> dict:
    """Run a single test scenario against Ollama."""
    input_json = json.dumps(scenario["input"], ensure_ascii=False, indent=None)
    prompt = (
        "<instruction>Given this part feature, classify the appropriate GD&T control.</instruction>\n"
        f"<input>{input_json}</input>\n"
        "<output>"
    )

    start_time = time.time()

    try:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 256,
                },
            },
            timeout=60.0,
        )
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
        return {
            "name": scenario["name"],
            "status": "FAIL",
            "error": f"Ollama request failed: {exc}",
            "latency_ms": (time.time() - start_time) * 1000,
        }

    latency_ms = (time.time() - start_time) * 1000
    raw_response = resp.json().get("response", "")

    if verbose:
        print(f"\n  Raw response: {raw_response[:500]}")

    # Parse classification JSON from response
    try:
        # Try to find JSON in the response
        text = raw_response.strip()
        if text.startswith("{"):
            classification = json.loads(text)
        elif "{" in text:
            # Extract first JSON object
            brace_start = text.index("{")
            # Find matching closing brace
            depth = 0
            brace_end = brace_start
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        brace_end = i + 1
                        break
            classification = json.loads(text[brace_start:brace_end])
        else:
            return {
                "name": scenario["name"],
                "status": "FAIL",
                "error": f"No JSON found in response: {raw_response[:200]}",
                "latency_ms": latency_ms,
            }
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "name": scenario["name"],
            "status": "FAIL",
            "error": f"JSON parse error: {exc}",
            "latency_ms": latency_ms,
        }

    # Validate against expected values
    expected = scenario["expected"]
    failures = []

    for key, expected_val in expected.items():
        if key == "must_not_be":
            if classification.get("primary_control") == expected_val:
                failures.append(
                    f"primary_control should NOT be '{expected_val}' "
                    f"(got '{classification.get('primary_control')}')"
                )
            continue

        actual_val = classification.get(key)
        if actual_val != expected_val:
            failures.append(f"{key}: expected '{expected_val}', got '{actual_val}'")

    # ASME rule validation
    primary = classification.get("primary_control", "")
    datum_req = classification.get("datum_required")

    # Form controls must not require datums
    form_controls = {"straightness", "flatness", "circularity", "cylindricity"}
    if primary in form_controls and datum_req is True:
        failures.append(f"Form control '{primary}' must have datum_required=false")

    # Orientation/location/runout must require datums
    datum_required_categories = {
        "perpendicularity", "angularity", "parallelism",
        "position", "concentricity", "symmetry",
        "circular_runout", "total_runout",
    }
    if primary in datum_required_categories and datum_req is False:
        failures.append(f"Control '{primary}' must have datum_required=true")

    status = "PASS" if not failures else "FAIL"

    result = {
        "name": scenario["name"],
        "status": status,
        "latency_ms": latency_ms,
        "predicted": classification,
    }
    if failures:
        result["failures"] = failures

    return result


# --- Main ---


async def async_main(scenarios: list[dict], verbose: bool) -> list[dict]:
    """Run all scenarios and return results."""
    async with httpx.AsyncClient() as client:
        # Check Ollama
        ollama_errors = await check_ollama(client)
        if ollama_errors:
            for err in ollama_errors:
                print(f"PREREQUISITE FAIL: {err}")
            raise RuntimeError("Ollama prerequisites not met")

        results = []
        for scenario in scenarios:
            print(f"Running: {scenario['name']}...", end="", flush=True)
            result = await run_scenario(client, scenario, verbose=verbose)
            print(f" {result['status']} ({result['latency_ms']:.0f}ms)")
            if result.get("failures"):
                for f in result["failures"]:
                    print(f"  - {f}")
            if result.get("error"):
                print(f"  ERROR: {result['error']}")
            results.append(result)

        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GD&T pipeline end-to-end")
    parser.add_argument("--verbose", action="store_true", help="Print full classification output")
    parser.add_argument("--scenario", type=str, help="Run a single scenario by name")
    args = parser.parse_args()

    # Check file prerequisites
    prereq_errors = check_prerequisites()
    if prereq_errors:
        for err in prereq_errors:
            print(f"PREREQUISITE FAIL: {err}")
        raise RuntimeError("Prerequisites not met. Run seed_database.py and embed_standards.py first.")

    # Filter scenarios
    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["name"] == args.scenario]
        if not scenarios:
            available = [s["name"] for s in SCENARIOS]
            raise ValueError(f"Scenario '{args.scenario}' not found. Available: {available}")

    print(f"Running {len(scenarios)} scenario(s)...\n")

    results = asyncio.run(async_main(scenarios, verbose=args.verbose))

    # Summary table
    print(f"\n{'='*60}")
    print(f"{'Scenario':<25} {'Status':<8} {'Latency':>10}")
    print(f"{'-'*60}")
    for r in results:
        print(f"{r['name']:<25} {r['status']:<8} {r['latency_ms']:>8.0f} ms")
    print(f"{'='*60}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\nResult: {passed}/{total} passed")

    if passed < total:
        print("\nFailed scenarios need investigation before demo.")
        raise SystemExit(1)

    print("\nAll scenarios passed. Pipeline is ready for demo.")


if __name__ == "__main__":
    main()
