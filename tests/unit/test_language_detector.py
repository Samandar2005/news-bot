"""Tests for pipeline.processing.language_detector.

Uses real text samples (not synthetic/lorem-ipsum) since the whole point
of this module is behavior on real Uzbek/Russian/English news-style text —
see the module docstring for why confidence-threshold fallback exists at
all. Expected results below match what was empirically observed against
the actual bundled model during development, not assumptions about how it
"should" behave.
"""

from __future__ import annotations

from pipeline.processing.language_detector import (
    HIGH_CONFIDENCE_THRESHOLD,
    detect_language,
)

RUSSIAN_TEXT = (
    "Сегодня в Узбекистане резко поднялась температура воздуха. "
    "В Ташкенте открылась новая линия метро."
)
ENGLISH_TEXT = (
    "Today the temperature in Uzbekistan rose sharply. "
    "A new metro line opened in Tashkent."
)
UZBEK_LONG_TEXT = (
    "Prezident bugun muhim qonun loyihasini imzoladi. Bu qonun tadbirkorlar "
    "uchun soliq imtiyozlarini nazarda tutadi va mamlakat iqtisodiyotini "
    "rivojlantirishga qaratilgan."
)
# Empirically low-confidence / misclassified when run alone — this is
# exactly the case the declared_language fallback exists for.
UZBEK_AMBIGUOUS_SHORT_TITLE = "Toshkentda metro liniyasi ochildi"


def test_detects_russian_with_high_confidence():
    assert detect_language(RUSSIAN_TEXT) == "ru"


def test_detects_english_with_high_confidence():
    assert detect_language(ENGLISH_TEXT) == "en"


def test_detects_clear_uzbek_text():
    assert detect_language(UZBEK_LONG_TEXT) == "uz"


def test_ambiguous_uzbek_falls_back_to_declared_language():
    """The real, documented reason this function takes declared_language
    at all: a short, plausible Uzbek headline that the model alone does
    not confidently (or even correctly) identify as Uzbek."""
    result = detect_language(UZBEK_AMBIGUOUS_SHORT_TITLE, declared_language="uz")
    assert result == "uz"


def test_ambiguous_text_without_declared_language_does_not_crash():
    # No safety net here — should still return *something* reasonable
    # (a supported language or None), never raise.
    result = detect_language(UZBEK_AMBIGUOUS_SHORT_TITLE, declared_language=None)
    assert result is None or result in {"en", "ru", "uz"}


def test_very_short_text_skips_detection_and_uses_declared_language():
    result = detect_language("Hi", declared_language="ru")
    assert result == "ru"


def test_very_short_text_with_no_declared_language_returns_none():
    result = detect_language("Hi", declared_language=None)
    assert result is None


def test_unsupported_language_declared_falls_through():
    # "fr" isn't one of our three supported languages — the function
    # should not blindly trust a declared_language it can't actually
    # serve downstream (categorization/summarization only cover en/ru/uz).
    result = detect_language(
        "Bonjour le monde, comment ça va aujourd'hui ?", declared_language="fr"
    )
    assert result is None or result in {"en", "ru", "uz"}


def test_high_confidence_threshold_is_reasonably_strict():
    # Documents the actual chosen value rather than letting it drift
    # silently — see module docstring for why 0.8 was picked.
    assert HIGH_CONFIDENCE_THRESHOLD == 0.8
