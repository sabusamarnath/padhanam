"""Unit tests for the matcher single-signal suppression rule (D185/S91, S91a).

The first non-inference RecommendationRule. Synthetic metric runs only — the
matcher-quality producer is label-free, so there is no PII to fixture.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from contexts.matcher_evaluation.domain import (
    MatcherQualityMetrics,
    MatcherQualityRun,
)
from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.application.rules import SuppressSingleSignalRule
from contexts.optimization.domain import (
    MatcherSuppressionEvidenceCitation,
    RecommendationCategory,
    SubstrateGapError,
)
from contexts.optimization.domain.citation_serialization import (
    citation_from_dict,
    citation_to_dict,
)
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeAuditEventReader,
    FakeEvaluationRunReader,
    FakeGoldSetReader,
    FakeRunHistoryReader,
)

_TENANT = "00000000-0000-4000-8000-00000000d001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )


def _metrics(*, single_signal: int = 28) -> MatcherQualityMetrics:
    # The S90 baseline shape: 28 single-signal == 28 candidate, 669 confirmed.
    return MatcherQualityMetrics(
        edge_count=697,
        unit_count=1359,
        orphan_count=664,
        single_signal_count=single_signal,
        candidate_count=single_signal,
        confirmed_count=669,
    )


def _run(*, single_signal: int = 28, run_id: UUID | None = None) -> MatcherQualityRun:
    from datetime import datetime, timezone

    return MatcherQualityRun(
        id=run_id or uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        computed_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        metrics=_metrics(single_signal=single_signal),
    )


class _FakeMatcherQualityRunReader:
    def __init__(self, run: MatcherQualityRun | None) -> None:
        self._run = run

    async def get_latest_run(self, *, tenant_context):
        return self._run

    async def list_runs(self, *, tenant_context, limit):
        return (self._run,) if self._run else ()


def _context(matcher_reader) -> EvidenceContext:
    return EvidenceContext(
        tenant_context=_ctx(),
        evaluation_run_reader=FakeEvaluationRunReader(),
        run_history_reader=FakeRunHistoryReader(),
        gold_set_reader=FakeGoldSetReader(),
        audit_event_reader=FakeAuditEventReader(),
        matcher_quality_run_reader=matcher_reader,
    )


def test_evidence_context_exposes_the_matcher_reader() -> None:
    reader = _FakeMatcherQualityRunReader(_run())
    ctx = _context(reader)
    assert ctx.matcher_quality_run_reader is reader


def test_rule_emits_suppress_candidate_with_evidence_impact_confidence() -> None:
    run = _run(run_id=uuid4())
    candidates = list(
        asyncio.run(
            SuppressSingleSignalRule().evaluate(
                evidence_context=_context(_FakeMatcherQualityRunReader(run))
            )
        )
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert c.category is RecommendationCategory.MATCHER_SUPPRESSION
    citation = c.evidence_citations[0]
    assert isinstance(citation, MatcherSuppressionEvidenceCitation)
    assert citation.matcher_quality_run_id == run.id
    assert citation.single_signal_count == 28
    assert citation.edge_count == 697
    assert round(citation.current_single_signal_share, 4) == 0.0402  # 28/697
    assert citation.projected_single_signal_share == 0.0  # impact
    assert 0.0 < citation.confidence <= 1.0  # carries a confidence


def test_rule_returns_empty_when_no_single_signal_edges() -> None:
    candidates = list(
        asyncio.run(
            SuppressSingleSignalRule().evaluate(
                evidence_context=_context(
                    _FakeMatcherQualityRunReader(_run(single_signal=0))
                )
            )
        )
    )
    assert candidates == []


def test_rule_substrate_gap_when_reader_absent() -> None:
    with pytest.raises(SubstrateGapError):
        asyncio.run(
            SuppressSingleSignalRule().evaluate(evidence_context=_context(None))
        )


def test_rule_substrate_gap_when_no_run_recorded() -> None:
    with pytest.raises(SubstrateGapError):
        asyncio.run(
            SuppressSingleSignalRule().evaluate(
                evidence_context=_context(_FakeMatcherQualityRunReader(None))
            )
        )


def test_matcher_citation_round_trips_through_jsonb() -> None:
    citation = MatcherSuppressionEvidenceCitation(
        matcher_quality_run_id=uuid4(),
        edge_count=697,
        single_signal_count=28,
        current_single_signal_share=28 / 697,
        projected_single_signal_share=0.0,
        confidence=0.9,
    )
    payload = citation_to_dict(citation)
    assert payload["category"] == "matcher_suppression"
    back = citation_from_dict(payload)
    assert back == citation
