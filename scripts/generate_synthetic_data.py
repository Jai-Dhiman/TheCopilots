"""Generate synthetic GD&T training pairs using Gemini 2.5 Pro via Google AI.

Calls Gemini to generate 500+ training pairs mapping structured feature input
to GD&T classification + datum scheme + callouts. Validates every pair against
ASME Y14.5-2018 rules and tolerance ranges before saving.

Uses Google AI's OpenAI-compatible endpoint (billed to GCP project credits).

Output:
- data/synthetic/training_pairs.jsonl  -- validated pairs, one per line
- data/synthetic/generation_log.jsonl  -- per-batch metadata
- data/synthetic/generation_prompts.txt -- system + user prompt templates
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
STANDARDS_DIR = BASE_DIR / "data" / "standards"
SYNTHETIC_DIR = BASE_DIR / "data" / "synthetic"

REQUIRED_FILES = [
    "asme_y14_5.json",
    "tolerance_tables.json",
    "material_properties.json",
    "datum_patterns.json",
]

# --- Configuration ---

GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL_ID = "gemini-2.5-pro"
BATCH_SIZE = 5
TARGET_TOTAL = 550
MAX_REJECTION_RATE = 0.20
RATE_LIMIT_DELAY = 1.0
MAX_RETRIES = 3

# Tolerance table keys that are NOT geometric characteristics
TOLERANCE_META_KEYS = {"surface_finish_ra_um", "notes"}

# --- Data Loading ---


def load_json(filename: str) -> dict:
    path = STANDARDS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def load_all_standards() -> dict:
    """Load all standards files into a single dict keyed by filename stem."""
    return {
        "asme": load_json("asme_y14_5.json"),
        "tolerances": load_json("tolerance_tables.json"),
        "materials": load_json("material_properties.json"),
        "datums": load_json("datum_patterns.json"),
    }


# --- Coverage Matrix ---

FEATURE_TYPES = ["hole", "boss", "surface", "slot", "groove", "shaft", "pattern", "bend"]

COMPLEXITY_LEVELS = ["single_feature", "multi_feature_with_datum", "assembly_context"]

# Edge cases: characteristic pairs where one should be preferred over another
EDGE_CASE_PAIRS = [
    {"target": "circular_runout", "instead_of": "concentricity", "reason": "concentricity requires median line derivation"},
    {"target": "position", "instead_of": "symmetry", "reason": "symmetry requires median plane derivation"},
    {"target": "flatness", "instead_of": None, "reason": "form control with NO datums"},
    {"target": "circularity", "instead_of": None, "reason": "form control with NO datums"},
    {"target": "cylindricity", "instead_of": None, "reason": "form control with NO datums"},
    {"target": "straightness", "instead_of": None, "reason": "form control with NO datums"},
    {"target": "profile_of_a_surface", "instead_of": None, "reason": "profile with datums (location+form)"},
    {"target": "profile_of_a_surface", "instead_of": None, "reason": "profile without datums (form only)"},
    {"target": "profile_of_a_line", "instead_of": None, "reason": "profile with datums"},
    {"target": "profile_of_a_line", "instead_of": None, "reason": "profile without datums"},
]


def build_valid_combos(standards: dict) -> list[dict]:
    """Build valid (process, material_category, material_id) combos from tolerance_tables.json."""
    combos = []
    mat_data = standards["materials"]["materials"]
    tol_data = standards["tolerances"]["processes"]

    for process_id, process_info in tol_data.items():
        materials = process_info.get("materials", {})
        for mat_category in materials:
            # Find all specific material IDs that map to this category
            for mat_id, mat_info in mat_data.items():
                if mat_info["category"] == mat_category:
                    combos.append({
                        "process": process_id,
                        "material_category": mat_category,
                        "material_id": mat_id,
                    })
    return combos


def get_available_characteristics(standards: dict, process: str, material_category: str) -> list[str]:
    """Return characteristic IDs available for a process/material combo in tolerance_tables."""
    proc_data = standards["tolerances"]["processes"].get(process, {})
    mat_data = proc_data.get("materials", {}).get(material_category, {})
    return [
        k for k, v in mat_data.items()
        if k not in TOLERANCE_META_KEYS and isinstance(v, dict) and "min_mm" in v
    ]


def _get_fallback_characteristic(char_id: str) -> str | None:
    """For characteristics not in tolerance_tables, return a related one for combo lookup."""
    fallbacks = {
        "angularity": "perpendicularity",       # same category (orientation)
        "concentricity": "circular_runout",      # preferred replacement
        "symmetry": "position",                  # preferred replacement
        "profile_of_a_line": "profile_of_a_surface",  # same category (profile)
    }
    return fallbacks.get(char_id)


def build_coverage_plan(standards: dict) -> list[dict]:
    """Build the systematic generation plan ensuring coverage of all 14 characteristics."""
    plan = []
    valid_combos = build_valid_combos(standards)
    char_ids = [c["id"] for c in standards["asme"]["characteristics"]]

    # Track how many pairs per characteristic we've planned
    char_counts = {cid: 0 for cid in char_ids}
    min_per_char = 30

    # Phase 1: systematic coverage -- round-robin through characteristics
    for target_char in char_ids:
        # Find combos that support this characteristic (or a fallback)
        supporting_combos = []
        for combo in valid_combos:
            available = get_available_characteristics(
                standards, combo["process"], combo["material_category"]
            )
            if target_char in available:
                supporting_combos.append(combo)

        # If no combos found, use a fallback characteristic for combo selection
        if not supporting_combos:
            fallback = _get_fallback_characteristic(target_char)
            if fallback:
                for combo in valid_combos:
                    available = get_available_characteristics(
                        standards, combo["process"], combo["material_category"]
                    )
                    if fallback in available:
                        supporting_combos.append(combo)

        if not supporting_combos:
            continue

        pairs_needed = min_per_char - char_counts[target_char]
        combo_idx = 0
        feature_idx = 0
        complexity_idx = 0

        while char_counts[target_char] < min_per_char and pairs_needed > 0:
            combo = supporting_combos[combo_idx % len(supporting_combos)]
            feature = FEATURE_TYPES[feature_idx % len(FEATURE_TYPES)]
            complexity = COMPLEXITY_LEVELS[complexity_idx % len(COMPLEXITY_LEVELS)]

            plan.append({
                "target_characteristic": target_char,
                "feature_type": feature,
                "process": combo["process"],
                "material_id": combo["material_id"],
                "material_category": combo["material_category"],
                "complexity": complexity,
                "is_edge_case": False,
            })

            char_counts[target_char] += 1
            pairs_needed -= 1
            combo_idx += 1
            feature_idx += 1
            complexity_idx += 1

    # Phase 2: edge cases (at least 50)
    edge_case_count = 0
    for edge in EDGE_CASE_PAIRS:
        target = edge["target"]
        supporting = [
            c for c in valid_combos
            if target in get_available_characteristics(standards, c["process"], c["material_category"])
        ]
        if not supporting:
            continue

        # Generate 5 edge case pairs per edge case type
        for i in range(5):
            combo = supporting[i % len(supporting)]
            plan.append({
                "target_characteristic": target,
                "feature_type": FEATURE_TYPES[i % len(FEATURE_TYPES)],
                "process": combo["process"],
                "material_id": combo["material_id"],
                "material_category": combo["material_category"],
                "complexity": COMPLEXITY_LEVELS[i % len(COMPLEXITY_LEVELS)],
                "is_edge_case": True,
                "edge_case_reason": edge["reason"],
                "instead_of": edge.get("instead_of"),
            })
            edge_case_count += 1

    return plan


# --- Prompt Construction ---


def build_system_prompt(standards: dict) -> str:
    """Build the system prompt with embedded ASME Y14.5 rules and tolerance data."""
    asme = standards["asme"]

    char_table = []
    for c in asme["characteristics"]:
        char_table.append(
            f"- {c['id']} ({c['symbol']}): category={c['category']}, "
            f"datum_required={c['datum_required']}, "
            f"datum_optional={c.get('datum_optional', False)}, "
            f"applicable_modifiers={c['applicable_modifiers']}, "
            f"applicable_features={c.get('applicable_features', [])}, "
            f"when_to_use: {c['when_to_use']}, "
            f"when_NOT_to_use: {c.get('when_NOT_to_use', 'N/A')}"
        )
        if c.get("prefer_instead"):
            char_table.append(f"  PREFER: {c['prefer_instead']} -- {c.get('deprecation_note', '')}")

    return f"""You are an expert ASME Y14.5-2018 GD&T engineer generating training data for a classifier model.

