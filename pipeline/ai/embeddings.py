"""Article embeddings, used by pipeline/processing/clustering.py for
near-duplicate and event-clustering similarity (spec Phase 3, stages 6-7).

**This is a placeholder implementation, stated plainly rather than hidden
behind a reassuring name.** The summarization provider has no native embeddings endpoint;
the spec's own AI-system section (Phase 5) anticipates pairing a summarizer with
a separate embeddings provider. That requires an external API — and this
development sandbox's network egress only allows a fixed set of
package-registry domains, so no embeddings API (Voyage AI or otherwise)
is reachable from here to build and test against.

So `compute_embedding` below is a self-contained *lexical* (bag-of-words,
feature-hashed) vector, not a real semantic embedding:
- It runs entirely offline — no model download, no API call, no network
  dependency of any kind, so the whole clustering pipeline can be built
  and genuinely tested end-to-end right now.
- It catches near-duplicates that share substantial vocabulary — the
  common case in practice (wire-service syndication, lightly-reworded
  reposts of the same story) — which is exactly the case spec Phase 3
  stage 6 calls out.
- It will NOT catch genuinely paraphrased duplicates that describe the
  same event in mostly different words. That needs real semantic
  embeddings.

**Swap-out path:** every caller goes through `compute_embedding(text)` and
nothing downstream cares how the vector was produced — replacing this
function's body with a real embeddings API call (or a locally-run
sentence-transformer, once one can be installed with model weights
included) is a one-file change. `EMBEDDING_DIM` here must keep matching
`shared.models.user.EMBEDDING_DIM` / the pgvector column width either way.
"""

from __future__ import annotations

import hashlib
import math
import re

from shared.models.user import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _stable_hash_index(token: str, dim: int) -> int:
    # Python's built-in hash() is randomized per-process (for security) —
    # unusable here, since the same article text must hash to the same
    # vector across every Celery worker process and every restart.
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


def compute_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Feature-hashed bag-of-unigrams-and-bigrams vector, L2-normalized so
    dot product == cosine similarity (matching pgvector's cosine_distance,
    which callers use directly rather than normalizing at query time).

    Returns a zero vector for empty/whitespace-only input rather than
    raising — callers decide whether a zero vector is meaningful for
    their use case (it trivially has zero cosine similarity to everything,
    which is a reasonable "no signal" default for a stray empty article).
    """
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return [0.0] * dim

    bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]

    vector = [0.0] * dim
    for token in tokens + bigrams:
        vector[_stable_hash_index(token, dim)] += 1.0

    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]
