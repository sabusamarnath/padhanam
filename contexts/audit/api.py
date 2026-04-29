"""Public query interface for the audit context.

Per D17, every context exposes a single api.py at its root with read-only
query methods other contexts may call. Audit's queries (chain verification,
event lookup) land in P3 with the real adapter; P2 only ships the interface
shape.
"""

from __future__ import annotations

__all__: list[str] = []
