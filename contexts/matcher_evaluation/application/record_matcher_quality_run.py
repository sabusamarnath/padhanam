"""record_matcher_quality_run use case — measure + persist one run (D185).

The producer's single use case: given a classified ``MatcherQualitySample``,
compute the structural metrics via the injected ``MatcherMetricCalculator`` and
persist a ``MatcherQualityRun`` through the repository. Returns the run so the
caller (the apps bridge, at the correlate hook) can log counts.

Observe-only with respect to the matcher: this neither reads nor writes the
SERVES graph; it records a measurement of edges the matcher already produced.
Counts and rates only — the sample is label-free, so nothing content-bearing
reaches the record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared_kernel.tenant_context import TenantContext

from contexts.matcher_evaluation.domain import (
    MatcherMetricCalculator,
    MatcherQualityRun,
    MatcherQualitySample,
    StructuralMatcherMetrics,
)
from contexts.matcher_evaluation.ports import MatcherQualityRunRepository


async def record_matcher_quality_run(
    *,
    tenant_context: TenantContext,
    sample: MatcherQualitySample,
    repository: MatcherQualityRunRepository,
    calculator: MatcherMetricCalculator | None = None,
    run_id: UUID | None = None,
    computed_at: datetime | None = None,
) -> MatcherQualityRun:
    """Compute the run's structural metrics and persist it. Returns the run."""
    calculator = calculator or StructuralMatcherMetrics()
    metrics = calculator.compute(sample)
    run = MatcherQualityRun(
        id=run_id or uuid4(),
        tenant_id=UUID(str(tenant_context.tenant_id)),
        jurisdiction=tenant_context.jurisdiction,
        computed_at=computed_at or datetime.now(timezone.utc),
        metrics=metrics,
    )
    await repository.save(tenant_context=tenant_context, run=run)
    return run


__all__ = ["record_matcher_quality_run"]
