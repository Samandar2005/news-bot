"""Backend-local re-export of the shared settings object.

Defined once in shared/config.py (bot, backend, and workers all need the
same DB/Redis connection info); this module exists so backend code can
`from backend.core.config import settings` per the documented project
structure, without a second Settings definition living here.
"""

from shared.config import settings

__all__ = ["settings"]
