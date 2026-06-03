"""ThresholdRule — the configured-rules schema (D153, S57).

A threshold is an operator-configurable rule the ThresholdEvaluator
matches against the calendar state at each scan. The schema supports the
deferred rule shapes (so adding one at dogfooding is config, not code)
but Phase 2-A populates only the two calendar must-haves
(``MEETING_CANCELLED``, ``MEETING_CONFLICT``).

The governing discipline is restraint against the reverse Kano category
(D153): for a platform-*initiated* surface, a low-signal threshold trains
the user to dismiss briefings and collapses the surface's value, so the
active set is deliberately narrow. The deferred shapes are enumerated
here (the schema knows them) but their evaluation is not built at Phase
2-A — ``MEETING_MOVED`` needs prior-vs-current start retention (a
calendar-substrate touch deferred to the dogfooding gate, D154); the
email/topic/synthesis shapes activate when their substrates carry
thresholds.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ThresholdRuleType(StrEnum):
    """The kinds of threshold a rule can match (D153).

    The two Phase 2-A must-haves are ``MEETING_CANCELLED`` and
    ``MEETING_CONFLICT``. The remaining values are the deferred shapes
    the schema supports but Phase 2-A does not evaluate — listed so the
    closed set is explicit and a dogfooding-time activation is a config
    change plus an evaluation branch, not a schema change.
    """

    # --- Phase 2-A active (calendar must-haves) ---
    MEETING_CANCELLED = "meeting_cancelled"
    MEETING_CONFLICT = "meeting_conflict"
    # --- deferred (supported by the schema, not evaluated at Phase 2-A) ---
    MEETING_MOVED = "meeting_moved"
    EMAIL_FROM_SENDER = "email_from_sender"
    EMAIL_TOPIC = "email_topic"
    EXTERNALLY_INITIATED_MEETING = "externally_initiated_meeting"
    CROSS_SOURCE_SYNTHESIS = "cross_source_synthesis"


# The rule types ThresholdEvaluator actually evaluates at Phase 2-A. A
# rule whose type is outside this set is accepted by the schema but
# skipped at evaluation (it is a deferred shape carried as configuration).
PHASE_2A_ACTIVE_RULE_TYPES: frozenset[ThresholdRuleType] = frozenset(
    {ThresholdRuleType.MEETING_CANCELLED, ThresholdRuleType.MEETING_CONFLICT}
)


@dataclass(frozen=True)
class ThresholdRule:
    """One operator-configured threshold rule (D153).

    ``rule_id`` is the stable identifier the crossing references (it
    seeds the THRESHOLD_CROSSED idempotency key). ``rule_type`` selects
    the evaluation branch. ``enabled`` gates the rule. ``params`` is the
    open per-type parameter slot (empty for the two parameterless Phase
    2-A must-haves; the deferred shapes use it for sender addresses,
    topic terms, etc.) — the open-dict discipline mirrors
    TriggerContext.metadata so adding a parameterised rule shape does not
    change this domain type.
    """

    rule_id: str
    rule_type: ThresholdRuleType
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def is_phase_2a_active(self) -> bool:
        """True when this rule is enabled and of a Phase 2-A evaluated type."""
        return self.enabled and self.rule_type in PHASE_2A_ACTIVE_RULE_TYPES


__all__ = [
    "PHASE_2A_ACTIVE_RULE_TYPES",
    "ThresholdRule",
    "ThresholdRuleType",
]
