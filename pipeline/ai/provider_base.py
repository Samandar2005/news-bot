"""Provider abstraction for AI summarization (spec: "design so the AI
provider can be replaced later").

A `Protocol` (structural typing), not an ABC — any object with a matching
`summarize()` method works as a provider, including test doubles that
don't need to inherit from anything. `pipeline/ai/google_provider.py`
is the real implementation; tests use a small fake (see
tests/integration/test_summarizer.py) so the summarization *logic*
(caching, batching, truncation) is fully testable without a network call
or a real API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SummaryResult:
    text: str
    input_tokens: int
    output_tokens: int


class SummarizationProvider(Protocol):
    async def summarize(self, source_texts: list[str], target_language: str) -> SummaryResult:
        """Produces one summary from one or more source article excerpts,
        written in target_language (a code like "en"/"ru"/"uz") regardless
        of what language the source excerpts are in — see spec Phase 5.2:
        generating directly in the target language is cheaper than a
        separate translate step.
        """
        ...
