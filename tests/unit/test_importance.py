"""Unit tests for pipeline.scoring.importance.compute_importance — the
pure Phase 6 formula, tested against constructed cases per M9's roadmap
test criterion. No database needed for any of these.
"""

from __future__ import annotations

import math

import pytest

from pipeline.scoring.importance import compute_importance
from shared.config import settings


def test_more_sources_increases_importance_all_else_equal():
    low = compute_importance(
        source_count=1,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    high = compute_importance(
        source_count=5,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    assert high > low


def test_higher_reliability_increases_importance_all_else_equal():
    low = compute_importance(
        source_count=2,
        avg_reliability=0.3,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    high = compute_importance(
        source_count=2,
        avg_reliability=0.9,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    assert high > low


def test_higher_category_weight_increases_importance_all_else_equal():
    low = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.3,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    high = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.9,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    assert high > low


def test_fresher_event_scores_higher_all_else_equal():
    fresh = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=0.5,
        avg_clickbait_score=0.0,
    )
    stale = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=48.0,
        avg_clickbait_score=0.0,
    )
    assert fresh > stale


def test_clickbait_penalty_decreases_importance_all_else_equal():
    clean = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    clickbaity = compute_importance(
        source_count=2,
        avg_reliability=0.7,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=1.0,
    )
    assert clean > clickbaity


def test_single_source_breaking_disaster_still_scores_meaningfully():
    """The exact edge case spec Phase 3 stage 9 calls out: a fast-breaking,
    single-source, high-reliability, high-category-weight story (e.g. a
    natural disaster) must not be scored near zero just for lacking
    corroboration yet — log1p(1) still contributes real signal, and a
    high category weight (natural_disasters defaults to 0.85 in the seed
    data) plus freshness should keep this comfortably above a run-of-the-
    mill multi-source but low-weight story.
    """
    breaking_disaster = compute_importance(
        source_count=1,
        avg_reliability=0.9,
        category_weight=0.85,
        hours_since_first_seen=0.1,
        avg_clickbait_score=0.0,
    )
    routine_multi_source_low_weight = compute_importance(
        source_count=3,
        avg_reliability=0.5,
        category_weight=0.35,
        hours_since_first_seen=24.0,
        avg_clickbait_score=0.0,
    )
    assert breaking_disaster > routine_multi_source_low_weight


def test_negative_hours_since_first_seen_is_clamped_not_crashed():
    # Guards against clock skew producing a "future" first_seen_at.
    result = compute_importance(
        source_count=1,
        avg_reliability=0.5,
        category_weight=0.5,
        hours_since_first_seen=-5.0,
        avg_clickbait_score=0.0,
    )
    at_zero = compute_importance(
        source_count=1,
        avg_reliability=0.5,
        category_weight=0.5,
        hours_since_first_seen=0.0,
        avg_clickbait_score=0.0,
    )
    assert result == pytest.approx(at_zero)


def test_zero_sources_does_not_crash_on_log():
    # log1p(0) = 0, a well-defined edge case, not a math domain error.
    result = compute_importance(
        source_count=0,
        avg_reliability=0.5,
        category_weight=0.5,
        hours_since_first_seen=1.0,
        avg_clickbait_score=0.0,
    )
    assert math.isfinite(result)


def test_formula_matches_manual_calculation_for_a_known_case():
    """Pins the actual formula shape (spec Phase 6.2) against hand
    computation with the real configured weights, so a future accidental
    reordering or sign-flip of a term gets caught immediately."""
    source_count = 3
    avg_reliability = 0.8
    category_weight = 0.6
    hours = 4.0
    avg_clickbait = 0.2

    expected = (
        settings.weight_source_count * math.log1p(source_count)
        + settings.weight_reliability * avg_reliability
        + settings.weight_category * category_weight
        - settings.weight_clickbait_penalty * avg_clickbait
        + settings.weight_freshness * math.exp(-hours / settings.freshness_decay_hours)
    )

    actual = compute_importance(
        source_count=source_count,
        avg_reliability=avg_reliability,
        category_weight=category_weight,
        hours_since_first_seen=hours,
        avg_clickbait_score=avg_clickbait,
    )
    assert actual == pytest.approx(expected)
