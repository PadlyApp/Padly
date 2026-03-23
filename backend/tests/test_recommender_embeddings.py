"""Phase 3.1/3.2 helpers: taste vector similarity (no Supabase or model load required)."""

import numpy as np

from app.ai.recommender import taste_similarity_from_mean_embeddings


def test_taste_similarity_identical_vectors():
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    s = taste_similarity_from_mean_embeddings(a, b)
    assert s is not None
    assert s > 0.99


def test_taste_similarity_opposite_maps_low():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([-1.0, 0.0], dtype=np.float32)
    s = taste_similarity_from_mean_embeddings(a, b)
    assert s is not None
    assert s < 0.01


def test_taste_similarity_none_inputs():
    assert taste_similarity_from_mean_embeddings(None, np.array([1.0])) is None
    assert taste_similarity_from_mean_embeddings(np.array([1.0]), None) is None
