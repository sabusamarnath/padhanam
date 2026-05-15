"""contexts/optimization/ — the P11 optimization engine (D108, D111).

The optimization layer consumes producer-context evidence
(retrieval_evaluation, run_history, audit, retrieval_evaluation for
gold-set citations) through consumer-defined reader ports and
produces recommendation output. Hexagonal layout per D16: domain
value objects and aggregates, application use cases and ports,
Postgres outbound adapters at the adapters tree.

D111 commits two aggregate roots: ``OptimizationRun`` (engine
invocation lifecycle) and ``Recommendation`` (per-output aggregate
with append-only content and mutable status). Pluggable abstractions
(``RecommendationRule`` and ``MetricCalculator``) operationalise the
vendor-flexibility principle at ``charter/principles.md``.
"""
