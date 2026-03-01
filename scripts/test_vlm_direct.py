#!/usr/bin/env python3
"""Direct mlx-vlm inference test -- no FastAPI, no SSE, no browser.

Loads the Gemma 3n E4B model and runs feature extraction directly,
printing raw output, parsed JSON, and timing. Use this to verify
the model can interpret CAD screenshots and produce valid structured JSON.

Usage:
    # Text-only (no image)
    python scripts/test_vlm_direct.py --text "12mm aluminum boss, CNC machined"

    # With a saved image
    python scripts/test_vlm_direct.py --image screenshot.png --text "identify the main feature"

    # Capture current screen (macOS) and feed to model
    python scripts/test_vlm_direct.py --screenshot --text "cylindrical boss"

    # Just print the prompt without running inference
    python scripts/test_vlm_direct.py --text "12mm boss" --prompt-only

    # Control max tokens
    python scripts/test_vlm_direct.py --text "12mm boss" --max-tokens 256
"""

import argparse
import base64
import json
import os
import sys
import tempfile
import time
import traceback

# Add backend to sys.path so we can import prompts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

from models.prompts import FEATURE_EXTRACTION_SYSTEM


def capture_screenshot() -> str:
    """Capture the current screen using PIL.ImageGrab (macOS). Returns temp file path."""
    try:
        from PIL import ImageGrab
    except ImportError:
        print("ERROR: Pillow is required for --screenshot. Install with: uv pip install Pillow")
        sys.exit(1)

    print("Capturing screen in 3 seconds... switch to your FreeCAD window!")
    time.sleep(3)

    img = ImageGrab.grab()
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    print(f"Screen captured: {path} ({img.size[0]}x{img.size[1]})")
    return path


def load_image_as_base64(image_path: str) -> str:
    """Read an image file and return base64-encoded bytes."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def prepare_image_tempfile(image_base64: str) -> str:
    """Write base64 image to a temp file for mlx-vlm. Returns temp path."""
    image_bytes = base64.b64decode(image_base64)
    fd, temp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.write(fd, image_bytes)
    finally:
        os.close(fd)
    return temp_path


def extract_json(raw: str) -> dict:
    """Extract JSON from raw model output -- mirrors MlxVlmClient._extract_json."""
    import re

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract JSON from model output:\n{raw}")


def main():
    parser = argparse.ArgumentParser(
        description="Direct mlx-vlm inference test (no server needed)"
    )
    parser.add_argument(
        "--text", "-t",
        default="Table made up of a rectangular surface and 4 legs that are press fit at each corner. The rectangular surface is 350x700x50 mm, with 4 holes in each corner where the legs are press fit. Each leg is 100 mm in diameter and 700 mm in length. Each leg has a cylindrical piece of diameter 60 mm at the top (50 mm tall).",
        help="Text description of the part feature",
    )
    parser.add_argument(
        "--image", "-i",
        help="Path to an image file (PNG/JPEG) to feed to the model",
    )
    parser.add_argument(
        "--screenshot", "-s",
        action="store_true",
        help="Capture the current screen (macOS) after a 3-second delay",
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Print the formatted prompt and exit without running inference",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum tokens for model generation (default: 512)",
    )
    args = parser.parse_args()

    if args.image and args.screenshot:
        print("ERROR: Use --image or --screenshot, not both.")
        sys.exit(1)

    # -- Build the prompt --
    prompt = FEATURE_EXTRACTION_SYSTEM + "\n\n" + args.text

    # -- Prepare image --
    image_path = None
    temp_screenshot = None

    if args.screenshot:
        temp_screenshot = capture_screenshot()
        image_path = temp_screenshot
    elif args.image:
        if not os.path.isfile(args.image):
            print(f"ERROR: Image file not found: {args.image}")
            sys.exit(1)
        image_path = os.path.abspath(args.image)

    image_paths = [image_path] if image_path else None
    num_images = 1 if image_path else 0

    print("=" * 60)
    print("TEST: Direct mlx-vlm inference")
    print("=" * 60)
    print(f"Text input:  {args.text}")
    print(f"Image:       {image_path or '(none)'}")
    print(f"Max tokens:  {args.max_tokens}")
    print()

    if args.prompt_only:
        print("--- FORMATTED PROMPT (what the model sees) ---")
        print(prompt)
        print("--- END PROMPT ---")
        if temp_screenshot:
            os.unlink(temp_screenshot)
        return

    # -- Load model --
    print("Loading mlx-vlm model...")
    t_load_start = time.monotonic()

    try:
        from mlx_vlm import load, generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config

        model_id = "mlx-community/gemma-3n-E4B-it-4bit"
        model, processor = load(model_id)
        config = load_config(model_id)
    except Exception:
        print("\nERROR: Failed to load mlx-vlm model")
        traceback.print_exc()
        if temp_screenshot:
            os.unlink(temp_screenshot)
        sys.exit(1)

    t_load_elapsed = time.monotonic() - t_load_start
    print(f"Model loaded in {t_load_elapsed:.1f}s")
    print()

    # -- Format prompt with chat template --
    formatted = apply_chat_template(processor, config, prompt, num_images=num_images)

    print("--- FORMATTED PROMPT (after chat template) ---")
    # Truncate if very long
    if len(formatted) > 2000:
        print(formatted[:1000])
        print(f"\n... ({len(formatted)} chars total, truncated) ...\n")
        print(formatted[-500:])
    else:
        print(formatted)
    print("--- END PROMPT ---")
    print()

    # -- Run inference --
    print(f"Running inference (max_tokens={args.max_tokens})...")
    t_infer_start = time.monotonic()

    try:
        result = generate(
            model,
            processor,
            formatted,
            image_paths,
            verbose=False,
            max_tokens=args.max_tokens,
        )
        raw_output = result if isinstance(result, str) else result.text
    except Exception:
        t_infer_elapsed = time.monotonic() - t_infer_start
        print(f"\nERROR: Inference failed after {t_infer_elapsed:.1f}s")
        traceback.print_exc()
        if temp_screenshot:
            os.unlink(temp_screenshot)
        sys.exit(1)

    t_infer_elapsed = time.monotonic() - t_infer_start

    print(f"Inference completed in {t_infer_elapsed:.1f}s")
    print()

    # -- Print raw output --
    print("--- RAW MODEL OUTPUT ---")
    print(raw_output)
    print("--- END RAW OUTPUT ---")
    print()

    # -- Parse JSON --
    print("--- JSON EXTRACTION ---")
    try:
        parsed = extract_json(raw_output)
        print(json.dumps(parsed, indent=2))
        print()
        print("JSON extraction: SUCCESS")
    except ValueError as e:
        print(f"JSON extraction: FAILED")
        print(f"  {e}")
        parsed = None
    print()

    # -- Summary --
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Model load time:     {t_load_elapsed:.1f}s")
    print(f"  Inference time:      {t_infer_elapsed:.1f}s")
    print(f"  Total time:          {t_load_elapsed + t_infer_elapsed:.1f}s")
    print(f"  Raw output length:   {len(raw_output)} chars")
    print(f"  JSON valid:          {'YES' if parsed else 'NO'}")
    if parsed:
        print(f"  Feature type:        {parsed.get('feature_type', '?')}")
        print(f"  Material:            {parsed.get('material', '?')}")
        print(f"  Process:             {parsed.get('manufacturing_process', '?')}")
    print()

    # -- Cleanup --
    if temp_screenshot:
        os.unlink(temp_screenshot)
        print(f"Cleaned up temp screenshot: {temp_screenshot}")


if __name__ == "__main__":
    main()
