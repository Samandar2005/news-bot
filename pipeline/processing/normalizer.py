"""Normalization helpers.

This module starts small on purpose: M4 (collection) needs *some*
content_hash and *some* cleanup to write a valid `news_articles` row at
all, so that minimum lives here now. Full boilerplate/ad stripping via
trafilatura, encoding edge cases, and language-aware cleanup are M5's
scope (spec Phase 3, stage 3) and will extend this file rather than
replace it.
"""

from __future__ import annotations

import hashlib
import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html_lightly(raw: str) -> str:
    """Remove HTML tags and decode entities from an RSS description/content
    fragment. Deliberately simple regex-based stripping — this is for
    short feed-supplied snippets, not full web pages (that's trafilatura's
    job in M5, for the "fetch full article body" case)."""
    text = _TAG_RE.sub(" ", raw)
    text = unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def compute_content_hash(title: str, content: str) -> str:
    """sha256 of normalized title+content — the cheap exact-duplicate
    pre-filter from spec Phase 3, stage 6, ahead of the embedding
    similarity check that lands in M7.
    """
    normalized = f"{title.strip().lower()}|{content.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
