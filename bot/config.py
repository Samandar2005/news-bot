"""Bot-local re-export of the shared settings object — see
backend/core/config.py for the same pattern and rationale.
"""

from shared.config import settings

__all__ = ["settings"]
