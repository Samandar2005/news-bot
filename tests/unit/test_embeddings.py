"""Tests for pipeline.ai.embeddings.

See the module's docstring for what this embedding actually is (a
feature-hashed lexical vector, not a semantic one) and why — these tests
verify the properties clustering.py actually depends on: determinism,
normalization, and that textually-similar articles score higher than
unrelated ones. They do not claim semantic understanding.
"""

from __future__ import annotations

import math

import pytest

from pipeline.ai.embeddings import compute_embedding


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_same_text_produces_identical_vector():
    text = "NASA announces new Mars mission timeline for rocket launch"
    assert compute_embedding(text) == compute_embedding(text)


def test_vector_has_configured_dimension():
    vec = compute_embedding("Some article text here.", dim=256)
    assert len(vec) == 256


def test_vector_is_l2_normalized():
    vec = compute_embedding("NASA announces new Mars mission for rocket launch")
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm == pytest.approx(1.0)


def test_empty_text_returns_zero_vector():
    vec = compute_embedding("")
    assert all(v == 0.0 for v in vec)


def test_whitespace_only_text_returns_zero_vector():
    vec = compute_embedding("   \n\t  ")
    assert all(v == 0.0 for v in vec)


def test_near_duplicate_text_scores_higher_than_unrelated_text():
    """The actual property clustering.py relies on: two articles covering
    the same wire-service story (heavy vocabulary overlap, different
    outlet framing) should be far more similar than two unrelated
    articles."""
    original = (
        "NASA announces new Mars mission timeline for rocket launch. "
        "The space station crew will prepare a new satellite for orbit."
    )
    reworded_repost = (
        "NASA has announced a new timeline for its Mars mission and rocket launch. "
        "Space station crew members will prepare a satellite for orbit."
    )
    unrelated = (
        "Local bakery wins regional award for best sourdough bread recipe "
        "after years of community fundraising events."
    )

    emb_original = compute_embedding(original)
    emb_repost = compute_embedding(reworded_repost)
    emb_unrelated = compute_embedding(unrelated)

    similarity_to_repost = _dot(emb_original, emb_repost)
    similarity_to_unrelated = _dot(emb_original, emb_unrelated)

    assert similarity_to_repost > similarity_to_unrelated


def test_identical_text_has_cosine_similarity_one():
    text = "A clear, specific sentence about a specific news event today."
    vec = compute_embedding(text)
    assert _dot(vec, vec) == pytest.approx(1.0)


def test_completely_disjoint_vocabulary_has_near_zero_similarity():
    a = compute_embedding("aardvark aardvark aardvark zeppelin zeppelin")
    b = compute_embedding("quantum quantum quantum broccoli broccoli")
    assert _dot(a, b) == pytest.approx(0.0, abs=1e-9)
