"""The authored CDD — provenance, proof, the draft schema, and the pure parse (S102, D200).

D200 pivots the CDD from auto-derived to authored-per-goal: the LLM drafts each
goal's levers, intermediaries, externals, and expected outcome, and the user
proofs it. This module is pure domain (D16, stdlib only): the enums that carry
the authored signal, the JSON Schema the structured-output port constrains the
model to, the prompt builder, the pure response mapping, and the value objects
the proof read returns. The LLM call itself lives in an adapter behind the
``StructuredOutputPort`` (the checkin reply-parse precedent).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


class ProvenanceOrigin(str, Enum):
    """Where an authored element came from — first-class optimization signal (D200)."""

    LLM_DRAFTED = "llm_drafted"
    USER_AUTHORED = "user_authored"
    SYSTEM_SUGGESTED = "system_suggested"


class ProofState(str, Enum):
    """Whether the user has proofed an authored element (D200). A rejected element
    is removed (user-initiated delete), so it has no resting state here."""

    PENDING = "pending"
    ACCEPTED = "accepted"


class ElementKind(str, Enum):
    """The authored element kinds that feed the outcome (D198/D200). The goal-and-
    outcome node itself is the existing ``:Outcome`` (D199), not an authored kind."""

    LEVER = "lever"
    INTERMEDIARY = "intermediary"
    EXTERNAL = "external"


# The kinds an EVIDENCES edge can target (D202) — the authored elements *plus* the
# outcome goal node a unit can be bound to. Distinct from ``ElementKind`` (which is
# the authored-element kinds only): unlink/relink operate on EVIDENCES endpoints, so
# they accept ``outcome`` too. (S103c-fix-3: the Map-unlink 422 was the router
# rejecting ``outcome`` via ``ElementKind`` while the graph endpoint supported it.)
EVIDENCE_KINDS: frozenset[str] = frozenset(
    {"lever", "intermediary", "external", "outcome"}
)


# The recent-few cap per kind so a verbose draft cannot flood the proof surface.
_MAX_PER_KIND = 6


@dataclass(frozen=True)
class DraftedElement:
    """One element the LLM drafted (kind + label), before it is persisted."""

    kind: ElementKind
    label: str


@dataclass(frozen=True)
class DraftedCdd:
    """A goal's drafted CDD as parsed from the model (S102, D200)."""

    levers: tuple[DraftedElement, ...]
    intermediaries: tuple[DraftedElement, ...]
    externals: tuple[DraftedElement, ...]
    expected_outcome: str

    @property
    def elements(self) -> tuple[DraftedElement, ...]:
        return self.levers + self.intermediaries + self.externals


@dataclass(frozen=True)
class AuthoredElement:
    """One authored element as read for proof (S102, D200)."""

    kind: ElementKind
    element_id: UUID
    label: str
    provenance_origin: ProvenanceOrigin
    proof_state: ProofState
    # The gate whose local CDD this element belongs to (S103g, D207), or None for
    # a goal-level (portfolio) element.
    gate_id: UUID | None = None


@dataclass(frozen=True)
class AuthoredEdgeView:
    """One authored causal edge as read for proof (S102).

    ``needs_review`` is set when a reclassify (D201, S103a) left the edge
    ungrammatical for its new source kind — surfaced for the user, never dropped.
    """

    edge_type: str
    source_kind: str
    source_id: UUID
    target_kind: str
    target_id: UUID
    needs_review: bool = False


@dataclass(frozen=True)
class GoalCddView:
    """A goal's authored CDD as read for proof (S102, D200).

    ``expected_outcome_origin`` / ``expected_outcome_proof_state`` carry the
    outcome's authored signal so it renders as a proofable terminal element
    (S103a); both are ``None`` when the goal has no authored outcome yet.
    """

    outcome_id: UUID
    expected_outcome: str
    elements: tuple[AuthoredElement, ...]
    edges: tuple[AuthoredEdgeView, ...]
    expected_outcome_origin: ProvenanceOrigin | None = None
    expected_outcome_proof_state: ProofState | None = None


