"""Read-side port for the retrieval-evaluation runner (consumer-defined per D17).

The runner's read surface returns the three record types as a
single ``EvaluationRunSnapshot`` aggregate for ``get_evaluation_run``
and as a paginated page of run aggregates (without children) for
``list_evaluation_runs``. The optimization context at S41 reads
through this same port to fold runner evidence into recommendations.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
)


@dataclass(frozen=True)
class EvaluationRunSnapshot:
    """Aggregate snapshot returned by ``get_evaluation_run``.

    Carries the parent run, every per-query result row sorted by
    (gold_set_entry_id, retrieval_strategy), and every per-strategy
    aggregate sorted by retrieval_strategy.
    """

    run: EvaluationRun
    results: tuple[EvaluationResult, ...]
    aggregates: tuple[EvaluationAggregate, ...]


@dataclass(frozen=True)
class EvaluationRunListPage:
    """One page of ``list_evaluation_runs`` output."""

    runs: tuple[EvaluationRun, ...]
    next_cursor: EvaluationRunListCursor | None


class EvaluationRunReader(Protocol):
    """Read-side port for evaluation-run queries."""

    async def list_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: EvaluationRunListCursor | None,
        page_size: int,
    ) -> EvaluationRunListPage:
        """List runs for a tenant, paginated (invoked_at DESC, id DESC)."""
        ...

    async def get_run_with_results_and_aggregates(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> EvaluationRunSnapshot | None:
        """Read run + per-query results + per-strategy aggregates.

        Returns None when the run does not exist or belongs to a
        different tenant (tenant_isolation contract).
        """
        ...
