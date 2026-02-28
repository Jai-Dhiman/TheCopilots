import numpy as np
from pathlib import Path


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

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        emb_path = Path(embeddings_path)
        if emb_path.exists():
            data = np.load(str(emb_path))
            self.standard_embeddings = data["embeddings"]
            self.standard_keys = data["keys"].tolist()

    def match_standards(self, query: str, top_k: int = 5) -> list[dict]:
        """Find top-K ASME Y14.5 sections most relevant to the query."""
        if self.standard_embeddings is None:
            return []

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
        return results
