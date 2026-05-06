"""Regression report domain entities (D58, S18).

The user-facing output of the eval harness: a comparison between two
runs of a scoring sheet against the same interaction set. Per-criterion
success-rate deltas plus aggregate metrics (overall success rate and
cost-per-task), serialised through render functions in the application
layer.

Three frozen dataclasses, all framework-free per D16:

  - ``CriterionDelta`` — per-criterion success-rate delta. Joined
    across two revisions on criterion ``name`` (criterion ids differ
    across revisions because each revision creates fresh criterion
    rows). Carries baseline_count and candidate_count so consumers
    can distinguish "no data" (zero count) from "all failures"
    (non-zero count, zero successful) when reading the rate.

  - ``AggregateMetrics`` — overall success-rate and cost-per-task
    metrics for the whole comparison. Cost-per-task lives at this
    aggregate level only; per-criterion cost is P11 territory (a
    single inference call produces one trace_id shared across every
    criterion that scores the same model output, so cost is
    structurally per-trace and not per-criterion).

  - ``RegressionReport`` — the top-level container. Carries
    baseline and candidate revision ids, the interaction set id,
    the per-criterion deltas, the aggregate metrics, and a
    ``generated_at`` timestamp.

Build-time refinement from S18 brief (per the D54 / S15 / S16
methodology pattern: framing prompts are recommendations subject to
structural-honesty review at build):

  - Brief named ``baseline_run_id`` / ``candidate_run_id`` on
    RegressionReport. Refined to ``baseline_revision_id`` /
    ``candidate_revision_id`` (UUIDs) because the data model has
    no "run" entity — the closest concept is a (revision,
    interaction_set, tenant) tuple, and the revision id is the
    user-facing handle the CLI reads. ``baseline_run_id`` /
    ``candidate_run_id`` would have been a free-form string with
    no structural anchor.

  - Brief placed ``baseline_cost_per_task`` / ``candidate_cost_per_task``
    / ``cost_delta`` on CriterionDelta. The brief's own out-of-scope
    section names per-criterion cost as P11 territory; the existing
    cost_per_successful_task use case (S17b) returns an aggregate,
    not per-criterion data, because trace_ids are shared across
    criteria scoring the same model output. Cost lives only on
    AggregateMetrics; CriterionDelta stays focused on success-rate.
    P11's recommendation engine adds per-criterion cost when its
    consumer model justifies the extra query work.

Both refinements are documented in the S18 reflection paragraph and
in D58's text.

Score interpretation per D55: success is criterion-level, derived
from the criterion's ``levels`` jsonb where the matched label's
``is_success`` flag is True. The comparison use case at
``application/regression_compare.py`` performs the matching and
filtering; this domain shape carries the computed rates only.

Float for success rates (0.0-1.0); Decimal for costs (D49 monetary
precision); int for counts. Mixed numeric types reflect each
quantity's natural precision: rates are ratios, costs are money,
counts are exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class CriterionDelta:
    """Per-criterion success-rate delta between two runs.

    ``criterion_name`` is the join key across revisions (criterion
    ids differ because each revision owns its own criterion rows).
    ``baseline_count`` and ``candidate_count`` are the total
    rubric_application counts for this criterion in each run; a
    zero count signals "no data" rather than "all failures",
    which the success_rate alone cannot distinguish.

    ``delta`` is ``candidate_success_rate - baseline_success_rate``
    when both counts are non-zero. When either side has zero
    rubric_applications for the criterion (e.g., the criterion
    name was renamed across revisions), the rate on that side is
    0.0 and ``delta`` reflects the structural absence; consumers
    read both ``baseline_count`` and ``candidate_count`` to
    interpret the value honestly.
    """

    criterion_name: str
    baseline_success_rate: float
    candidate_success_rate: float
    delta: float
    baseline_count: int
    candidate_count: int


@dataclass(frozen=True)
class AggregateMetrics:
    """Overall metrics across the comparison.

    Cost-per-task (USD) is the eval harness's substrate metric per
    D8 and the recommendation differentiator's data per D9. Success
    rate is the criterion-agnostic rollup (total successful
    rubric_applications / total rubric_applications), not weighted
    by criterion.

    ``overall_success_rate_delta`` is candidate - baseline.
    ``overall_cost_per_task_delta`` is candidate - baseline (USD,
    Decimal). Negative means the candidate is cheaper; positive
    means the candidate costs more per task.
    """

    total_baseline_applications: int
    total_candidate_applications: int
    total_baseline_successful: int
    total_candidate_successful: int
    overall_baseline_success_rate: float
    overall_candidate_success_rate: float
    overall_success_rate_delta: float
    baseline_cost_per_task_usd: Decimal
    candidate_cost_per_task_usd: Decimal
    overall_cost_per_task_delta_usd: Decimal


@dataclass(frozen=True)
class RegressionReport:
    """Single-baseline regression report (D58).

    Multi-baseline tracking (run history with trend lines) defers
    to P11 territory. The single-baseline shape is forward-
    compatible: a multi-baseline report is a list of single-
    baseline reports plus aggregation, so the data model extends
    without restructuring.
    """

    baseline_revision_id: UUID
    candidate_revision_id: UUID
    interaction_set_id: UUID
    per_criterion_deltas: tuple[CriterionDelta, ...]
    aggregate_metrics: AggregateMetrics
    generated_at: datetime
