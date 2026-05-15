"""Optimization application layer (D108, D111).

Engine + lifecycle + read use cases:

- ``run_optimization`` (engine) at ``run_optimization.py``.
- ``acknowledge_recommendation`` / ``apply_recommendation`` /
  ``reject_recommendation`` lifecycle transitions.
- ``get_recommendation`` / ``list_recommendations`` reads.
- ``get_optimization_run`` / ``list_optimization_runs`` reads.

Supporting modules:

- ``evidence_context.py`` wraps the four producer-context reader ports.
- ``rules/`` ships the four default RecommendationRule implementations
  (placement deviation from the brief recorded at the package
  docstring; the rules orchestrate over producer ports so they live
  at application not domain per hexagonal layering).
- ``audit_events.py`` drafts the seven optimization-context audit
  events (run start/complete/fail; recommendation generate/ack/
  apply/reject).
- ``cursors.py`` codecs for the two list shapes.

Errors raised at the application layer:

- ``RecommendationNotFoundError`` — get/transition on missing or
  cross-tenant recommendation.
- ``TransitionNotPermittedError`` — transition target violates the
  RecommendationStatus.can_transition map.
"""

from contexts.optimization.application._transition_helpers import (
    RecommendationNotFoundError,
    TransitionNotPermittedError,
    TransitionResult,
)
from contexts.optimization.application.acknowledge_recommendation import (
    acknowledge_recommendation,
)
from contexts.optimization.application.apply_recommendation import (
    apply_recommendation,
)
from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.application.get_optimization_run import (
    get_optimization_run,
)
from contexts.optimization.application.get_recommendation import (
    get_recommendation,
)
from contexts.optimization.application.list_optimization_runs import (
    list_optimization_runs,
)
from contexts.optimization.application.list_recommendations import (
    list_recommendations,
)
from contexts.optimization.application.reject_recommendation import (
    reject_recommendation,
)
from contexts.optimization.application.run_optimization import (
    RunOptimizationResult,
    run_optimization,
)

__all__ = [
    "EvidenceContext",
    "RecommendationNotFoundError",
    "RunOptimizationResult",
    "TransitionNotPermittedError",
    "TransitionResult",
    "acknowledge_recommendation",
    "apply_recommendation",
    "get_optimization_run",
    "get_recommendation",
    "list_optimization_runs",
    "list_recommendations",
    "reject_recommendation",
    "run_optimization",
]
