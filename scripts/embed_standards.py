"""Generate embeddings for ASME Y14.5 GD&T characteristics.

Loads data/standards/asme_y14_5.json, concatenates text fields per characteristic,
encodes with sentence-transformers all-MiniLM-L6-v2 (384-dim), and saves to
data/embeddings/standards_embeddings.npz.

NPZ keys: ids (string array), embeddings (float32 matrix), model_name (string).
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
STANDARDS_FILE = BASE_DIR / "data" / "standards" / "asme_y14_5.json"
EMBEDDINGS_DIR = BASE_DIR / "data" / "embeddings"
OUTPUT_FILE = EMBEDDINGS_DIR / "standards_embeddings.npz"

MODEL_NAME = "all-MiniLM-L6-v2"


def build_text(char: dict) -> str:
    """Concatenate characteristic fields into a single embedding text."""
    parts = [char["name"]]
    if char.get("rules"):
        parts.append(" ".join(char["rules"]))
    if char.get("when_to_use"):
        parts.append(char["when_to_use"])
    if char.get("when_NOT_to_use"):
        parts.append(char["when_NOT_to_use"])
    return " ".join(parts)


def main() -> None:
    if not STANDARDS_FILE.exists():
        raise FileNotFoundError(f"Standards file not found: {STANDARDS_FILE}")

    data = json.loads(STANDARDS_FILE.read_text())
    characteristics = data["characteristics"]

    ids = []
    texts = []
    for char in characteristics:
        ids.append(char["id"])
        texts.append(build_text(char))

    print(f"Loaded {len(ids)} characteristics")
    print(f"Loading model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)

    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    np.savez(
        str(OUTPUT_FILE),
        ids=np.array(ids),
        embeddings=embeddings.astype(np.float32),
        model_name=np.array(MODEL_NAME),
    )

    print(f"Saved embeddings: {OUTPUT_FILE}")
    print(f"  Shape: {embeddings.shape}")
    print(f"  IDs: {ids}")
    print(f"  Model: {MODEL_NAME}")


if __name__ == "__main__":
    main()
