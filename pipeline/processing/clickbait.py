"""Heuristic clickbait scoring (spec Phase 3 stage 9 / Phase 5: "Heuristics
primary, LLM fallback for borderline cases" — this module is the heuristic
half; an LLM fallback for genuinely ambiguous titles is M10's job, not
this one's).

Title-only on purpose — clickbait is fundamentally about the headline
promising something the framing exploits (curiosity gaps, manufactured
urgency, listicle structure), not about article body content. Checking
the body wouldn't add signal here.

English, Russian, and (as of M14) Uzbek pattern sets — see
backend/db/seed_sources.py for the Uzbek source that closed this gap.
The Uzbek list is a smaller, less battle-tested starting set than en/ru's.
"""

from __future__ import annotations

import re

_CLICKBAIT_PATTERNS_EN = [
    r"you won'?t believe",
    r"shocking",
    r"mind.?blowing",
    r"goes viral",
    r"breaks? the internet",
    r"here'?s why",
    r"this is why",
    r"what happened next",
    r"one weird trick",
    r"doctors hate",
    r"will change your life",
    r"this simple trick",
    r"number \d+ will",
    r"^\d+\s+(reasons|things|ways|signs|secrets|facts|tips)\b",
]

_CLICKBAIT_PATTERNS_RU = [
    r"вы не поверите",
    r"шокирующ",
    r"это шокирует",
    r"взорвал\w* интернет",
    r"вот почему",
    r"что случилось дальше",
    r"^\d+\s+(причин|способов|фактов|секретов|признаков)\b",
]

_CLICKBAIT_PATTERNS_UZ = [
    r"ishonmaysiz",
    r"hayratlanarli",
    r"internetni portlatdi",
    r"mana nega",
    r"keyin nima bo'ldi",
    r"^\d+\s+(sabab|usul|fakt|sir|belgi)\b",
]

_ALL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in _CLICKBAIT_PATTERNS_EN + _CLICKBAIT_PATTERNS_RU + _CLICKBAIT_PATTERNS_UZ
]

_PATTERN_WEIGHT = 0.3
_EXCLAMATION_WEIGHT = 0.1  # per "!", capped via the multi-exclamation branch below
_MIXED_PUNCTUATION_WEIGHT = 0.2
_SHOUTING_WEIGHT = 0.25

# A single capitalized acronym (NASA, US, UK) is normal in headlines; two
# or more separate all-caps words in one title reads as shouting.
_SHOUTING_MIN_WORDS = 2
_SHOUTING_MIN_WORD_LENGTH = 4


def score_clickbait(title: str) -> float:
    """Returns a 0-1 score; higher means more clickbait-like. Checks both
    language pattern sets unconditionally rather than branching on a
    passed-in language — Cyrillic and Latin patterns can't accidentally
    cross-match, so there's no false-positive risk from checking both,
    and it means a misdetected language doesn't get a free pass.
    """
    if not title:
        return 0.0

    score = 0.0

    for pattern in _ALL_PATTERNS:
        if pattern.search(title):
            score += _PATTERN_WEIGHT

    exclamation_count = title.count("!")
    if exclamation_count >= 2:
        score += _EXCLAMATION_WEIGHT * 2
    elif exclamation_count == 1:
        score += _EXCLAMATION_WEIGHT

    if "!?" in title or "?!" in title:
        score += _MIXED_PUNCTUATION_WEIGHT

    words = re.findall(r"[^\W\d_]+", title, re.UNICODE)
    shouting_words = [w for w in words if len(w) >= _SHOUTING_MIN_WORD_LENGTH and w.isupper()]
    if len(shouting_words) >= _SHOUTING_MIN_WORDS:
        score += _SHOUTING_WEIGHT

    return min(score, 1.0)