# The JSON Schema the structured-output port constrains the model to.
_ELEMENT_ARRAY: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
        "additionalProperties": False,
    },
}
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "levers": _ELEMENT_ARRAY,
        "intermediaries": _ELEMENT_ARRAY,
        "externals": _ELEMENT_ARRAY,
        "expected_outcome": {"type": "string"},
    },
    "required": ["levers", "intermediaries", "externals", "expected_outcome"],
    "additionalProperties": False,
}


def build_draft_prompt(
    *, goal_name: str, mode: str, lever_names: tuple[str, ...]
) -> str:
    """Build the per-goal CDD draft prompt (S102, D200).

    The prompt teaches the four element kinds in the user's own causal terms and
    seeds the draft with the levers already known to the goal, so the model
    refines rather than invents from nothing.
    """
    known = (
        "Levers already known for this goal: "
        + ", ".join(lever_names)
        + ".\n"
        if lever_names
        else ""
    )
    return (
        "You map a person's goal into a small causal diagram so they can see "
        "what drives it. Draft four things for the goal below.\n\n"
        f'Goal: "{goal_name}" (mode: {mode}).\n'
        f"{known}\n"
        "Draft:\n"
        "- levers: the concrete actions THIS PERSON controls that move the goal "
        "(2-5). Refine the known levers; add any obvious missing one.\n"
        "- intermediaries: the in-between factors a lever changes on the way to "
        "the outcome — the measurable middle of the chain (1-4). For a job "
        "search: application response rate, interview conversion.\n"
        "- externals: things OTHER parties decide that influence the outcome but "
        "the person does not control (0-3). For a job search: a hiring freeze, "
        "a recruiter reaching out.\n"
        "- expected_outcome: one short phrase naming the measurable result that "
        "means the goal is met.\n\n"
        "Keep each label short (a few words). Output only what fits the goal; "
        "an empty externals list is fine if nothing external applies."
    )


def required_edge_type(kind: ElementKind) -> str:
    """The authored edge type an element of this kind uses as a *source* (D198,
    D201): a lever or an intermediary ``FEEDS``; an external ``INFLUENCES`` (it
    is not controlled). Used to wire an added element's default edge and to test
    whether a reclassify leaves an incident edge ungrammatical (S103a)."""
    return "INFLUENCES" if kind is ElementKind.EXTERNAL else "FEEDS"


def _parse_elements(raw: Any, kind: ElementKind) -> tuple[DraftedElement, ...]:
    """Pull labelled elements of one kind, defensively (pure).

    Drops non-dict entries and empty/blank labels, dedupes case-insensitively,
    and caps at the per-kind maximum so a verbose draft cannot flood the surface.
    """
    out: list[DraftedElement] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        return ()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if not isinstance(label, str):
            continue
        label = label.strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(DraftedElement(kind=kind, label=label))
        if len(out) >= _MAX_PER_KIND:
            break
    return tuple(out)


def parse_cdd_draft(value: dict[str, Any]) -> DraftedCdd:
    """Map the model's draft to a ``DraftedCdd`` (pure, defensive).

    Unknown shapes degrade to empty tuples / an empty expected outcome rather
    than raising; the use case decides whether an empty draft is persistable.
    """
    if not isinstance(value, dict):
        value = {}
    expected = value.get("expected_outcome")
    return DraftedCdd(
        levers=_parse_elements(value.get("levers"), ElementKind.LEVER),
        intermediaries=_parse_elements(
            value.get("intermediaries"), ElementKind.INTERMEDIARY
        ),
        externals=_parse_elements(value.get("externals"), ElementKind.EXTERNAL),
        expected_outcome=expected.strip() if isinstance(expected, str) else "",
    )


__all__ = [
    "AuthoredEdgeView",
    "AuthoredElement",
    "DRAFT_SCHEMA",
    "DraftedCdd",
    "DraftedElement",
    "EVIDENCE_KINDS",
    "ElementKind",
    "GoalCddView",
    "ProofState",
    "ProvenanceOrigin",
    "build_draft_prompt",
    "parse_cdd_draft",
    "required_edge_type",
]