CRITICAL RULES:
1. Form controls (straightness, flatness, circularity, cylindricity) NEVER take datum references. datum_required MUST be false.
2. Orientation controls (perpendicularity, angularity, parallelism) ALWAYS require at least one datum. datum_required MUST be true.
3. Location controls (position, concentricity, symmetry) ALWAYS require datums. datum_required MUST be true.
4. Runout controls (circular_runout, total_runout) ALWAYS require datums. datum_required MUST be true.
5. Profile controls (profile_of_a_line, profile_of_a_surface) may or may not have datums. Without datums = form only. With datums = form + orientation + location.
6. Concentricity is rarely appropriate -- prefer circular_runout unless median line control is explicitly needed.
7. Symmetry is rarely appropriate -- prefer position unless median plane control is explicitly needed.
8. Tolerance values MUST fall within the achievable range for the given process/material/characteristic.
9. Feature control frame format: |symbol| tolerance [modifier] | datum_refs |
10. Modifiers must be from the characteristic's applicable_modifiers list.

THE 14 GEOMETRIC CHARACTERISTICS:
{chr(10).join(char_table)}

Output MUST be valid JSON matching the schema exactly. Generate {BATCH_SIZE} examples per request."""


def build_tolerance_context(standards: dict, process: str, material_category: str) -> str:
    """Extract tolerance ranges for a specific process/material combo."""
    proc_data = standards["tolerances"]["processes"].get(process, {})
    mat_data = proc_data.get("materials", {}).get(material_category, {})

    lines = []
    for key, val in mat_data.items():
        if key in TOLERANCE_META_KEYS:
            continue
        if isinstance(val, dict) and "min_mm" in val:
            lines.append(f"  {key}: {val['min_mm']}-{val['max_mm']} mm")
    return "\n".join(lines)


def build_datum_context(standards: dict, feature_type: str) -> str:
    """Find the most relevant datum pattern for a feature type."""
    patterns = standards["datums"]["patterns"]
    for pat_id, pat in patterns.items():
        applicable = pat.get("applicable_features", [])
        # Check if any applicable feature loosely matches the feature type
        for af in applicable:
            if feature_type in af.lower() or af.lower() in feature_type:
                return (
                    f"Suggested datum pattern ({pat_id}): "
                    f"primary={pat['primary']['type']} ({pat['primary']['reasoning']}), "
                    f"secondary={pat.get('secondary', {}).get('type', 'N/A')}, "
                    f"tertiary={pat.get('tertiary', {}).get('type', 'N/A')}"
                )
    # Default to flat_plate_with_holes as generic fallback
    pat = patterns["flat_plate_with_holes"]
    return (
        f"Suggested datum pattern (flat_plate_with_holes): "
        f"primary={pat['primary']['type']}, "
        f"secondary={pat.get('secondary', {}).get('type', 'N/A')}, "
        f"tertiary={pat.get('tertiary', {}).get('type', 'N/A')}"
    )


def build_user_prompt(batch_items: list[dict], standards: dict) -> str:
    """Build the user prompt for a batch of generation items."""
    examples_desc = []
    for i, item in enumerate(batch_items, 1):
        tol_context = build_tolerance_context(
            standards, item["process"], item["material_category"]
        )
        datum_context = build_datum_context(standards, item["feature_type"])

        # Find the characteristic info
        char_info = next(
            (c for c in standards["asme"]["characteristics"]
             if c["id"] == item["target_characteristic"]),
            None,
        )

        edge_note = ""
        if item.get("is_edge_case"):
            edge_note = f"\n  EDGE CASE: {item.get('edge_case_reason', '')}"
            if item.get("instead_of"):
                edge_note += f" (generate this INSTEAD of {item['instead_of']})"

        examples_desc.append(
            f"Example {i}:\n"
            f"  feature_type: {item['feature_type']}\n"
            f"  material: {item['material_id']} (category: {item['material_category']})\n"
            f"  process: {item['process']}\n"
            f"  target_characteristic: {item['target_characteristic']} ({char_info['symbol'] if char_info else '?'})\n"
            f"  complexity: {item['complexity']}\n"
            f"  Achievable tolerances for {item['process']}/{item['material_category']}:\n{tol_context}\n"
            f"  {datum_context}"
            f"{edge_note}"
        )

    return f"""Generate {len(batch_items)} training pairs as a JSON array. Each pair must follow this exact schema:

