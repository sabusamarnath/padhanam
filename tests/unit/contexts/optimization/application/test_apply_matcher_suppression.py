"""Unit tests for the category-aware matcher apply (D186/S91b).

Applying a matcher_suppression recommendation writes the active policy to the
neutral surface and marks the recommendation APPLIED. Idempotent. No PII.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.matcher_policy.domain import MatcherPolicy
from contexts.optimization.application._transition_helpers import (
    RecommendationNotFoundError,
)
from contexts.optimization.application.apply_matcher_suppression import (
    apply_matcher_suppression,
)
from contexts.optimization.domain import (
    MatcherSuppressionEvidenceCitation,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeRecommendationReader,
    FakeRecommendationRepository,
    RecordingAuditPort,
)

_NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)
_TENANT = "00000000-0000-4000-8000-00000000d001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )


def _matcher_recommendation(rec_id: UUID | None = None) -> Recommendation:
    citation = MatcherSuppressionEvidenceCitation(
        matcher_quality_run_id=uuid4(),
        edge_count=697,
        single_signal_count=28,
        current_single_signal_share=28 / 697,
        projected_single_signal_share=0.0,
        confidence=0.9,
    )
    return Recommendation(
        id=rec_id or uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        category=RecommendationCategory.MATCHER_SUPPRESSION,
        subject="Suppress single-signal keyword-on-name candidate matches",
        text="28 single-signal edges; project to ~0.",
        evidence_citations=(citation,),
        status=RecommendationStatus.GENERATED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=None,
    )


def _seed(rec: Recommendation):
    repo = FakeRecommendationRepository()
    repo.recommendations[rec.id] = rec
    return repo, FakeRecommendationReader(repository=repo)


class _FakePolicyRepo:
    def __init__(self) -> None:
        self.policy: MatcherPolicy | None = None
        self.writes = 0

    async def set_policy(self, *, tenant_context, policy: MatcherPolicy) -> None:
        self.policy = policy
        self.writes += 1


def test_apply_writes_policy_and_marks_applied() -> None:
    rec = _matcher_recommendation()
    repo, reader = _seed(rec)
    policy_repo = _FakePolicyRepo()
    applied = asyncio.run(
        apply_matcher_suppression(
            tenant_context=_ctx(),
            recommendation_id=rec.id,
            actor_user_id="operator",
            reader=reader,
            repository=repo,
            audit_port=RecordingAuditPort(),
            policy_repository=policy_repo,
            now=_NOW,
        )
    )
    assert policy_repo.policy == MatcherPolicy(suppress_single_signal=True)
    assert applied.status is RecommendationStatus.APPLIED


def test_apply_is_idempotent_on_repeat() -> None:
    rec = _matcher_recommendation()
    repo, reader = _seed(rec)
    policy_repo = _FakePolicyRepo()
    args = dict(
        tenant_context=_ctx(),
        recommendation_id=rec.id,
        actor_user_id="operator",
        reader=reader,
        repository=repo,
        audit_port=RecordingAuditPort(),
        policy_repository=policy_repo,
        now=_NOW,
    )
    asyncio.run(apply_matcher_suppression(**args))
    again = asyncio.run(apply_matcher_suppression(**args))  # no error
    assert policy_repo.policy.suppress_single_signal is True
    assert again.status is RecommendationStatus.APPLIED


def test_apply_rejects_a_non_matcher_recommendation() -> None:
    from contexts.optimization.domain import (
        RetrievalStrategyEvidenceCitation,
        StrategyComparison,
    )

    rec = Recommendation(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="x",
        text="y",
        evidence_citations=(
            RetrievalStrategyEvidenceCitation(
                evaluation_run_id=uuid4(),
                gold_set_id=uuid4(),
                comparison=StrategyComparison(
                    strategy_a="a", strategy_b="b",
                    recall_at_k_delta={3: 0.2}, precision_at_k_delta={3: 0.2},
                ),
            ),
        ),
        status=RecommendationStatus.GENERATED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=None,
    )
    repo, reader = _seed(rec)
    with pytest.raises(ValueError):
        asyncio.run(
            apply_matcher_suppression(
                tenant_context=_ctx(),
                recommendation_id=rec.id,
                actor_user_id="operator",
                reader=reader,
                repository=repo,
                audit_port=RecordingAuditPort(),
                policy_repository=_FakePolicyRepo(),
                now=_NOW,
            )
        )


def test_revert_writes_the_flag_back_to_false() -> None:
    from contexts.matcher_policy.domain import MatcherPolicy
    from contexts.optimization.application import revert_matcher_suppression

    policy_repo = _FakePolicyRepo()
    # arm it, then revert
    asyncio.run(
        policy_repo.set_policy(
            tenant_context=_ctx(),
            policy=MatcherPolicy(suppress_single_signal=True),
        )
    )
    asyncio.run(
        revert_matcher_suppression(
            tenant_context=_ctx(), policy_repository=policy_repo
        )
    )
    assert policy_repo.policy == MatcherPolicy(suppress_single_signal=False)


def test_revert_is_idempotent() -> None:
    from contexts.matcher_policy.domain import MatcherPolicy
    from contexts.optimization.application import revert_matcher_suppression

    policy_repo = _FakePolicyRepo()
    asyncio.run(
        revert_matcher_suppression(
            tenant_context=_ctx(), policy_repository=policy_repo
        )
    )
    asyncio.run(
        revert_matcher_suppression(
            tenant_context=_ctx(), policy_repository=policy_repo
        )
    )
    assert policy_repo.policy.suppress_single_signal is False


def test_apply_unknown_recommendation_raises() -> None:
    repo, reader = _seed(_matcher_recommendation())
    with pytest.raises(RecommendationNotFoundError):
        asyncio.run(
            apply_matcher_suppression(
                tenant_context=_ctx(),
                recommendation_id=uuid4(),  # not seeded
                actor_user_id="operator",
                reader=reader,
                repository=repo,
                audit_port=RecordingAuditPort(),
                policy_repository=_FakePolicyRepo(),
                now=_NOW,
            )
        )
