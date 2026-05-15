"""Default RecommendationRule implementations (D111 cmt 5).

Four rules covering the four D108 categories:

- ``retrieval_strategy_rule.py`` — pairwise recall@3 deltas between
  executing strategies; triggers when any delta exceeds 0.15 absolute.
- ``cost_optimization_rule.py`` — cost-per-successful-task aggregated
  by ``agent_template_id`` over a 14-day window; triggers when any
  template exceeds the threshold (default $0.10).
- ``model_choice_rule.py`` — Phase 1 zero; raises ``SubstrateGapError``
  naming scoring-sheet evaluation runs as the missing input.
- ``prompt_revision_rule.py`` — Phase 1 zero; same shape as
  model_choice with prompt-failure substrate text.

Each rule implementation is the consumer of the producer-context
reader ports the engine injects via the ``EvidenceContext`` at
``contexts/optimization/application/evidence_context.py``.

Placement note: the rules live at the application layer (not domain)
because they orchestrate over producer-context reader ports.
Architectural intent of hexagonal: domain is the language of the
domain; application is orchestration. The S41 brief framed
``contexts/optimization/domain/rules/`` but the rules' actual shape
(import producer ports, consume the application-layer
EvidenceContext, compute aggregates) is application-layer
orchestration. The brief deviation is recorded at the S41 session
log entry.
"""

from contexts.optimization.application.rules.cost_optimization_rule import (
    CostOptimizationRule,
)
from contexts.optimization.application.rules.model_choice_rule import (
    ModelChoiceRule,
)
from contexts.optimization.application.rules.prompt_revision_rule import (
    PromptRevisionRule,
)
from contexts.optimization.application.rules.retrieval_strategy_rule import (
    RetrievalStrategyRule,
)


def default_rules(
    *,
    recall_at_k_delta_threshold: float = 0.15,
    cost_per_successful_task_threshold_usd: float = 0.10,
    cost_window_days: int = 14,
) -> tuple:
    """Construct the four default rules with the Phase 1 thresholds.

    Returns the tuple in registration order: retrieval_strategy,
    cost_optimization, model_choice (zero), prompt_revision (zero).
    Composition roots call this and pass the result to the engine.
    """
    return (
        RetrievalStrategyRule(
            recall_at_k_delta_threshold=recall_at_k_delta_threshold,
        ),
        CostOptimizationRule(
            cost_per_successful_task_threshold_usd=(
                cost_per_successful_task_threshold_usd
            ),
            window_days=cost_window_days,
        ),
        ModelChoiceRule(),
        PromptRevisionRule(),
    )


__all__ = [
    "CostOptimizationRule",
    "ModelChoiceRule",
    "PromptRevisionRule",
    "RetrievalStrategyRule",
    "default_rules",
]
