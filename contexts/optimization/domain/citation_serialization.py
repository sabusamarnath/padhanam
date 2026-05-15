"""Discriminated-union citation serialization (D111 commitment 7).

Converts ``EvidenceCitation`` union variants to JSON-compatible
dicts (for JSONB storage and audit-event payloads) and back. The
discriminator field is ``category``; each variant's payload follows
the shape committed at D111 commitment 7.

The audit context's event payload requires JSON-serialisable dicts;
the Postgres adapter at commit 6 reads from JSONB columns and
reconstructs domain objects. Centralising the serialisation here
gives both callers one canonical shape.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.evidence_citation import (
    CaveatAnnotation,
    CostAggregate,
    CostOptimizationEvidenceCitation,
    EvidenceCitation,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)


def citation_to_dict(citation: EvidenceCitation) -> dict[str, Any]:
    """Serialise an EvidenceCitation variant to a JSON-compatible dict."""
    if isinstance(citation, RetrievalStrategyEvidenceCitation):
        return {
            "category": RecommendationCategory.RETRIEVAL_STRATEGY.value,
            "evaluation_run_id": str(citation.evaluation_run_id),
            "gold_set_id": str(citation.gold_set_id),
            "comparison": {
                "strategy_a": citation.comparison.strategy_a,
                "strategy_b": citation.comparison.strategy_b,
                "recall_at_k_delta": {
                    str(k): float(v)
                    for k, v in citation.comparison.recall_at_k_delta.items()
                },
                "precision_at_k_delta": {
                    str(k): float(v)
                    for k, v in citation.comparison.precision_at_k_delta.items()
                },
            },
            "caveats": [
                {
                    "strategy_id": c.strategy_id,
                    "state": c.state,
                    "caveat_code": c.caveat_code,
                }
                for c in citation.caveats
            ],
        }
    if isinstance(citation, CostOptimizationEvidenceCitation):
        return {
            "category": RecommendationCategory.COST_OPTIMIZATION.value,
            "run_history_record_ids": [
                str(rid) for rid in citation.run_history_record_ids
            ],
            "cost_aggregate": {
                "agent_template_id": str(
                    citation.cost_aggregate.agent_template_id
                ),
                "mean_cost_per_successful_task_usd": str(
                    citation.cost_aggregate.mean_cost_per_successful_task_usd
                ),
                "time_window_start": (
                    citation.cost_aggregate.time_window_start.isoformat()
                ),
                "time_window_end": (
                    citation.cost_aggregate.time_window_end.isoformat()
                ),
                "n_successful_runs": citation.cost_aggregate.n_successful_runs,
                "n_runs_total": citation.cost_aggregate.n_runs_total,
            },
        }
    raise TypeError(
        f"unsupported citation type: {type(citation).__name__}"
    )


def citations_to_payload(
    citations: tuple[EvidenceCitation, ...],
) -> list[dict[str, Any]]:
    """Serialise a tuple of citations to a JSON-array payload."""
    return [citation_to_dict(c) for c in citations]


def citation_from_dict(payload: Mapping[str, Any]) -> EvidenceCitation:
    """Deserialise a citation payload back to a domain object.

    Raises ``ValueError`` on unknown category, missing fields, or
    type errors. The Postgres adapter reconstructs domain citations
    on read using this helper.
    """
    category_raw = payload.get("category")
    if category_raw == RecommendationCategory.RETRIEVAL_STRATEGY.value:
        return _retrieval_strategy_from_dict(payload)
    if category_raw == RecommendationCategory.COST_OPTIMIZATION.value:
        return _cost_optimization_from_dict(payload)
    raise ValueError(f"unknown citation category: {category_raw!r}")


def citations_from_payload(
    payload: list[Mapping[str, Any]],
) -> tuple[EvidenceCitation, ...]:
    """Deserialise an array payload to a tuple of citations."""
    return tuple(citation_from_dict(p) for p in payload)


def _retrieval_strategy_from_dict(
    payload: Mapping[str, Any],
) -> RetrievalStrategyEvidenceCitation:
    comparison_raw = payload["comparison"]
    comparison = StrategyComparison(
        strategy_a=comparison_raw["strategy_a"],
        strategy_b=comparison_raw["strategy_b"],
        recall_at_k_delta={
            int(k): float(v)
            for k, v in comparison_raw["recall_at_k_delta"].items()
        },
        precision_at_k_delta={
            int(k): float(v)
            for k, v in comparison_raw["precision_at_k_delta"].items()
        },
    )
    caveats = tuple(
        CaveatAnnotation(
            strategy_id=c["strategy_id"],
            state=c["state"],
            caveat_code=c["caveat_code"],
        )
        for c in payload.get("caveats", [])
    )
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=UUID(payload["evaluation_run_id"]),
        gold_set_id=UUID(payload["gold_set_id"]),
        comparison=comparison,
        caveats=caveats,
    )


def _cost_optimization_from_dict(
    payload: Mapping[str, Any],
) -> CostOptimizationEvidenceCitation:
    aggregate_raw = payload["cost_aggregate"]
    aggregate = CostAggregate(
        agent_template_id=UUID(aggregate_raw["agent_template_id"]),
        mean_cost_per_successful_task_usd=Decimal(
            aggregate_raw["mean_cost_per_successful_task_usd"]
        ),
        time_window_start=datetime.fromisoformat(
            aggregate_raw["time_window_start"]
        ),
        time_window_end=datetime.fromisoformat(
            aggregate_raw["time_window_end"]
        ),
        n_successful_runs=int(aggregate_raw["n_successful_runs"]),
        n_runs_total=int(aggregate_raw["n_runs_total"]),
    )
    return CostOptimizationEvidenceCitation(
        run_history_record_ids=tuple(
            UUID(rid) for rid in payload["run_history_record_ids"]
        ),
        cost_aggregate=aggregate,
    )


def skipped_categories_to_dict(
    skipped: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    """Serialise OptimizationRun.skipped_categories to a JSON dict."""
    return {
        category: {
            "reason_code": reason.reason_code,
            "reason_text": reason.reason_text,
        }
        for category, reason in skipped.items()
    }


__all__ = [
    "citation_from_dict",
    "citation_to_dict",
    "citations_from_payload",
    "citations_to_payload",
    "skipped_categories_to_dict",
]
