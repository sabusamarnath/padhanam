"""Write-side port for the matcher-quality producer (D185).

The runner persists one ``MatcherQualityRun`` per measurement. Ports layer is
pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext

from contexts.matcher_evaluation.domain import MatcherQualityRun


class MatcherQualityRunRepository(Protocol):
    """Persists matcher-quality runs."""

    async def save(
        self, *, tenant_context: TenantContext, run: MatcherQualityRun
    ) -> None:
        """Persist one run. Append-only — runs are immutable measurements."""
        ...


__all__ = ["MatcherQualityRunRepository"]
