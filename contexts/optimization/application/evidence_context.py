"""EvidenceContext — wraps producer-context reader ports (D111 cmt 5).

The optimization engine constructs an ``EvidenceContext`` at
invocation time, injecting the four reader ports defined at the
producer contexts (EvaluationRunReader and GoldSetReader at
retrieval_evaluation, RunHistoryReader at run_history, AuditEventReader
at audit). Each rule's ``evaluate`` method takes the context and
calls the readers it needs.

The frozen dataclass shape is the interface contract: rules import
this class and call attribute-named readers; the engine constructs
instances with concrete adapter implementations at composition time
(commit 5 wires the four readers through the consumer-port-plus-
wiring-adapter pattern at fifteenth through eighteenth instances).

Phase 1 active reader usage:

- ``evaluation_run_reader`` — retrieval_strategy rule iterates
  completed runs for the tenant and inspects per-strategy
  aggregates.
- ``run_history_reader`` — cost_optimization rule iterates
  successful runs over a time window and aggregates
  cost-per-successful-task by ``agent_template_id``.
- ``gold_set_reader`` — passive citation reference (the
  retrieval_strategy rule's citation includes a ``gold_set_id``
  drawn from the evaluation run; the reader is wired for symmetry
  with the run-history pattern and for Phase 2 use where richer
  gold-set context may be cited).
- ``audit_event_reader`` — passive citation reference (no Phase 1
  rule actively queries audit events; the reader is wired so
  forward-compatible audit-driven recommendations have the surface
  ready when the substrate demands it per D108).

Application code can import vendor SDKs and Pydantic; this layer
is the legitimate seam where consumer ports meet producer concrete
implementations.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.audit.ports.reader import AuditEventReader
from contexts.matcher_evaluation.ports.matcher_quality_run_reader import (
    MatcherQualityRunReader,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunReader,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.run_history.ports.reader import RunHistoryReader
from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class EvidenceContext:
    """Wraps the four reader ports a RecommendationRule may consume.

    Constructed per-invocation by the engine with the tenant context
    bound at the outer boundary. Rules access the readers via the
    named attributes; concrete adapter implementations are wired at
    the composition root.
    """

    tenant_context: TenantContext
    evaluation_run_reader: EvaluationRunReader
    run_history_reader: RunHistoryReader
    gold_set_reader: GoldSetReader
    audit_event_reader: AuditEventReader
    # D185/S91: the matcher-quality producer's reader (the first non-inference
    # evidence source). Optional — a tenant or test without the matcher producer
    # is a substrate gap the matcher rule reports, mirroring the Phase-2 rules.
    matcher_quality_run_reader: MatcherQualityRunReader | None = None


__all__ = ["EvidenceContext"]
