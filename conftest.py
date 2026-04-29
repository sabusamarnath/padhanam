"""Project-root pytest configuration.

The Meridian top-level package is named ``platform`` (per D16 and
charter/principles.md). Python's stdlib also ships a ``platform`` module that
pytest imports during startup for its banner. Once the stdlib version is in
``sys.modules`` the import system never reconsults sys.path, so our package
shadows nothing — instead the stdlib module shadows ours, and any
``from platform.config import ...`` fails with ``'platform' is not a package``.

Why this matters: the charter commits to ``platform/`` as the cross-cutting
layer, and renaming would force a charter rewrite. Evicting the stdlib module
from ``sys.modules`` is the smallest fix that preserves the architectural
naming. We do not import stdlib ``platform`` anywhere in Meridian code, so
the eviction has no functional cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_existing = sys.modules.get("platform")
if _existing is not None and not hasattr(_existing, "__path__"):
    del sys.modules["platform"]
    import platform  # noqa: F401  # re-imports as the Meridian platform package
