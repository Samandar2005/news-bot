"""Google Gemini summarization provider.

Uses the Google GenAI SDK's async client. One compact prompt produces the
requested language directly; no separate translation call is made.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from pipeline.ai.provider_base import SummaryResult
from shared.config import settings

_LANGUAGE_NAMES = {"en": "English", "ru": "Russian", "uz": "Uzbek"}
_SYSTEM_PROMPT = (
    "Summarize the supplied news excerpts in the requested language. "
    "Use only stated facts; omit speculation and clickbait. Return 2 concise "
    "sentences, plain text only."
)


class GoogleSummarizationProvider:
    """Gemini-backed provider, compatible with SummarizationProvider."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or settings.google_api_key
        if not key:
            raise ValueError("GOOGLE_API_KEY is required for summarization")
        self._client = genai.Client(api_key=key)
        self._model = model or settings.summarization_model

    async def summarize(self, source_texts: list[str], target_language: str) -> SummaryResult:
        language = _LANGUAGE_NAMES.get(target_language, target_language)
        excerpts = "\n---\n".join(source_texts)
        prompt = f"Language: {language}\nExcerpts:\n{excerpts}"
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=180,
            ),
        )
        usage = response.usage_metadata
        return SummaryResult(
            text=(response.text or "").strip(),
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client when the SDK exposes a close hook."""
        close = getattr(self._client.aio, "aclose", None)
        if close is not None:
            await close()


# Short generic name for dependency injection and future providers.
SummarizationProviderImpl = GoogleSummarizationProvider

__all__ = ["GoogleSummarizationProvider", "SummarizationProviderImpl"]
