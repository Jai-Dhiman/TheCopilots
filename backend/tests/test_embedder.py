import numpy as np
import pytest
from pathlib import Path
from models.embedder import Embedder


@pytest.fixture
def fake_embeddings(tmp_path):
    """Create a fake NPZ file with pre-computed embeddings."""
    keys = ["flatness", "perpendicularity", "position", "circular_runout"]
    rng = np.random.default_rng(42)
    embeddings = rng.random((4, 384)).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms

    npz_path = tmp_path / "standards_embeddings.npz"
    np.savez(
        str(npz_path),
        embeddings=embeddings,
        keys=np.array(keys),
    )
    return str(npz_path)


@pytest.fixture
def embedder(fake_embeddings):
    e = Embedder()
    e.load(embeddings_path=fake_embeddings)
    return e


def test_load_creates_model(embedder):
    assert embedder.model is not None


def test_load_reads_embeddings(embedder):
    assert embedder.standard_embeddings is not None
    assert embedder.standard_embeddings.shape == (4, 384)
    assert len(embedder.standard_keys) == 4


def test_match_standards_returns_results(embedder):
    results = embedder.match_standards("flat surface control", top_k=2)
    assert len(results) == 2
    assert "key" in results[0]
    assert "score" in results[0]


def test_match_standards_respects_top_k(embedder):
    results = embedder.match_standards("position", top_k=1)
    assert len(results) == 1


def test_match_standards_no_embeddings():
    e = Embedder()
    e.model = True  # fake to avoid NotReady
    e.standard_embeddings = None
    results = e.match_standards("test", top_k=3)
    assert results == []