{{
  "input": {{
    "feature_type": "<string>",
    "geometry": {{"diameter": <float>, "height": <float>, "unit": "mm"}},
    "material": "<material_id>",
    "manufacturing_process": "<process_id>",
    "mating_condition": "<descriptive string>",
    "parent_surface": "<descriptive string>"
  }},
  "classification": {{
    "primary_control": "<characteristic_id>",
    "symbol": "<unicode symbol>",
    "tolerance_class": "<tight|standard|loose>",
    "datum_required": <true|false>,
    "modifier": "<MMC|LMC|RFS|none>",
    "reasoning_key": "<descriptive_key>"
  }},
  "full_output": {{
    "datum_scheme": {{"A": "<surface>", "B": "<surface>"}},
    "callouts": [
      {{"feature": "<name>", "frame": "|symbol| tolerance [modifier] | datums |", "reasoning": "<1-2 sentences>"}}
    ],
    "warnings": ["<optional warnings>"]
  }}
}}

REQUIREMENTS PER EXAMPLE:
{chr(10).join(examples_desc)}

Remember:
- geometry fields should have realistic values for the feature type
- mating_condition and parent_surface should be realistic engineering descriptions
- tolerance values in callout frames MUST be within the achievable range shown above
- For form controls: datum_required=false, NO datum refs in callouts
- For orientation/location/runout: datum_required=true, datum refs MUST be present
- For profile: datum_required=false, but datum refs may or may not be present depending on the use case
- reasoning should explain WHY this control is appropriate
- modifier must be from the characteristic's applicable_modifiers list
- If modifier is "none" or "RFS", do not include a modifier symbol in the frame

