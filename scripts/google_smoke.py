import asyncio

from pipeline.ai.google_provider import GoogleSummarizationProvider


async def main() -> None:
    provider = GoogleSummarizationProvider()
    result = await provider.summarize(
        ["NASA announced a new Mars mission scheduled for launch in 2028."],
        "uz",
    )
    print(
        {
            "text": result.text,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
