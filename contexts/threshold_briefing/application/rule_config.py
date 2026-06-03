"""Configured-rules provider (D153, S57).

The Phase 2-A configured-rule set: the two calendar must-haves populated,
the deferred shapes supported-but-empty. Restraint against the reverse
Kano category is encoded as the *contents* of this set, not as a missing
capability — the schema (``ThresholdRule``/``ThresholdRuleType``) knows
the deferred shapes; this provider simply does not enable them at Phase
2-A. Adding one at dogfooding is a change here (enable + parameterise) plus
its evaluation branch, not a schema change.

At Phase 2-A the set is static. The forward shape is operator-configured
rows (a per-tenant rules store) the composition root loads; that lands
when dogfooding produces the first rule-tuning signal — deferred per the
two-threshold rule, not built against zero configuration demand.

Framework-free per D16 — stdlib plus the threshold domain only.
"""

from __future__ import annotations

from contexts.threshold_briefing.domain.threshold_rule import (
    ThresholdRule,
    ThresholdRuleType,
)

# The two Phase 2-A calendar must-haves. rule_id values are stable
# identifiers the crossing references (they seed the THRESHOLD_CROSSED
# idempotency key); both are parameterless (empty params).
_MEETING_CANCELLED = ThresholdRule(
    rule_id="calendar.meeting_cancelled",
    rule_type=ThresholdRuleType.MEETING_CANCELLED,
    enabled=True,
)
_MEETING_CONFLICT = ThresholdRule(
    rule_id="calendar.meeting_conflict",
    rule_type=ThresholdRuleType.MEETING_CONFLICT,
    enabled=True,
)


def phase_2a_rules() -> tuple[ThresholdRule, ...]:
    """Return the Phase 2-A configured-rule set (the two calendar must-haves).

    Deferred shapes (meeting-moved, email-sender, topic,
    externally-initiated-meeting, cross-source-synthesis) are intentionally
    absent — supported by the schema, not enabled here, per D153's restraint
    discipline. They are config-tuned at dogfooding.
    """
    return (_MEETING_CANCELLED, _MEETING_CONFLICT)


__all__ = ["phase_2a_rules"]
