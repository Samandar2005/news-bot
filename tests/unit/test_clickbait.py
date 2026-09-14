"""Tests for pipeline.processing.clickbait."""

from __future__ import annotations

from pipeline.processing.clickbait import score_clickbait


def test_neutral_headline_scores_low():
    score = score_clickbait("Federal Reserve raises interest rates by quarter point")
    assert score < 0.2


def test_neutral_russian_headline_scores_low():
    score = score_clickbait("Президент подписал новый закон о выборах")
    assert score < 0.2


def test_classic_clickbait_phrase_scores_high():
    score = score_clickbait("You won't believe what happened next at this press conference")
    assert score >= 0.5


def test_listicle_pattern_detected():
    score = score_clickbait("10 things you didn't know about the new policy")
    assert score >= 0.3


def test_russian_listicle_pattern_detected():
    score = score_clickbait("7 причин почему этот закон важен для всех")
    assert score >= 0.3


def test_russian_clickbait_phrase_detected():
    score = score_clickbait("Вы не поверите, что произошло на саммите")
    assert score >= 0.3


def test_excessive_exclamation_marks_add_score():
    calm = score_clickbait("New policy announced today")
    excited = score_clickbait("New policy announced today!!!")
    assert excited > calm


def test_mixed_punctuation_adds_score():
    score = score_clickbait("Is this really happening?!")
    assert score > 0.0


def test_shouting_multiple_caps_words_adds_score():
    calm = score_clickbait("NASA announces new Mars mission")  # one acronym, normal
    shouting = score_clickbait("SHOCKING NEWS about the mission REVEALED today")
    assert shouting > calm


def test_single_acronym_does_not_trigger_shouting_penalty():
    # "NASA" alone (one all-caps word) should not be flagged as shouting
    score = score_clickbait("NASA announces new Mars mission timeline")
    assert score < 0.25  # below the shouting-weight threshold on its own


def test_empty_title_returns_zero():
    assert score_clickbait("") == 0.0


def test_score_is_capped_at_one():
    extreme = score_clickbait(
        "SHOCKING!!! You won't believe this ONE WEIRD TRICK that WILL CHANGE YOUR LIFE?!"
    )
    assert extreme <= 1.0


def test_score_never_negative():
    assert score_clickbait("A") >= 0.0
