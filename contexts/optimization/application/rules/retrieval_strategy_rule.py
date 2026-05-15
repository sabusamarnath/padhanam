"""RetrievalStrategyRule — pairwise recall@3 delta trigger (D111 cmt 5).

Consumes completed evaluation runs via ``EvaluationRunReader``,
computes pairwise per-strategy recall@3 deltas inside each run, and
emits a ``RecommendationCandidate`` per (run, strategy_a,
strategy_b) pair where the recall@3 delta exceeds the configured
absolute threshold (default 0.15 per the S40b S41-evidence verdict).

Trigger surface choices (per Finding 3b disposition):

- Primary trigger metric: recall@3 absolute delta. Other k values
  (1, 5, 10) are emitted in the citation for procurement-grade
  transparency but do not gate emission. Per S40b: recall@k
  differentials at @3 are the load-bearing procurement-grade
  surface; MRR is structurally non-discriminating in this evaluation
  setup; recall@1 is too noisy for triggering.
- Pair ordering: alphabetical on strategy name to avoid duplicate
  emission of the same comparison.
- Caveat annotation (per Finding 3a disposition): when either
  compared strategy's aggregates are all-zeros, attach a structured
  ``CaveatAnnotation`` carrying ``caveat_code=
  infrastructure_substrate_check_required``. The recommendation is
  still emitted (rule-pure semantics); the caveat surfaces the
  substrate-state for procurement readers to weigh.

Pagination: the reader returns pages of run summaries; the rule
walks pages until exhausted to consider every completed run.
Per-run snapshot fetch retrieves aggregates because the list-page
shape omits them.
"""

from __future__ import annotations

from typing import Iterable

from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.domain import (
    CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
    CaveatAnnotation,
    RecommendationCandidate,
    RecommendationCategory,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationRun,
    EvaluationRunStatus,
)


DEFAULT_RECALL_AT_K_DELTA_THRESHOLD: float = 0.15
PRIMARY_K: int = 3
PAGE_SIZE: int = 50  # reader page-size ceiling per D97


class RetrievalStrategyRule:
    """Default retrieval-strategy rule (D111 cmt 5)."""

    category: RecommendationCategory = RecommendationCategory.RETRIEVAL_STRATEGY

    def __init__(
        self,
        *,
        recall_at_k_delta_threshold: float = DEFAULT_RECALL_AT_K_DELTA_THRESHOLD,
    ) -> None:
        if recall_at_k_delta_threshold < 0:
            raise ValueError(
                "recall_at_k_delta_threshold must be >= 0; "
                f"got {recall_at_k_delta_threshold}"
            )
        self._threshold = recall_at_k_delta_threshold

    async def evaluate(
        self,
        *,
        evidence_context: EvidenceContext,
    ) -> Iterable[RecommendationCandidate]:
        candidates: list[RecommendationCandidate] = []
        async for run in _iterate_completed_runs(evidence_context):
            snapshot = await evidence_context.evaluation_run_reader.get_run_with_results_and_aggregates(
                tenant_context=evidence_context.tenant_context,
                run_id=run.id,
            )
            if snapshot is None:
                continue
            for candidate in self._emit_for_run(
                run=snapshot.run,
                aggregates=snapshot.aggregates,
            ):
                candidates.append(candidate)
        return candidates

    def _emit_for_run(
        self,
        *,
        run: EvaluationRun,
        aggregates: tuple[EvaluationAggregate, ...],
    ) -> Iterable[RecommendationCandidate]:
        if len(aggregates) < 2:
            return ()
        by_strategy: dict[str, EvaluationAggregate] = {
            a.retrieval_strategy: a for a in aggregates
        }
        emitted: list[RecommendationCandidate] = []
        strategies = sorted(by_strategy.keys())
        for i, strategy_a in enumerate(strategies):
            for strategy_b in strategies[i + 1 :]:
                agg_a = by_strategy[strategy_a]
                agg_b = by_strategy[strategy_b]
                recall_a = float(agg_a.recall_at_k_mean.get(PRIMARY_K, 0.0))
                recall_b = float(agg_b.recall_at_k_mean.get(PRIMARY_K, 0.0))
                delta = abs(recall_b - recall_a)
                if delta <= self._threshold:
                    continue
                candidate = self._build_candidate(
                    run=run,
                    agg_a=agg_a,
                    agg_b=agg_b,
                )
                emitted.append(candidate)
        return emitted

    def _build_candidate(
        self,
        *,
        run: EvaluationRun,
        agg_a: EvaluationAggregate,
        agg_b: EvaluationAggregate,
    ) -> RecommendationCandidate:
        # Identify underperformer vs overperformer for prose direction.
        recall_a_at_primary = float(agg_a.recall_at_k_mean.get(PRIMARY_K, 0.0))
        recall_b_at_primary = float(agg_b.recall_at_k_mean.get(PRIMARY_K, 0.0))
        if recall_a_at_primary < recall_b_at_primary:
            underperformer, overperformer = agg_a, agg_b
        else:
            underperformer, overperformer = agg_b, agg_a

        recall_at_k_delta = {
            k: float(agg_b.recall_at_k_mean.get(k, 0.0))
            - float(agg_a.recall_at_k_mean.get(k, 0.0))
            for k in (1, 3, 5, 10)
        }
        precision_at_k_delta = {
            k: float(agg_b.precision_at_k_mean.get(k, 0.0))
            - float(agg_a.precision_at_k_mean.get(k, 0.0))
            for k in (1, 3, 5, 10)
        }
        comparison = StrategyComparison(
            strategy_a=agg_a.retrieval_strategy,
            strategy_b=agg_b.retrieval_strategy,
            recall_at_k_delta=recall_at_k_delta,
            precision_at_k_delta=precision_at_k_delta,
        )
        caveats = _build_caveats(agg_a=agg_a, agg_b=agg_b)
        citation = RetrievalStrategyEvidenceCitation(
            evaluation_run_id=run.id,
            gold_set_id=run.gold_set_id,
            comparison=comparison,
            caveats=caveats,
        )
        text = (
            f"Switch from {underperformer.retrieval_strategy} to "
            f"{overperformer.retrieval_strategy} for retrieval on this tenant. "
            f"Evidence: gold-set {run.gold_set_id} run {run.id} shows "
            f"recall@{PRIMARY_K} of "
            f"{float(underperformer.recall_at_k_mean.get(PRIMARY_K, 0.0)):.4f} "
            f"for {underperformer.retrieval_strategy} vs "
            f"{float(overperformer.recall_at_k_mean.get(PRIMARY_K, 0.0)):.4f} "
            f"for {overperformer.retrieval_strategy} "
            f"(absolute delta "
            f"{abs(recall_b_at_primary - recall_a_at_primary):.4f})."
        )
        subject = (
            f"{agg_a.retrieval_strategy} vs {agg_b.retrieval_strategy} "
            f"on gold_set {str(run.gold_set_id)[:8]}"
        )
        return RecommendationCandidate(
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject=subject,
            text=text,
            evidence_citations=(citation,),
        )


