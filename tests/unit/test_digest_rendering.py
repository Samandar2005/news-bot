"""Tests for pipeline.digest.rendering.render_digest_message — pure text
formatting, no DB or network."""

from __future__ import annotations

from pipeline.digest.rendering import MAX_MESSAGE_CHARS, render_digest_message


def test_renders_header_in_requested_language():
    en = render_digest_message([], "en")
    ru = render_digest_message([], "ru")
    uz = render_digest_message([], "uz")

    assert "digest" in en.lower()
    assert "новостей" in ru.lower()
    assert "yangiliklar" in uz.lower()


def test_unsupported_language_falls_back_to_english_header():
    result = render_digest_message([], "fr")
    assert "digest" in result.lower()


def test_renders_numbered_summaries_in_order():
    items = [(None, "First summary"), (None, "Second summary"), (None, "Third summary")]
    result = render_digest_message(items, "en")

    assert "1. First summary" in result
    assert "2. Second summary" in result
    assert "3. Third summary" in result
    assert result.index("1. First") < result.index("2. Second") < result.index("3. Third")


def test_empty_items_still_renders_just_the_header():
    result = render_digest_message([], "en")
    assert len(result.strip()) > 0
    assert "1." not in result


def test_stays_under_telegram_hard_limit_even_with_many_long_items():
    long_summary = "x" * 500
    items = [(None, long_summary) for _ in range(20)]  # would be ~10,000+ chars unbounded

    result = render_digest_message(items, "en")

    assert len(result) <= MAX_MESSAGE_CHARS
    assert "1. " in result
    assert "20. " not in result


def test_included_entries_are_never_truncated_mid_summary():
    """A dropped item should be dropped entirely, never half-included —
    that would produce garbled, confusing output."""
    long_summary = "x" * 500
    items = [(None, long_summary) for _ in range(20)]

    result = render_digest_message(items, "en")

    numbered_lines = [line for line in result.split("\n") if line and line[0].isdigit()]
    assert len(numbered_lines) > 0
    for line in numbered_lines:
        assert "x" * 500 in line