Return ONLY the JSON array, no markdown fences or extra text."""


# --- Validation ---


def build_char_lookup(standards: dict) -> dict:
    """Build a lookup from characteristic ID to its properties."""
    return {c["id"]: c for c in standards["asme"]["characteristics"]}


def build_tolerance_lookup(standards: dict) -> dict:
    """Build a lookup: (process, material_category, characteristic) -> (min_mm, max_mm)."""
    lookup = {}
    for proc_id, proc_data in standards["tolerances"]["processes"].items():
        for mat_id, mat_data in proc_data.get("materials", {}).items():
            for key, val in mat_data.items():
                if key in TOLERANCE_META_KEYS:
                    continue
                if isinstance(val, dict) and "min_mm" in val:
                    lookup[(proc_id, mat_id, key)] = (val["min_mm"], val["max_mm"])
    return lookup


def build_material_category_lookup(standards: dict) -> dict:
    """Build a lookup from material_id to category."""
    return {
        mat_id: mat_info["category"]
        for mat_id, mat_info in standards["materials"]["materials"].items()
    }


def validate_pair(pair: dict, char_lookup: dict, tol_lookup: dict,
                   mat_cat_lookup: dict) -> list[str]:
    """Validate a single training pair. Returns list of error messages (empty = valid)."""
    errors = []

    # 1. Schema check
    for top_key in ("input", "classification", "full_output"):
        if top_key not in pair:
            errors.append(f"Missing top-level key: {top_key}")
    if errors:
        return errors

    inp = pair["input"]
    cls = pair["classification"]
    out = pair["full_output"]

    for field in ("feature_type", "material", "manufacturing_process"):
        if field not in inp:
            errors.append(f"input missing field: {field}")

    for field in ("primary_control", "symbol", "tolerance_class", "datum_required", "modifier"):
        if field not in cls:
            errors.append(f"classification missing field: {field}")

    if "callouts" not in out:
        errors.append("full_output missing field: callouts")

    if errors:
        return errors

    primary_control = cls["primary_control"]
    char_info = char_lookup.get(primary_control)

    if char_info is None:
        errors.append(f"Unknown characteristic: {primary_control}")
        return errors

    # 2 & 3. Datum checks
    category = char_info["category"]
    datum_required = cls["datum_required"]

    if category == "form":
        if datum_required is not False:
            errors.append(f"Form control '{primary_control}' must have datum_required=false")
        # Check callouts don't have datum refs
        for callout in out.get("callouts", []):
            frame = callout.get("frame", "")
            parts = [p.strip() for p in frame.split("|") if p.strip()]
            # Form controls: frame should have symbol + tolerance, no datum letters
            if len(parts) > 2:
                # Check if extra parts look like datum references (single letters)
                for extra in parts[2:]:
                    extra_clean = extra.strip()
                    if len(extra_clean) <= 2 and extra_clean[0].isupper():
                        errors.append(
                            f"Form control '{primary_control}' callout has datum ref '{extra_clean}'"
                        )

    elif category in ("orientation", "location", "runout"):
        if datum_required is not True:
            errors.append(f"{category} control '{primary_control}' must have datum_required=true")
        # Check callouts have datum refs
        for callout in out.get("callouts", []):
            if callout.get("feature") == inp.get("feature_type") or len(out.get("callouts", [])) == 1:
                frame = callout.get("frame", "")
                parts = [p.strip() for p in frame.split("|") if p.strip()]
                has_datum = False
                for part in parts[2:] if len(parts) > 2 else []:
                    if part.strip() and part.strip()[0].isupper() and len(part.strip()) <= 3:
                        has_datum = True
                        break
                if not has_datum:
                    errors.append(
                        f"{category} control '{primary_control}' callout missing datum refs"
                    )

    # 4. Tolerance range check
    material_id = inp.get("material", "")
    process = inp.get("manufacturing_process", "")
    mat_category = mat_cat_lookup.get(material_id)

    if mat_category:
        tol_key = (process, mat_category, primary_control)
        tol_range = tol_lookup.get(tol_key)
        if tol_range:
            for callout in out.get("callouts", []):
                frame = callout.get("frame", "")
                # Extract numeric tolerance value from frame
                tol_val = _extract_tolerance_value(frame)
                if tol_val is not None:
                    min_mm, max_mm = tol_range
                    if tol_val < min_mm * 0.8 or tol_val > max_mm * 1.5:
                        errors.append(
                            f"Tolerance {tol_val}mm outside range "
                            f"[{min_mm}, {max_mm}] for {process}/{mat_category}/{primary_control}"
                        )

    # 5. Symbol check
    if cls["symbol"] != char_info["symbol"]:
        errors.append(
            f"Symbol mismatch: got '{cls['symbol']}', "
            f"expected '{char_info['symbol']}' for {primary_control}"
        )

    # 6. Modifier check
    modifier = cls.get("modifier", "none")
    applicable = char_info.get("applicable_modifiers", [])
    if modifier not in ("none", "RFS") and modifier not in applicable:
        errors.append(
            f"Modifier '{modifier}' not in applicable_modifiers {applicable} "
            f"for {primary_control}"
        )

    return errors


def _extract_tolerance_value(frame: str) -> float | None:
    """Extract the numeric tolerance value from a feature control frame string."""
    match = re.search(r'[\d]+\.[\d]+', frame)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


# --- API Calls ---


def create_client() -> OpenAI:
    """Create Google AI client via OpenAI-compatible endpoint."""
    load_dotenv(BASE_DIR / ".env")
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not found. Add it to .env in the project root:\n"
            "  GOOGLE_API_KEY=<your-key>\n"
            "Get a key at https://aistudio.google.com/apikey (select GCP project with credits)"
        )
    return OpenAI(base_url=GOOGLE_AI_BASE_URL, api_key=api_key)


def call_gemini(client: OpenAI, system_prompt: str, user_prompt: str) -> str:
    """Call Gemini via Google AI with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=16384,  # Gemini 2.5 Pro uses thinking tokens that count against this limit
            )
            return response.choices[0].message.content
        except Exception as exc:
            exc_str = str(exc)
            # Fail immediately on auth errors
            if "401" in exc_str or "403" in exc_str:
                raise RuntimeError(
                    f"Authentication failed (HTTP {exc_str[:3]}). "
                    "Check your GOOGLE_API_KEY."
                ) from exc

            if attempt < MAX_RETRIES - 1:
                wait = (2 ** attempt) * RATE_LIMIT_DELAY
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {wait:.1f}s: {exc}")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Unreachable")


