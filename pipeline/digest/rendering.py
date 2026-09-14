"""Digest message rendering (spec Phase 3 stage 13).

Pure text formatting — no DB, no network — so it's testable in isolation
from the ranking/summary lookup that produces its input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.scoring.relevance import RankedEvent

# Telegram's hard limit is 4096 characters; staying well under it leaves
# headroom for the header/formatting overhead added below without needing
# to precisely account for every character.
MAX_MESSAGE_CHARS = 3500

_HEADER = {
    "en": "📰 Your news digest",
    "ru": "📰 Ваша подборка новостей",
    "uz": "📰 Sizning yangiliklar to'plamingiz",
}


def render_digest_message(items: list[tuple["RankedEvent", str]], language: str) -> str:
    """`items` is (ranked_event, summary_text) pairs, already in the order
    they should appear — this function doesn't re-sort or filter, only
    renders, and stops adding entries once the message would exceed
    MAX_MESSAGE_CHARS rather than truncating mid-summary (spec Phase 3
    stage 13's "fewer than N relevant events — send fewer" edge case
    applies here too, at the rendering level, as a safety net even though
    pipeline/digest/assembly.py should rarely hand this function enough
    items to actually hit the cap).
    """
    header = _HEADER.get(language, _HEADER["en"])
    lines = [header, ""]
    current_length = len(header) + 1

    for i, (_ranked, summary_text) in enumerate(items, start=1):
        entry = f"{i}. {summary_text}"
        if current_length + len(entry) + 2 > MAX_MESSAGE_CHARS:
            break
        lines.append(entry)
        lines.append("")
        current_length += len(entry) + 2

    return "\n".join(lines).strip()
