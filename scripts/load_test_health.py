"""Small smoke/load test for the unauthenticated backend health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def run(url: str, requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    failures = 0

    async with httpx.AsyncClient(timeout=10) as client:
        async def one() -> None:
            nonlocal failures
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    if response.json().get("status") != "ok":
                        failures += 1
                except (httpx.HTTPError, ValueError):
                    failures += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        await asyncio.gather(*(one() for _ in range(requests)))

    print({
        "requests": requests,
        "concurrency": concurrency,
        "failures": failures,
        "p50_ms": round(statistics.median(latencies), 2),
        "max_ms": round(max(latencies), 2),
    })
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.requests, args.concurrency))
