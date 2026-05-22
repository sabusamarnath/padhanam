"""Target identifier resolution for the manual entry cell (D129, S46).

The manual entry cell extracts intents carrying *natural-language*
references — ``AddDataPointIntent.case_reference``,
``ReviseDataPointIntent.data_point_reference`` (Path B). Before the
cell can drive a portfolio write it must resolve that reference to a
concrete Case or DataPoint id.

This module owns the pure matching logic: given a reference string
and a set of ``TargetCandidate`` (id plus human label) the cell
fetched from portfolio state, it returns a ``ResolutionOutcome`` —
matched-single, ambiguous, or no-match. Fetching the candidates is
the cell's job (through the ``PortfolioGateway`` consumer port);
``resolve_target`` is deliberately port-free and pure so it is
exhaustively unit-testable.

The Phase 2-A heuristic is significant-token overlap: an exact
token-set match wins outright; otherwise the candidate sharing the
most reference tokens wins, and a tie at the top score is honestly
reported as ambiguous rather than guessed. LLM-assisted resolution
is a later refinement if the heuristic proves too blunt at dogfooding.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

# Words that carry no discriminating signal for a portfolio reference.
# Stripped before token overlap so "the Q3 review case" and "Q3
# review" score as a clean two-token match.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those",
        "to", "of", "for", "in", "on", "and", "or", "with", "about",
        "case", "cases", "data", "point", "points", "datapoint", "item",
        "items", "please", "update", "add", "revise", "change", "set",
        "goal", "status",
    }
)


class ResolutionStatus(StrEnum):
    """The outcome class of a target-identifier resolution."""

    MATCHED_SINGLE = "matched_single"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


@dataclass(frozen=True)
class TargetCandidate:
    """One Case or DataPoint a reference might name.

    ``label`` is the human-readable string the match scores against
    (a Case title, or a DataPoint's type plus value summary). The
    cell builds these from what the ``PortfolioGateway`` returns.
    """

    id: UUID
    label: str


@dataclass(frozen=True)
class ResolutionOutcome:
    """The result of resolving a natural-language reference.

    ``matched_id`` is set only on ``MATCHED_SINGLE``;
    ``candidate_labels`` carries the tied human labels only on
    ``AMBIGUOUS`` so the cell can compose a clarification naming them.
    """

    status: ResolutionStatus
    matched_id: UUID | None = None
    candidate_labels: tuple[str, ...] = field(default_factory=tuple)


def _significant_tokens(text: str) -> frozenset[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords."""
    return frozenset(
        word
        for word in re.split(r"[^a-z0-9]+", text.lower())
        if word and word not in _STOPWORDS
    )


def resolve_target(
    reference: str, candidates: Sequence[TargetCandidate]
) -> ResolutionOutcome:
    """Resolve a natural-language reference against candidate targets.

    An exact significant-token-set match wins outright when unique.
    Otherwise the candidate sharing the most reference tokens wins;
    a tie at the top non-zero score is ambiguous; a top score of zero
    is no-match. An empty reference or empty candidate set is
    no-match.
    """
    ref_tokens = _significant_tokens(reference)
    if not ref_tokens or not candidates:
        return ResolutionOutcome(status=ResolutionStatus.NO_MATCH)

    # Exact token-set match takes precedence over overlap scoring.
    exact = [
        c for c in candidates if _significant_tokens(c.label) == ref_tokens
    ]
    if len(exact) == 1:
        return ResolutionOutcome(
            status=ResolutionStatus.MATCHED_SINGLE, matched_id=exact[0].id
        )

    scored = [
        (len(ref_tokens & _significant_tokens(c.label)), c)
        for c in candidates
    ]
    best_score = max(score for score, _ in scored)
    if best_score == 0:
        return ResolutionOutcome(status=ResolutionStatus.NO_MATCH)

    winners = [c for score, c in scored if score == best_score]
    if len(winners) == 1:
        return ResolutionOutcome(
            status=ResolutionStatus.MATCHED_SINGLE, matched_id=winners[0].id
        )
    return ResolutionOutcome(
        status=ResolutionStatus.AMBIGUOUS,
        candidate_labels=tuple(c.label for c in winners),
    )


__all__ = [
    "ResolutionOutcome",
    "ResolutionStatus",
    "TargetCandidate",
    "resolve_target",
]
