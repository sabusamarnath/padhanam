"""Threshold evaluation — pure functions over calendar state (D153, S57).

The two Phase 2-A must-have rules, as pure functions over a tuple of
``MeetingState`` projections (D153: evaluate over the state store, not the
audit chain):

- ``detect_cancellations``: meetings whose ``status`` is cancelled and
  whose ``cancelled_at`` falls in the scan window — a recently-cancelled
  meeting the operator would want surfaced proactively.
- ``detect_conflicts``: pairs of confirmed meetings whose time ranges
  overlap — a double-booking. A standing condition over the current set,
  which is exactly why it is a state query and never was a state-change
  event (the reconciliation finding behind D153).

``evaluate`` dispatches the enabled, Phase-2A-active rules over the state
and returns the flattened matches. Restraint is structural: only the two
must-have rule types are evaluated; a deferred-shape rule carried in the
config is skipped here (it is configuration, not behaviour, until its
evaluation branch is built).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from datetime import datetime

from contexts.threshold_briefing.domain.meeting_state import MeetingState
from contexts.threshold_briefing.domain.rule_match import RuleMatch
from contexts.threshold_briefing.domain.threshold_rule import (
    ThresholdRule,
    ThresholdRuleType,
)

_CANCELLED = "cancelled"
_CONFIRMED = "confirmed"


def detect_cancellations(
    meetings: tuple[MeetingState, ...],
    *,
    rule_id: str,
    window_start: datetime,
    window_end: datetime,
) -> tuple[RuleMatch, ...]:
    """Cancelled meetings whose ``cancelled_at`` is at or after ``window_start``.

    Lower-bound only, deliberately (the S57 live-smoke finding): the
    calendar tombstone sets ``cancelled_at`` to the refresh time, and
    refresh-then-evaluate runs the refresh *inside* the scan — so a
    freshly-refreshed cancellation's ``cancelled_at`` lands a moment
    *after* the trigger's ``window_end``, and an upper bound would
    exclude exactly the cancellations the scan is meant to catch. Matching
    ``cancelled_at >= window_start`` catches currently-cancelled events
    (idempotency then briefs each once); a Google-dropped tombstone whose
    ``cancelled_at`` froze before ``window_start`` ages out. ``window_end``
    is accepted for signature symmetry but not used as an upper bound.
    """
    del window_end  # not an upper bound; see docstring
    matches: list[RuleMatch] = []
    for m in meetings:
        if m.status != _CANCELLED or m.cancelled_at is None:
            continue
        if m.cancelled_at < window_start:
            continue
        matches.append(
            RuleMatch(
                rule_id=rule_id,
                rule_type=ThresholdRuleType.MEETING_CANCELLED,
                google_event_id=m.google_event_id,
                meeting_id=m.meeting_id,
                title=m.title,
                summary=f"Meeting cancelled: {m.title}",
                cancelled_at=m.cancelled_at,
            )
        )
    return tuple(matches)


def _overlaps(a: MeetingState, b: MeetingState) -> bool:
    """True when two timed meetings overlap (half-open interval overlap)."""
    if a.start_at is None or a.end_at is None:
        return False
    if b.start_at is None or b.end_at is None:
        return False
    return a.start_at < b.end_at and b.start_at < a.end_at


def detect_conflicts(
    meetings: tuple[MeetingState, ...],
    *,
    rule_id: str,
) -> tuple[RuleMatch, ...]:
    """Pairs of confirmed meetings whose time ranges overlap (double-booking).

    Each conflicting pair yields one match; the primary meeting is the
    earlier-starting one (stable so the crossing identity is deterministic)
    and the partner is the later. Pairs are de-duplicated — a set of N
    mutually-overlapping meetings yields the C(N,2) distinct pairs once
    each, not twice.
    """
    confirmed = [
        m
        for m in meetings
        if m.status == _CONFIRMED and m.start_at is not None and m.end_at is not None
    ]
    confirmed.sort(key=lambda m: (m.start_at, m.google_event_id))  # type: ignore[arg-type,return-value]
    matches: list[RuleMatch] = []
    for i in range(len(confirmed)):
        for j in range(i + 1, len(confirmed)):
            a, b = confirmed[i], confirmed[j]
            if not _overlaps(a, b):
                continue
            matches.append(
                RuleMatch(
                    rule_id=rule_id,
                    rule_type=ThresholdRuleType.MEETING_CONFLICT,
                    google_event_id=a.google_event_id,
                    meeting_id=a.meeting_id,
                    title=a.title,
                    summary=f"Double-booking: {a.title} overlaps {b.title}",
                    partner_event_id=b.google_event_id,
                    partner_title=b.title,
                )
            )
    return tuple(matches)


def evaluate(
    rules: tuple[ThresholdRule, ...],
    meetings: tuple[MeetingState, ...],
    *,
    window_start: datetime,
    window_end: datetime,
) -> tuple[RuleMatch, ...]:
    """Run the enabled Phase-2A-active rules over the state; flatten matches.

    Deferred-shape rules (anything outside the two must-have types) are
    skipped — restraint is enforced here, not assumed: the evaluator never
    fires a rule type whose evaluation branch is not built.
    """
    matches: list[RuleMatch] = []
    for rule in rules:
        if not rule.is_phase_2a_active:
            continue
        if rule.rule_type is ThresholdRuleType.MEETING_CANCELLED:
            matches.extend(
                detect_cancellations(
                    meetings,
                    rule_id=rule.rule_id,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
        elif rule.rule_type is ThresholdRuleType.MEETING_CONFLICT:
            matches.extend(detect_conflicts(meetings, rule_id=rule.rule_id))
    return tuple(matches)


__all__ = ["detect_cancellations", "detect_conflicts", "evaluate"]
