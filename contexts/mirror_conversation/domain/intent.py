"""Mirror-conversation intent value objects (P14, S52, D137).

Six concrete mirror-conversation intents plus the UnclearMirrorIntent
fallback the cell extracts from the operator's inbound message via the
structured-output port at D130.

The six concrete intents split into three *absolute* variants (which
resolve their references directly against portfolio state) and three
*relative* variants (which resolve against the conversation's current
focus extracted from prior outbound's ``cell_payload`` per D141):

- Absolute: ShowCase, ListCases, ShowDataPoint.
- Relative: DrillDownToChild, ShowParent, ShowSiblings.
- Fallback: UnclearMirrorIntent.

The intent classes follow the same shape as the manual entry cell's
intent surface (S46) and the audit-conversation surface (S51): each
intent class is a frozen dataclass with __post_init__ invariants;
``parse_mirror_intent`` discriminates on the ``intent_class`` field
and returns a typed instance.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MirrorIntentType(str, Enum):
    """Mirror-conversation intent kinds, mirroring the YAML schema."""

    SHOW_CASE = "show_case"
    LIST_CASES = "list_cases"
    SHOW_DATA_POINT = "show_data_point"
    DRILL_DOWN_TO_CHILD = "drill_down_to_child"
    SHOW_PARENT = "show_parent"
    SHOW_SIBLINGS = "show_siblings"
    UNCLEAR_MIRROR = "unclear_mirror"


# ----------------------------------------------- absolute intents


@dataclass(frozen=True)
class ShowCase:
    """Show the operator's case named by a natural-language reference."""

    case_reference: str

    def __post_init__(self) -> None:
        if not self.case_reference or not self.case_reference.strip():
            raise ValueError("ShowCase.case_reference must be non-empty")


@dataclass(frozen=True)
class ListCases:
    """List all the operator's cases (no reference; absolute)."""


@dataclass(frozen=True)
class ShowDataPoint:
    """Show a specific data point by natural-language reference.

    ``case_reference`` is optional: when present, narrows the data-point
    search to one case; when absent, the cell searches across all cases.
    """

    data_point_reference: str
    case_reference: str = ""

    def __post_init__(self) -> None:
        if (
            not self.data_point_reference
            or not self.data_point_reference.strip()
        ):
            raise ValueError(
                "ShowDataPoint.data_point_reference must be non-empty"
            )


# ----------------------------------------------- relative intents


@dataclass(frozen=True)
class DrillDownToChild:
    """Drill from the current focus artefact to one of its children.

    Resolves against the conversation's current focus (extracted from
    the prior mirror-conversation outbound's cell_payload per D141);
    ``child_reference`` names the target child within the focus's
    scope. When no prior focus exists, the cell routes through D139 to
    D134 clarification per the no-prior-focus edge case.
    """

    child_reference: str

    def __post_init__(self) -> None:
        if not self.child_reference or not self.child_reference.strip():
            raise ValueError(
                "DrillDownToChild.child_reference must be non-empty"
            )


@dataclass(frozen=True)
class ShowParent:
    """Show the parent of the current focus artefact (relative; no args)."""


@dataclass(frozen=True)
class ShowSiblings:
    """Show the siblings of the current focus artefact (relative; no args)."""


@dataclass(frozen=True)
class UnclearMirrorIntent:
    """Fallback for classification failures.

    Carries the clarification text the model produced so the cell can
    render an operator-facing question; mirrors the audit-conversation
    UnclearAuditIntent shape.
    """

    clarification: str

    def __post_init__(self) -> None:
        if not self.clarification or not self.clarification.strip():
            raise ValueError(
                "UnclearMirrorIntent.clarification must be non-empty"
            )


MirrorIntent = (
    ShowCase
    | ListCases
    | ShowDataPoint
    | DrillDownToChild
    | ShowParent
    | ShowSiblings
    | UnclearMirrorIntent
)


_RELATIVE_TYPES = {
    MirrorIntentType.DRILL_DOWN_TO_CHILD,
    MirrorIntentType.SHOW_PARENT,
    MirrorIntentType.SHOW_SIBLINGS,
}


def is_relative(intent: MirrorIntent) -> bool:
    """True when the intent depends on prior conversation focus to resolve."""
    return mirror_intent_type_of(intent) in {t.value for t in _RELATIVE_TYPES}


def mirror_intent_type_of(intent: MirrorIntent) -> str:
    """Return the canonical string identifier for a mirror intent."""
    if isinstance(intent, ShowCase):
        return MirrorIntentType.SHOW_CASE.value
    if isinstance(intent, ListCases):
        return MirrorIntentType.LIST_CASES.value
    if isinstance(intent, ShowDataPoint):
        return MirrorIntentType.SHOW_DATA_POINT.value
    if isinstance(intent, DrillDownToChild):
        return MirrorIntentType.DRILL_DOWN_TO_CHILD.value
    if isinstance(intent, ShowParent):
        return MirrorIntentType.SHOW_PARENT.value
    if isinstance(intent, ShowSiblings):
        return MirrorIntentType.SHOW_SIBLINGS.value
    return MirrorIntentType.UNCLEAR_MIRROR.value


def parse_mirror_intent(raw: dict[str, Any]) -> MirrorIntent:
    """Discriminate a raw structured-output dict into a typed MirrorIntent.

    Defensive: empty/missing required fields fall back to
    UnclearMirrorIntent so the cell's confidence-dispatch routing
    handles them uniformly with model-reported unclear cases.
    """
    intent_class = str(raw.get("intent_class", "")).strip()
    case_reference = str(raw.get("case_reference", "")).strip()
    data_point_reference = str(raw.get("data_point_reference", "")).strip()
    child_reference = str(raw.get("child_reference", "")).strip()
    clarification = str(raw.get("clarification", "")).strip()

    if intent_class == MirrorIntentType.SHOW_CASE.value and case_reference:
        return ShowCase(case_reference=case_reference)
    if intent_class == MirrorIntentType.LIST_CASES.value:
        return ListCases()
    if (
        intent_class == MirrorIntentType.SHOW_DATA_POINT.value
        and data_point_reference
    ):
        return ShowDataPoint(
            data_point_reference=data_point_reference,
            case_reference=case_reference,
        )
    if (
        intent_class == MirrorIntentType.DRILL_DOWN_TO_CHILD.value
        and child_reference
    ):
        return DrillDownToChild(child_reference=child_reference)
    if intent_class == MirrorIntentType.SHOW_PARENT.value:
        return ShowParent()
    if intent_class == MirrorIntentType.SHOW_SIBLINGS.value:
        return ShowSiblings()
    return UnclearMirrorIntent(
        clarification=(
            clarification
            or "Could you clarify which case or data point you'd like to see?"
        )
    )


__all__ = [
    "DrillDownToChild",
    "ListCases",
    "MirrorIntent",
    "MirrorIntentType",
    "ShowCase",
    "ShowDataPoint",
    "ShowParent",
    "ShowSiblings",
    "UnclearMirrorIntent",
    "is_relative",
    "mirror_intent_type_of",
    "parse_mirror_intent",
]
