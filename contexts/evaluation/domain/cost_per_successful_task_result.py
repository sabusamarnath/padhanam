"""CostPerSuccessfulTaskResult — output value object for the
cost-per-successful-task use case (D8, S17b).

Carries four numbers:

  - ``total_cost_usd``: sum of cost across the unique trace_ids the
    successful rubric_applications produced. Costs are deduplicated
    per trace_id (one inference call → one cost), even when multiple
    criteria score against the same model output.

  - ``successful_count``: count of rubric_applications whose
    ``automated_score`` matched a criterion level marked
    ``is_success=True``.

  - ``cost_per_task_usd``: ``total_cost_usd / successful_count`` when
    ``successful_count > 0``; ``Decimal("0")`` otherwise. The
    consumer reads this alongside ``excluded_count`` to discount the
    value when most successful applications could not be costed.

  - ``excluded_count``: count of successful rubric_applications that
    did not contribute to the cost rollup (no ``trace_id``, or
    ``trace_id`` present but Langfuse returned no cost data, or the
    cross-tenant filter discarded the trace). The diagnostic the
    reflection prompt 3 in the S17b session log discusses: "low
    cost-per-task because most data was excluded" is a different
    failure mode from "low cost-per-task with full coverage".

Decimal-typed cost values per D49's monetary-precision posture; int
counts; frozen dataclass for the same reason every other domain
value object is frozen (D16 — immutable, framework-free).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostPerSuccessfulTaskResult:
    total_cost_usd: Decimal
    successful_count: int
    cost_per_task_usd: Decimal
    excluded_count: int
