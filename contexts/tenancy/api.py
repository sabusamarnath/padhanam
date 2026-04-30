"""Public query interface for the tenancy context.

Per D17, every context exposes a single api.py at its root with read-only
query methods other contexts may call. Tenancy's queries (tenant lookup,
jurisdiction filter) land in S10 with the real registry adapter; S9 only
ships the interface shape.
"""

from __future__ import annotations

__all__: list[str] = []
