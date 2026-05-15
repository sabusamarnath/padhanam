"""CostOptimizationRule — cost-per-successful-task trigger (D111 cmt 5).

Aggregates client-side over ``RunHistoryReader.list_runs_with_filters``
for a configurable time window (default 14 days), computes
cost-per-successful-task by ``agent_template_id``, and emits a
``RecommendationCandidate`` per template whose mean exceeds the
configured threshold (default $0.10).

Aggregation choices (per D111 cmt 5 reasoning):

- Rollup key: ``agent_template_id``. ``RunRecord`` per S31 D95
  carries ``agent_template_id`` and ``total_cost_usd`` but not
  ``model_id``; aggregation by template is the structurally honest
  cut at Phase 1 substrate. Model rollup is a Phase 2 promotion if
  recommendation evidence demands.
- Successful task definition: ``termination_reason in {'content',
  'max_iterations'}`` — runs that produced an output the user can
  consume. Other termination reasons (error, tool_not_registered,
  invariant_blocked, failed) are excluded from the success
  numerator. Per D111 alternative (m) reasoning: aggregating over
  the reader's existing filter surface is the Phase 1 cut.
- Mean computation: ``sum(total_cost_usd) / count(successful_runs)``.
  The cost denominator is "successful runs only" because the
  recommendation surface is "cost per task you actually got
  value from". The citation surfaces both ``n_successful_runs`` and
  ``n_runs_total`` so procurement readers see the success ratio.
- Time window: lower-inclusive, upper-exclusive 14-day window
  ending now. The reader's ``started_at_range`` filter applies.

Pagination: walks reader pages until exhausted; PAGE_SIZE_CEILING
from D97 caps individual page sizes at 50.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.domain import (
    CostAggregate,
    CostOptimizationEvidenceCitation,
    RecommendationCandidate,
    RecommendationCategory,
)
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord


DEFAULT_COST_PER_SUCCESSFUL_TASK_THRESHOLD_USD: float = 0.10
DEFAULT_WINDOW_DAYS: int = 14

# D95 six-value CHECK set: 'content' and 'max_iterations' are the
# two terminal reasons that produce a consumable output. The other
# four ('tool_not_registered', 'error', 'invariant_blocked',
# 'failed') terminate the agent loop without a user-consumable
# result; they count toward n_runs_total but not n_successful_runs.
SUCCESSFUL_TERMINATION_REASONS: tuple[str, ...] = ("content", "max_iterations")


class CostOptimizationRule:
    """Default cost-optimization rule (D111 cmt 5)."""

    category: RecommendationCategory = RecommendationCategory.COST_OPTIMIZATION

    def __init__(
        self,
        *,
        cost_per_successful_task_threshold_usd: float = (
            DEFAULT_COST_PER_SUCCESSFUL_TASK_THRESHOLD_USD
        ),
        window_days: int = DEFAULT_WINDOW_DAYS,
        now: datetime | None = None,
    ) -> None:
        if cost_per_successful_task_threshold_usd < 0:
            raise ValueError(
                "cost_per_successful_task_threshold_usd must be >= 0; "
                f"got {cost_per_successful_task_threshold_usd}"
            )
        if window_days <= 0:
            raise ValueError(
                f"window_days must be > 0; got {window_days}"
            )
        self._threshold_usd = Decimal(
            str(cost_per_successful_task_threshold_usd)
        )
        self._window_days = window_days
        self._now = now  # tests inject a fixed reference time

    async def evaluate(
        self,
        *,
        evidence_context: EvidenceContext,
    ) -> Iterable[RecommendationCandidate]:
        now = self._now or datetime.now(timezone.utc)
        window_end = now
        window_start = now - timedelta(days=self._window_days)
        runs: list[RunRecord] = []
        successful_runs: list[RunRecord] = []
        async for run in _iterate_runs_in_window(
            evidence_context=evidence_context,
            window_start=window_start,
            window_end=window_end,
        ):
            runs.append(run)
            if run.termination_reason in SUCCESSFUL_TERMINATION_REASONS:
                successful_runs.append(run)
        return self._build_candidates(
            successful_runs=successful_runs,
            all_runs=runs,
            window_start=window_start,
            window_end=window_end,
        )

    def _build_candidates(
        self,
        *,
        successful_runs: list[RunRecord],
        all_runs: list[RunRecord],
        window_start: datetime,
        window_end: datetime,
    ) -> Iterable[RecommendationCandidate]:
        per_template_successful: dict[UUID, list[RunRecord]] = {}
        for run in successful_runs:
            per_template_successful.setdefault(
                run.agent_template_id, []
            ).append(run)
        per_template_total_count: dict[UUID, int] = {}
        for run in all_runs:
            per_template_total_count[run.agent_template_id] = (
                per_template_total_count.get(run.agent_template_id, 0) + 1
            )

        emitted: list[RecommendationCandidate] = []
        for template_id, runs_for_template in per_template_successful.items():
            n_successful = len(runs_for_template)
            if n_successful == 0:
                continue
            total_cost = sum(
                (r.total_cost_usd for r in runs_for_template),
                Decimal("0"),
            )
            mean_cost = total_cost / Decimal(n_successful)
            if mean_cost <= self._threshold_usd:
                continue
            n_total = per_template_total_count.get(template_id, n_successful)
            citation = CostOptimizationEvidenceCitation(
                run_history_record_ids=tuple(r.id for r in runs_for_template),
                cost_aggregate=CostAggregate(
                    agent_template_id=template_id,
                    mean_cost_per_successful_task_usd=mean_cost,
                    time_window_start=window_start,
                    time_window_end=window_end,
                    n_successful_runs=n_successful,
                    n_runs_total=n_total,
                ),
            )
            text = (
                f"Agent template {template_id} has cost-per-successful-task "
                f"of ${mean_cost:.4f} USD over the last {self._window_days} "
                f"days ({n_successful} successful out of {n_total} runs). "
                f"Investigate model choice and/or invocation patterns to "
                f"bring cost-per-task below "
                f"${self._threshold_usd:.4f}."
            )
            subject = f"agent_template {str(template_id)[:8]} cost-per-task"
            emitted.append(
                RecommendationCandidate(
                    category=RecommendationCategory.COST_OPTIMIZATION,
                    subject=subject,
                    text=text,
                    evidence_citations=(citation,),
                )
            )
        return emitted


async def _iterate_runs_in_window(
    *,
    evidence_context: EvidenceContext,
    window_start: datetime,
    window_end: datetime,
):
    """Yield every run within the time window for the bound tenant."""
    filters = RunListFilters(
        started_at_range=(window_start, window_end),
    )
    cursor: RunListCursor | None = None
    while True:
        page = await evidence_context.run_history_reader.list_runs_with_filters(
            tenant_context=evidence_context.tenant_context,
            filters=filters,
            cursor=cursor,
        )
        for run in page.runs:
            yield run
        if page.next_cursor is None:
            break
        cursor = page.next_cursor


__all__ = [
    "DEFAULT_COST_PER_SUCCESSFUL_TASK_THRESHOLD_USD",
    "DEFAULT_WINDOW_DAYS",
    "SUCCESSFUL_TERMINATION_REASONS",
    "CostOptimizationRule",
]
