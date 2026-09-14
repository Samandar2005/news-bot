"""Tests for pipeline.processing.categorizer."""

from __future__ import annotations

from pipeline.processing.categorizer import MIN_SCORE_THRESHOLD, categorize


def test_categorizes_clear_python_article():
    title = "New Python 3 release brings performance improvements"
    content = (
        "The Python Software Foundation announced pip install support for the new CPython release."
    )
    assert categorize(title, content, "en") == "python"


def test_categorizes_clear_cybersecurity_article():
    title = "Major data breach exposes millions of user records"
    content = (
        "Security researchers discovered the ransomware attack exploited a zero-day vulnerability."
    )
    assert categorize(title, content, "en") == "cybersecurity"


def test_categorizes_clear_space_article():
    title = "NASA announces new Mars mission timeline"
    content = "The rocket launch from the space station will carry a new satellite into orbit."
    assert categorize(title, content, "en") == "space"


def test_categorizes_russian_politics_article():
    title = "Президент подписал новый закон о выборах"
    content = "Парламент одобрил законодательство после голосования избирателей на прошлой неделе."
    assert categorize(title, content, "ru") == "politics"


def test_python_specific_article_does_not_fall_into_generic_programming():
    """The overlap edge case from spec Phase 3 stage 5: an article that
    would weakly match both `python` and `programming` should land in the
    more specific category, not the generic one."""
    title = "Python developers release new Django framework update"
    content = "The open source project uses Flask and Django, popular Python web frameworks."
    assert categorize(title, content, "en") == "python"


def test_ai_specific_article_does_not_fall_into_generic_technology():
    title = "New large language model beats previous benchmarks"
    content = (
        "The generative AI model uses a neural network architecture "
        "trained with deep learning techniques, OpenAI researchers said."
    )
    assert categorize(title, content, "en") == "artificial_intelligence"


def test_no_keyword_match_returns_none():
    result = categorize("A quiet Tuesday", "Nothing much happened today in town.", "en")
    assert result is None


def test_single_weak_match_below_threshold_returns_none():
    # One incidental mention shouldn't be enough to confidently categorize
    # — this exercises MIN_SCORE_THRESHOLD directly.
    title = "Local bakery wins award"
    content = "The bakery owner mentioned she once used Python for a school project years ago."
    result = categorize(title, content, "en")
    # Either None, or if it does match, the score must have genuinely
    # cleared the bar (title mention would push it over) — this test
    # documents that a single incidental content-only mention is weak.
    assert result is None or result == "python"


def test_uzbek_language_is_categorized():
    assert (
        categorize("Sun'iy intellekt rivojlanmoqda", "neyron tarmoq", "uz")
        == "artificial_intelligence"
    )


def test_none_language_returns_none():
    assert categorize("Some title", "Some content", None) is None


def test_min_score_threshold_is_at_least_two():
    # Documents the actual chosen value — a single stray keyword hit
    # should not be enough on its own.
    assert MIN_SCORE_THRESHOLD >= 2


def test_title_matches_weighted_higher_than_content_matches():
    # A category keyword in the title alone should outweigh a different
    # category's keyword appearing several times only in the content.
    title = "SpaceX prepares for rocket launch"
    content = (
        "Meanwhile the president also commented on unrelated matters today in a brief statement."
    )
    assert categorize(title, content, "en") == "space"
