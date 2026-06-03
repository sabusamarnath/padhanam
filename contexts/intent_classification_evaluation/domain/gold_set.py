"""Intent-classification gold-set domain shape (D137, S48b).

Option B simplification: gold-set is loaded from a YAML fixture at
``tests/fixtures/intent_classification/gold_set.yaml`` rather than
persisted with the P11 retrieval-evaluation gold-set's revision-
with-hash-chain lifecycle (D109). The fixture is the canonical
source until the multi-tenant gold-set authoring trigger activates
the revision-lifecycle implementation per D137 alternative (c).

``IntentClassificationGoldSet`` carries the in-memory shape; the
fixture-loader at ``contexts.intent_classification_evaluation.
adapters.outbound.fixture`` constructs an instance from YAML.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


# The intent classes the substrate evaluates. Four intent surfaces at
# S52: the manual entry cell (four classes mirroring IntentType at
# contexts/messaging/domain/intent.py); the audit-conversation cell
# (six classes mirroring AuditIntentType at
# contexts/audit_conversation/domain/intent.py); the dispatch
# classifier (three real cell identifiers from D140 plus the
# dispatch_clarification sentinel); the mirror-conversation cell
# (six concrete intents plus the unclear fallback, mirroring
# MirrorIntentType at contexts/mirror_conversation/domain/intent.py
# which lands at S52 commit 8). Each surface's classes coexist in
# this tuple per the D137 substrate parameterisation activation
# trigger (deferred-decisions entry): tuple extension is the cheapest
# possible adaptation; the parameterisation refactor triggers when
# the tuple-extension pattern stops carrying the cumulative weight.
INTENT_CLASSES: tuple[str, ...] = (
    # Manual entry cell surface (S46, four classes).
    "create_case",
    "add_data_point",
    "revise_data_point",
    "unclear",
    # Audit-conversation surface (S51, six classes).
    "find_by_case",
    "find_by_date_range",
    "find_by_actor",
    "find_by_event_type",
    "find_by_combination",
    "unclear_audit",
    # Dispatch classifier surface (S52 D140, four classes; calendar_conversation
    # added at S55b-2 D140 four-way extension).
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
    "dispatch_clarification",
    "calendar_conversation",
    # Mirror-conversation surface (S52 commit 8, seven classes).
    "show_case",
    "list_cases",
    "show_data_point",
    "drill_down_to_child",
    "show_parent",
    "show_siblings",
    "unclear_mirror",
    # Calendar-conversation surface (S55b-1, five classes). find_by_date_range
    # is shared with the audit surface (same string) so it is not repeated.
    "find_by_attendee",
    "find_by_title",
    "find_next_meeting",
    "unclear_calendar",
)


@dataclass(frozen=True)
class IntentClassificationGoldSetEntry:
    """A single (input, expected) pair in the gold set.

    ``input_phrasing`` is the operator-shaped natural-language input
    the model classifies. ``expected_intent_class`` is the canonical
    correct classification (one of ``INTENT_CLASSES``).
    ``expected_confidence_minimum`` is optional; when set, a result
    is considered correct only if classification matches AND
    confidence is at or above this threshold.
    """

    input_phrasing: str
    expected_intent_class: str
    expected_confidence_minimum: float | None = None

    def __post_init__(self) -> None:
        if not self.input_phrasing or not self.input_phrasing.strip():
            raise ValueError(
                "IntentClassificationGoldSetEntry.input_phrasing must be non-empty"
            )
        if self.expected_intent_class not in INTENT_CLASSES:
            raise ValueError(
                "IntentClassificationGoldSetEntry.expected_intent_class must be "
                f"one of {INTENT_CLASSES}; got {self.expected_intent_class!r}"
            )
        if self.expected_confidence_minimum is not None and not (
            0.0 <= self.expected_confidence_minimum <= 1.0
        ):
            raise ValueError(
                "IntentClassificationGoldSetEntry.expected_confidence_minimum "
                f"must be in [0.0, 1.0]; got {self.expected_confidence_minimum!r}"
            )


# Intent surfaces the substrate evaluates. S46 introduced the
# manual_entry surface; S51 added the audit_conversation surface; S52
# adds dispatch_classifier (the meta-classifier from D140) and
# mirror_conversation (the second P14 implementer). Four surfaces at
# P14 close. The tuple-extension pattern still carries the load
# operationally; the parameterisation refactor activates at the
# deferred-decisions trigger when per-surface metric calculation, per-
# surface latency budget, or per-surface model-tier selection
# diverges across surfaces.
INTENT_SURFACES: tuple[str, ...] = (
    "manual_entry",
    "audit_conversation",
    "dispatch_classifier",
    "mirror_conversation",
    "calendar_conversation",
)
DEFAULT_INTENT_SURFACE: str = "manual_entry"


@dataclass(frozen=True)
class IntentClassificationGoldSet:
    """The in-memory shape of a gold set.

    ``name`` is the gold-set's identifier (e.g. ``phase_2_a_default``);
    references in ``EvaluationRun.gold_set_name`` carry this value.
    ``entries`` is the ordered tuple of entries the runner iterates.
    ``intent_surface`` selects which prompt+schema+result-key the
    runner uses for this gold set; defaults to ``manual_entry`` for
    backward compatibility with the S48b fixture.
    """

    name: str
    entries: tuple[IntentClassificationGoldSetEntry, ...]
    intent_surface: str = DEFAULT_INTENT_SURFACE

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("IntentClassificationGoldSet.name must be non-empty")
        if not self.entries:
            raise ValueError(
                "IntentClassificationGoldSet.entries must be non-empty"
            )
        if self.intent_surface not in INTENT_SURFACES:
            raise ValueError(
                "IntentClassificationGoldSet.intent_surface must be one of "
                f"{INTENT_SURFACES}; got {self.intent_surface!r}"
            )


__all__ = [
    "DEFAULT_INTENT_SURFACE",
    "INTENT_CLASSES",
    "INTENT_SURFACES",
    "IntentClassificationGoldSet",
    "IntentClassificationGoldSetEntry",
]