def parse_response(raw: str) -> list[dict]:
    """Parse the JSON array from Gemini's response."""
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        start = 1
        end = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON response: {exc}") from exc

    if isinstance(parsed, dict):
        # Sometimes Gemini wraps in a dict
        for key in ("examples", "pairs", "data", "training_pairs"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        # Single pair
        return [parsed]

    if isinstance(parsed, list):
        return parsed

    raise ValueError(f"Unexpected response type: {type(parsed)}")


# --- Main Pipeline ---


def count_existing_pairs(output_path: Path) -> int:
    """Count existing validated pairs in the output JSONL file."""
    if not output_path.exists():
        return 0
    text = output_path.read_text().strip()
    if not text:
        return 0
    return len(text.split("\n"))


def save_pair(pair: dict, output_path: Path) -> None:
    """Append a single validated pair to the JSONL file."""
    with open(output_path, "a") as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")


def save_log_entry(entry: dict, log_path: Path) -> None:
    """Append a log entry to the generation log."""
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def save_prompts(system_prompt: str, sample_user_prompt: str, prompts_path: Path) -> None:
    """Save prompts for reproducibility."""
    prompts_path.write_text(
        f"=== SYSTEM PROMPT ===\n\n{system_prompt}\n\n"
        f"=== SAMPLE USER PROMPT ===\n\n{sample_user_prompt}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic GD&T training data")
    parser.add_argument("--resume", action="store_true", help="Resume from existing output")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts, no API calls")
    parser.add_argument("--target", type=int, default=TARGET_TOTAL, help="Target pair count")
    args = parser.parse_args()

    # Verify all source files exist
    for filename in REQUIRED_FILES:
        path = STANDARDS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    output_path = SYNTHETIC_DIR / "training_pairs.jsonl"
    log_path = SYNTHETIC_DIR / "generation_log.jsonl"
    prompts_path = SYNTHETIC_DIR / "generation_prompts.txt"

    # Load standards
    standards = load_all_standards()
    char_lookup = build_char_lookup(standards)
    tol_lookup = build_tolerance_lookup(standards)
    mat_cat_lookup = build_material_category_lookup(standards)

    # Build coverage plan
    plan = build_coverage_plan(standards)
    print(f"Coverage plan: {len(plan)} items across {len(set(p['target_characteristic'] for p in plan))} characteristics")

    # Build system prompt
    system_prompt = build_system_prompt(standards)

    # Check resume state
    existing_count = 0
    if args.resume:
        existing_count = count_existing_pairs(output_path)
        print(f"Resuming: {existing_count} existing pairs found")
    elif output_path.exists() and not args.dry_run:
        # Overwrite -- clear files
        output_path.write_text("")
        log_path.write_text("")

    target = args.target

    # Batch the plan
    batches = []
    for i in range(0, len(plan), BATCH_SIZE):
        batches.append(plan[i:i + BATCH_SIZE])

    # Calculate how many batches to skip on resume
    skip_batches = 0
    if args.resume and existing_count > 0:
        # Approximate: each batch produces ~BATCH_SIZE valid pairs
        skip_batches = existing_count // BATCH_SIZE
        print(f"Skipping {skip_batches} batches")

    # Save sample prompts
    if batches:
        sample_user_prompt = build_user_prompt(batches[0], standards)
        save_prompts(system_prompt, sample_user_prompt, prompts_path)

    if args.dry_run:
        print(f"\n=== DRY RUN ===")
        print(f"System prompt length: {len(system_prompt)} chars")
        print(f"Total batches: {len(batches)}")
        print(f"\n=== SYSTEM PROMPT (first 2000 chars) ===")
        print(system_prompt[:2000])
        print(f"\n=== SAMPLE USER PROMPT ===")
        if batches:
            print(sample_user_prompt[:3000])
        return

    # Create API client
    client = create_client()

    total_generated = existing_count
    total_rejected = 0
    total_api_errors = 0

    print(f"\nGenerating pairs (target: {target})...")

    for batch_idx, batch in enumerate(batches):
        if batch_idx < skip_batches:
            continue

        if total_generated >= target:
            break

        user_prompt = build_user_prompt(batch, standards)

        print(f"Batch {batch_idx + 1}/{len(batches)}: "
              f"targets=[{', '.join(b['target_characteristic'] for b in batch)}]")

        try:
            raw_response = call_gemini(client, system_prompt, user_prompt)
        except Exception as exc:
            print(f"  API error (skipping batch): {exc}")
            total_api_errors += 1
            save_log_entry({
                "batch_idx": batch_idx,
                "status": "api_error",
                "error": str(exc),
                "timestamp": time.time(),
            }, log_path)
            continue

        try:
            pairs = parse_response(raw_response)
        except ValueError as exc:
            print(f"  Parse error (skipping batch): {exc}")
            total_rejected += BATCH_SIZE
            save_log_entry({
                "batch_idx": batch_idx,
                "status": "parse_error",
                "error": str(exc),
                "raw_length": len(raw_response),
                "timestamp": time.time(),
            }, log_path)
            continue

        batch_accepted = 0
        batch_rejected = 0

        for pair in pairs:
            validation_errors = validate_pair(pair, char_lookup, tol_lookup, mat_cat_lookup)
            if validation_errors:
                print(f"  Rejected: {validation_errors[0]}")
                batch_rejected += 1
                total_rejected += 1
            else:
                save_pair(pair, output_path)
                batch_accepted += 1
                total_generated += 1

        save_log_entry({
            "batch_idx": batch_idx,
            "status": "ok",
            "accepted": batch_accepted,
            "rejected": batch_rejected,
            "total_so_far": total_generated,
            "timestamp": time.time(),
        }, log_path)

        print(f"  Accepted: {batch_accepted}, Rejected: {batch_rejected}, Total: {total_generated}")

        time.sleep(RATE_LIMIT_DELAY)

    # Final summary
    total_attempted = total_generated + total_rejected
    rejection_rate = total_rejected / total_attempted if total_attempted > 0 else 0.0

    print(f"\n=== Generation Complete ===")
    print(f"Total pairs: {total_generated}")
    print(f"Total rejected: {total_rejected}")
    print(f"API errors: {total_api_errors}")
    print(f"Rejection rate: {rejection_rate:.1%}")
    print(f"Output: {output_path}")

    if rejection_rate > MAX_REJECTION_RATE:
        raise RuntimeError(
            f"Rejection rate {rejection_rate:.1%} exceeds maximum {MAX_REJECTION_RATE:.0%}. "
            "Review generation prompts and validation logic."
        )

    if total_generated < 500:
        print(f"WARNING: Only {total_generated} pairs generated (target: 500+)")

    # Verification: coverage stats
    print(f"\nVerification:")
    lines = output_path.read_text().strip().split("\n")
    pairs = [json.loads(line) for line in lines if line.strip()]
    from collections import Counter
    controls = Counter(p["classification"]["primary_control"] for p in pairs)
    print(f"  Total: {len(pairs)} pairs, {len(controls)} characteristics covered")
    for k, v in controls.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
