"""Read-side port for the matcher-quality producer (consumer-defined per D17).

The legal cross-context surface: the optimization ``EvidenceContext`` will read
through this port (S91) to fold matcher-quality evidence into recommendations,
exactly as it reads ``retrieval_evaluation``'s ``EvaluationRunReader``.
``get_latest_run`` gives S91 the current quality (and the "after" to re-measure
against the S90 baseline); ``list_runs`` gives the trend.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext

from contexts.matcher_evaluation.domain import MatcherQualityRun


class MatcherQualityRunReader(Protocol):
    """Read-side port for matcher-quality run queries."""

    async def get_latest_run(
        self, *, tenant_context: TenantContext
    ) -> MatcherQualityRun | None:
        """The most recent run for the tenant (computed_at DESC), or None."""
        ...

    async def list_runs(
        self, *, tenant_context: TenantContext, limit: int
    ) -> tuple[MatcherQualityRun, ...]:
        """Up to ``limit`` runs for the tenant, newest first."""
        ...


__all__ = ["MatcherQualityRunReader"]
