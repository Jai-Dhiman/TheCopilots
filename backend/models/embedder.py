import logging
import time

import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


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

        t0 = time.monotonic()
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence-transformer loaded in %.1fs", time.monotonic() - t0)

        emb_path = Path(embeddings_path)
        if emb_path.exists():
            data = np.load(str(emb_path))
            self.standard_embeddings = data["embeddings"]
            keys_field = "keys" if "keys" in data else "ids"
            self.standard_keys = data[keys_field].tolist()
            logger.info("Loaded %d standard embeddings from %s", len(self.standard_keys), emb_path.name)
        else:
            logger.warning("Embeddings file not found: %s", embeddings_path)

    def match_standards(self, query: str, top_k: int = 5) -> list[dict]:
        """Find top-K ASME Y14.5 sections most relevant to the query."""
        if self.standard_embeddings is None:
            logger.debug("match_standards skipped: no embeddings loaded")
            return []

        t0 = time.monotonic()
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
        logger.info("match_standards query=%r top_score=%.3f in %.0fms", query[:60], results[0]["score"] if results else 0.0, (time.monotonic() - t0) * 1000)
        return results
