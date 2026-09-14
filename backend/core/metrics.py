"""Small dependency-free process metrics for health and operational checks."""

from __future__ import annotations

from collections import Counter
from threading import Lock

_counts: Counter[str] = Counter()
_lock = Lock()


def increment(name: str, value: int = 1) -> None:
    with _lock:
        _counts[name] += value


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counts)


def prometheus_text() -> str:
    lines = []
    for name, value in sorted(snapshot().items()):
        metric = "newsbot_" + name.replace("-", "_")
        lines.append(f"# TYPE {metric} counter")
        lines.append(f"{metric} {value}")
    return "\n".join(lines) + ("\n" if lines else "")
