"""Unit tests for pipeline.scoring.relevance.compute_final_score — the
pure Phase 6 FinalScore formula, per M11's roadmap test criterion. No
database needed.
"""

from __future__ import annotations

import pytest

from pipeline.scoring.relevance import compute_final_score
from shared.config import settings


def test_matching_interest_increases_score_over_no_match():
    no_match = compute_final_score(
        importance_score=0.5, interest_match=0.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    matched = compute_final_score(
        importance_score=0.5, interest_match=1.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    assert matched > no_match


def test_zero_interest_match_does_not_zero_out_the_score():
    """The actual mechanism behind spec Phase 3 stage 10's 'must-know
    story override' — a zero match multiplies by (1 + 0) = 1, not by 0.
    A high-importance, non-matching event still scores at its full
    importance, not nothing.
    """
    score = compute_final_score(
        importance_score=0.8, interest_match=0.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    assert score == pytest.approx(0.8)


def test_very_important_unmatched_event_can_outrank_matched_low_importance_one():
    important_unmatched = compute_final_score(
        importance_score=0.9, interest_match=0.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    trivial_matched = compute_final_score(
        importance_score=0.1, interest_match=1.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    assert important_unmatched > trivial_matched


def test_geo_relevance_adds_a_flat_bonus():
    without_geo = compute_final_score(
        importance_score=0.5, interest_match=0.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    with_geo = compute_final_score(
        importance_score=0.5, interest_match=0.0, geo_relevance=1.0, repeat_penalty=0.0
    )
    assert with_geo > without_geo


def test_repeat_penalty_decreases_score():
    fresh = compute_final_score(
        importance_score=0.5, interest_match=1.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    repeated = compute_final_score(
        importance_score=0.5, interest_match=1.0, geo_relevance=0.0, repeat_penalty=1.0
    )
    assert fresh > repeated


def test_formula_matches_manual_calculation_for_a_known_case():
    """Pins the actual formula shape (spec Phase 6.2) against hand
    computation with the real configured weights."""
    importance = 0.6
    interest_match = 1.0
    geo = 1.0
    repeat = 0.0

    expected = (
        importance * (1 + settings.weight_interest_boost * interest_match)
        + settings.weight_geo_bonus * geo
        - settings.weight_repeat_penalty * repeat
    )
    actual = compute_final_score(
        importance_score=importance,
        interest_match=interest_match,
        geo_relevance=geo,
        repeat_penalty=repeat,
    )
    assert actual == pytest.approx(expected)


def test_full_repeat_penalty_can_exceed_importance_gain_from_match():
    """A repeated story with a matching interest can still end up scoring
    below its own base importance once the penalty is applied — this is
    intentional (spec Phase 3 stage 12: avoid re-surfacing the same
    story), not a bug, so pin the actual relationship for the currently
    configured weights.
    """
    importance = 0.4
    matched_but_repeated = compute_final_score(
        importance_score=importance, interest_match=1.0, geo_relevance=0.0, repeat_penalty=1.0
    )
    unmatched_fresh = compute_final_score(
        importance_score=importance, interest_match=0.0, geo_relevance=0.0, repeat_penalty=0.0
    )
    # Both reduce to importance plus/minus a term; confirm the penalty
    # term is actually being subtracted, not silently ignored.
    assert matched_but_repeated < importance * (1 + settings.weight_interest_boost)
    expected = (
        unmatched_fresh
        + importance * settings.weight_interest_boost
        - settings.weight_repeat_penalty
    )
    assert matched_but_repeated == pytest.approx(expected)
