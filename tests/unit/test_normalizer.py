"""Tests for pipeline.processing.normalizer — the light M4-era helpers."""

from __future__ import annotations

from pipeline.processing.normalizer import compute_content_hash, strip_html_lightly


def test_strip_html_lightly_removes_tags():
    assert strip_html_lightly("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_lightly_decodes_entities():
    assert strip_html_lightly("Fish &amp; chips &mdash; yum") == "Fish & chips — yum"


def test_strip_html_lightly_collapses_whitespace():
    assert strip_html_lightly("Too   much\n\nwhitespace") == "Too much whitespace"


def test_compute_content_hash_is_deterministic():
    h1 = compute_content_hash("Title", "Content")
    h2 = compute_content_hash("Title", "Content")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_compute_content_hash_case_insensitive():
    """Same story, different capitalization from two sources, should hash
    the same — this is the exact-duplicate pre-filter, not a literal-bytes
    comparison."""
    h1 = compute_content_hash("Breaking News", "Something happened.")
    h2 = compute_content_hash("BREAKING NEWS", "SOMETHING HAPPENED.")
    assert h1 == h2


def test_compute_content_hash_differs_for_different_content():
    h1 = compute_content_hash("Title A", "Content A")
    h2 = compute_content_hash("Title B", "Content B")
    assert h1 != h2


def test_compute_content_hash_strips_surrounding_whitespace():
    h1 = compute_content_hash("Title", "Content")
    h2 = compute_content_hash("  Title  ", "  Content  ")
    assert h1 == h2
