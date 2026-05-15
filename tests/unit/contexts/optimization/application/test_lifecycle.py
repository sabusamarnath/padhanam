"""Unit tests for the three lifecycle-transition use cases."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.optimization.application import (
    RecommendationNotFoundError,
    TransitionNotPermittedError,
    acknowledge_recommendation,
    apply_recommendation,
    reject_recommendation,
)
from contexts.optimization.application.audit_events import (
    ACTION_RECOMMENDATION_ACKNOWLEDGE,
    ACTION_RECOMMENDATION_APPLY,
    ACTION_RECOMMENDATION_REJECT,
)
from contexts.optimization.domain import (
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeRecommendationReader,
    FakeRecommendationRepository,
    RecordingAuditPort,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_A = "00000000-0000-0000-0000-00000000a000"
_TENANT_B = "00000000-0000-0000-0000-00000000b000"


def _tenant_ctx(tenant_id: str = _TENANT_A) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        jurisdiction="GB",
        cost_attribution_id="cost-attr-1",
    )


def _citation() -> RetrievalStrategyEvidenceCitation:
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="graph_only",
            strategy_b="vector_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.87, 10: 1.0},
            precision_at_k_delta={1: 1.0, 3: 0.67, 5: 0.47, 10: 0.3},
        ),
    )


def _generated_recommendation(
    *,
    tenant_id: str = _TENANT_A,
    rec_id: UUID | None = None,
) -> Recommendation:
    return Recommendation(
        id=rec_id or uuid4(),
        tenant_id=UUID(tenant_id),
        jurisdiction="GB",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="x",
        text="Switch from graph_only to vector_only.",
        evidence_citations=(_citation(),),
        status=RecommendationStatus.GENERATED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=None,
    )


def _seed(
    *recommendations: Recommendation,
) -> tuple[FakeRecommendationRepository, FakeRecommendationReader]:
    repo = FakeRecommendationRepository()
    for rec in recommendations:
        repo.recommendations[rec.id] = rec
    reader = FakeRecommendationReader(repository=repo)
    return repo, reader


# ----------------------------------------------------------------------
# acknowledge_recommendation
# ----------------------------------------------------------------------


def test_acknowledge_transitions_generated_to_acknowledged() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    audit = RecordingAuditPort()
    result = asyncio.run(
        acknowledge_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-1",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    assert result.recommendation.status is RecommendationStatus.ACKNOWLEDGED
    assert result.recommendation.last_transition_by_user_id == "user-1"
    assert result.transition.from_status is RecommendationStatus.GENERATED
    assert result.transition.to_status is RecommendationStatus.ACKNOWLEDGED
    assert repo.transitions[-1].id == result.transition.id
    assert audit.events[-1].action_verb == ACTION_RECOMMENDATION_ACKNOWLEDGE


def test_acknowledge_embeds_full_citation_in_audit_event() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    audit = RecordingAuditPort()
    asyncio.run(
        acknowledge_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-1",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    citation_payload = audit.events[-1].after_state["evidence_citations"]
    assert isinstance(citation_payload, list)
    assert citation_payload[0]["category"] == "retrieval_strategy"


def test_acknowledge_missing_recommendation_raises() -> None:
    repo, reader = _seed()
    with pytest.raises(RecommendationNotFoundError):
        asyncio.run(
            acknowledge_recommendation(
                tenant_context=_tenant_ctx(),
                recommendation_id=uuid4(),
                actor_user_id="user-1",
                reader=reader,
                repository=repo,
                audit_port=RecordingAuditPort(),
            )
        )


def test_acknowledge_cross_tenant_returns_not_found() -> None:
    rec = _generated_recommendation(tenant_id=_TENANT_B)
    repo, reader = _seed(rec)
    with pytest.raises(RecommendationNotFoundError):
        asyncio.run(
            acknowledge_recommendation(
                tenant_context=_tenant_ctx(_TENANT_A),
                recommendation_id=rec.id,
                actor_user_id="user-1",
                reader=reader,
                repository=repo,
                audit_port=RecordingAuditPort(),
            )
        )


# ----------------------------------------------------------------------
# apply_recommendation
# ----------------------------------------------------------------------


def test_apply_transitions_generated_directly_to_applied() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    audit = RecordingAuditPort()
    result = asyncio.run(
        apply_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-2",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    assert result.recommendation.status is RecommendationStatus.APPLIED
    assert audit.events[-1].action_verb == ACTION_RECOMMENDATION_APPLY


def test_apply_blocks_after_rejected() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    audit = RecordingAuditPort()
    asyncio.run(
        reject_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-1",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    with pytest.raises(TransitionNotPermittedError) as excinfo:
        asyncio.run(
            apply_recommendation(
                tenant_context=_tenant_ctx(),
                recommendation_id=rec.id,
                actor_user_id="user-2",
                reader=reader,
                repository=repo,
                audit_port=audit,
            )
        )
    assert excinfo.value.from_status is RecommendationStatus.REJECTED
    assert excinfo.value.to_status is RecommendationStatus.APPLIED


# ----------------------------------------------------------------------
# reject_recommendation
# ----------------------------------------------------------------------


def test_reject_transitions_acknowledged_to_rejected() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    audit = RecordingAuditPort()
    asyncio.run(
        acknowledge_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-1",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    result = asyncio.run(
        reject_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            actor_user_id="user-2",
            reader=reader,
            repository=repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    assert result.recommendation.status is RecommendationStatus.REJECTED
    assert audit.events[-1].action_verb == ACTION_RECOMMENDATION_REJECT


def test_reject_with_empty_actor_raises() -> None:
    rec = _generated_recommendation()
    repo, reader = _seed(rec)
    with pytest.raises(ValueError, match="actor_user_id"):
        asyncio.run(
            reject_recommendation(
                tenant_context=_tenant_ctx(),
                recommendation_id=rec.id,
                actor_user_id="",
                reader=reader,
                repository=repo,
                audit_port=RecordingAuditPort(),
            )
        )
