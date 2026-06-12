"""Unit tests for the matcher-quality producer (D185, S90).

Synthetic samples only — the producer is label-free, so there is no PII to fixture.
"""

from __future__ import annotations

import asyncio
from dataclasses import fields
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.matcher_evaluation.application import record_matcher_quality_run
from contexts.matcher_evaluation.domain import (
    EdgeSample,
    MatcherQualityMetrics,
    MatcherQualityRun,
    MatcherQualitySample,
    StructuralMatcherMetrics,
)
from shared_kernel.tenant_context import TenantContext

_TENANT = "00000000-0000-4000-8000-00000000d001"
_NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )


# --- the calculator ---------------------------------------------------------

def test_calculator_computes_the_three_structural_metrics() -> None:
    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    sample = MatcherQualitySample(
        edges=(
            # a weak keyword-on-name candidate guess
            EdgeSample(unit_id=u1, is_single_signal=True, is_candidate=True, is_confirmed=False),
            # a confirmed multi-signal edge
            EdgeSample(unit_id=u2, is_single_signal=False, is_candidate=False, is_confirmed=True),
        ),
        unit_ids=frozenset({u1, u2, u3}),  # u3 has no edge -> orphan
    )
    m = StructuralMatcherMetrics().compute(sample)
    assert (m.edge_count, m.unit_count, m.orphan_count) == (2, 3, 1)
    assert (m.single_signal_count, m.candidate_count, m.confirmed_count) == (1, 1, 1)
    assert m.single_signal_share == 0.5
    assert m.candidate_to_confirmed_ratio == 1.0
    assert m.orphan_rate == 1 / 3


def test_two_edges_on_one_unit_leave_that_unit_unorphaned() -> None:
    u1, u2 = uuid4(), uuid4()
    sample = MatcherQualitySample(
        edges=(
            EdgeSample(unit_id=u1, is_single_signal=True, is_candidate=True, is_confirmed=False),
            EdgeSample(unit_id=u1, is_single_signal=False, is_candidate=False, is_confirmed=True),
        ),
        unit_ids=frozenset({u1, u2}),  # only u2 is an orphan
    )
    m = StructuralMatcherMetrics().compute(sample)
    assert m.orphan_count == 1 and m.orphan_rate == 0.5


def test_empty_sample_rates_are_zero_not_a_division_error() -> None:
    m = StructuralMatcherMetrics().compute(
        MatcherQualitySample(edges=(), unit_ids=frozenset())
    )
    assert m.single_signal_share == 0.0
    assert m.candidate_to_confirmed_ratio == 0.0
    assert m.orphan_rate == 0.0


def test_ratio_guards_a_zero_confirmed_denominator() -> None:
    u = uuid4()
    m = StructuralMatcherMetrics().compute(
        MatcherQualitySample(
            edges=(EdgeSample(unit_id=u, is_single_signal=True, is_candidate=True, is_confirmed=False),),
            unit_ids=frozenset({u}),
        )
    )
    assert m.confirmed_count == 0 and m.candidate_to_confirmed_ratio == 0.0


# --- the no-content guarantee -----------------------------------------------

def test_records_carry_counts_and_rates_only_no_content() -> None:
    # Structural assertion: the metrics value object is six integer counts; the
    # run adds only tenant/jurisdiction/time. No title, sender, subject, or text.
    metric_fields = {f.name for f in fields(MatcherQualityMetrics)}
    assert metric_fields == {
        "edge_count", "unit_count", "orphan_count",
        "single_signal_count", "candidate_count", "confirmed_count",
    }
    run_fields = {f.name for f in fields(MatcherQualityRun)}
    assert run_fields == {"id", "tenant_id", "jurisdiction", "computed_at", "metrics"}


# --- the use case: compute + persist + read back ----------------------------

class _FakeStore:
    """An in-memory repository + reader over the same list (the port round-trip)."""

    def __init__(self) -> None:
        self.runs: list[MatcherQualityRun] = []

    async def save(self, *, tenant_context: TenantContext, run: MatcherQualityRun) -> None:
        self.runs.append(run)

    async def get_latest_run(self, *, tenant_context: TenantContext) -> MatcherQualityRun | None:
        return self.runs[-1] if self.runs else None


def test_use_case_persists_a_run_the_reader_reads_back() -> None:
    store = _FakeStore()
    u1, u2 = uuid4(), uuid4()
    sample = MatcherQualitySample(
        edges=(EdgeSample(unit_id=u1, is_single_signal=True, is_candidate=True, is_confirmed=False),),
        unit_ids=frozenset({u1, u2}),
    )
    run_id = uuid4()
    run = asyncio.run(
        record_matcher_quality_run(
            tenant_context=_ctx(),
            sample=sample,
            repository=store,
            run_id=run_id,
            computed_at=_NOW,
        )
    )
    assert run.id == run_id
    assert run.tenant_id == UUID(_TENANT)
    assert run.metrics.single_signal_share == 1.0
    # reads back through the (same-store) reader port
    back = asyncio.run(store.get_latest_run(tenant_context=_ctx()))
    assert back is not None and back.id == run_id
    assert back.metrics.orphan_count == 1  # u2 unlinked