def _is_all_zero(aggregate: EvaluationAggregate) -> bool:
    """Detect an all-zero aggregate (D111 cmt 7 caveat trigger).

    An aggregate is "all-zeros" when every per-k mean is zero AND the
    mean-MRR is zero. The (i) filter-all-zero-strategies alternative
    was rejected per Finding 3a (ii); the caveat annotation is the
    structurally-honest cut.
    """
    recall_zero = all(
        float(v) == 0.0 for v in aggregate.recall_at_k_mean.values()
    )
    precision_zero = all(
        float(v) == 0.0 for v in aggregate.precision_at_k_mean.values()
    )
    mrr_zero = float(aggregate.mrr_mean) == 0.0
    return recall_zero and precision_zero and mrr_zero


def _build_caveats(
    *,
    agg_a: EvaluationAggregate,
    agg_b: EvaluationAggregate,
) -> tuple[CaveatAnnotation, ...]:
    caveats: list[CaveatAnnotation] = []
    for agg in (agg_a, agg_b):
        if _is_all_zero(agg):
            caveats.append(
                CaveatAnnotation(
                    strategy_id=agg.retrieval_strategy,
                    state="all_zero_aggregates",
                    caveat_code=CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
                )
            )
    return tuple(caveats)


async def _iterate_completed_runs(evidence_context: EvidenceContext):
    """Yield every completed evaluation run for the bound tenant.

    Async generator over reader pagination. The retrieval evaluation
    reader returns pages of run summaries (without children); the
    consumer fetches snapshots for the runs it wants to inspect.
    """
    cursor = None
    while True:
        page = await evidence_context.evaluation_run_reader.list_runs(
            tenant_context=evidence_context.tenant_context,
            cursor=cursor,
            page_size=PAGE_SIZE,
        )
        for run in page.runs:
            if run.status is EvaluationRunStatus.COMPLETED:
                yield run
        if page.next_cursor is None:
            break
        cursor = page.next_cursor


__all__ = [
    "DEFAULT_RECALL_AT_K_DELTA_THRESHOLD",
    "PRIMARY_K",
    "RetrievalStrategyRule",
]
