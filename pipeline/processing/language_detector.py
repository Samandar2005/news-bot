"""Language detection (spec Phase 3, stage 4).

Uses fastText's bundled lid.176 "lite" model (via the `fast-langdetect`
package) rather than downloading the full model — the full one lives at
Facebook's own CDN, which most deployment networks can reach, but there's
no reason to depend on that when the bundled compressed model already
covers our three languages.

**Why this isn't just "call detect() and trust it":** empirically (tested
against real Uzbek/Russian/English text during development), the model is
excellent at distinguishing English and Russian — but noticeably weaker
on Uzbek, especially on short text like headlines. Confidence scores
around 0.5 are common for clearly-Uzbek article titles, and short titles
have been misclassified as English or Turkish outright.  This isn't a
bug to work around; it's a real limitation of general-purpose language ID
models on a comparatively low-resource language, called out as an
expected risk in spec Phase 1.6.

So detection is used to *confirm or override* the source's already-known
declared language, not to determine language from nothing:
- High-confidence detection in a supported language -> trust it (catches
  the real edge case of a source occasionally publishing in an
  unexpected language).
- Anything else -> fall back to what we already know about the source,
  which is correct for the overwhelming majority of articles since these
  sources were hand-curated by language in the first place.
"""

from __future__ import annotations

from fast_langdetect import detect as _ft_detect

SUPPORTED_LANGUAGES = {"en", "ru", "uz"}

# Chosen from empirical testing, not a library default: language ID
# confidence is inherently noisier on short text, and specifically noisy
# for Uzbek regardless of length. 0.8 reliably passes clear-cut en/ru
# text while still deferring to the source's declared language for the
# ambiguous Uzbek cases actually observed during testing.
HIGH_CONFIDENCE_THRESHOLD = 0.8

# Below this many characters, detection is little better than a coin
# flip for any language — don't bother running the model at all.
MIN_TEXT_LENGTH = 20


def detect_language(text: str, declared_language: str | None = None) -> str | None:
    """Best-effort language for one article.

    Returns a code in SUPPORTED_LANGUAGES, or None if detection was
    inconclusive and no usable declared_language was given either —
    callers (see pipeline/collectors/ingest.py) should decide their own
    fallback in that case rather than have this function guess.
    """
    cleaned = " ".join(text.split())  # fastText expects single-line input

    if len(cleaned) >= MIN_TEXT_LENGTH:
        result = _ft_detect(cleaned, model="lite")[0]
        lang, score = result["lang"], result["score"]
        if lang in SUPPORTED_LANGUAGES and score >= HIGH_CONFIDENCE_THRESHOLD:
            return lang

    if declared_language in SUPPORTED_LANGUAGES:
        return declared_language

    # No confident detection and no usable declared language — return
    # whatever the model guessed, if anything, purely as a last resort.
    if len(cleaned) >= MIN_TEXT_LENGTH:
        fallback_lang = result["lang"]
        return fallback_lang if fallback_lang in SUPPORTED_LANGUAGES else None

    return None
