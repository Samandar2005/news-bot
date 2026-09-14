"""Tests for bot.locales.strings.t — the lookup/fallback logic, not the
copy itself."""

from __future__ import annotations

from bot.locales.strings import _STRINGS, t


def test_t_returns_requested_language():
    assert t("ru", "language_set") == _STRINGS["ru"]["language_set"]
    assert t("uz", "language_set") == _STRINGS["uz"]["language_set"]


def test_t_falls_back_to_english_for_unknown_language():
    assert t("fr", "language_set") == _STRINGS["en"]["language_set"]


def test_t_falls_back_to_key_for_unknown_key():
    assert t("en", "totally_made_up_key") == "totally_made_up_key"


def test_all_languages_have_the_same_keys():
    """Catches copy-paste drift — every language must cover every key,
    or `t()` would silently fall back mid-conversation for real users."""
    key_sets = {lang: set(strings.keys()) for lang, strings in _STRINGS.items()}
    en_keys = key_sets["en"]
    for lang, keys in key_sets.items():
        missing = keys.symmetric_difference(en_keys)
        assert keys == en_keys, f"{lang} is missing or has extra keys: {missing}"
