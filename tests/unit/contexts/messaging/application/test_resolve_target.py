"""Unit tests for target identifier resolution (S46)."""

from __future__ import annotations

from uuid import uuid4

from contexts.messaging.application.resolve_target import (
    ResolutionStatus,
    TargetCandidate,
    resolve_target,
)


def test_exact_token_set_match_resolves_single() -> None:
    target = TargetCandidate(id=uuid4(), label="Q3 portfolio review")
    other = TargetCandidate(id=uuid4(), label="annual planning")
    outcome = resolve_target("the Q3 portfolio review case", [target, other])
    assert outcome.status is ResolutionStatus.MATCHED_SINGLE
    assert outcome.matched_id == target.id


def test_partial_overlap_resolves_to_best_single_candidate() -> None:
    target = TargetCandidate(id=uuid4(), label="Q3 portfolio review")
    other = TargetCandidate(id=uuid4(), label="hiring plan")
    outcome = resolve_target("update the Q3 review", [target, other])
    assert outcome.status is ResolutionStatus.MATCHED_SINGLE
    assert outcome.matched_id == target.id


def test_tied_overlap_is_ambiguous() -> None:
    first = TargetCandidate(id=uuid4(), label="Q3 review meeting")
    second = TargetCandidate(id=uuid4(), label="Q3 review planning")
    outcome = resolve_target("the Q3 review", [first, second])
    assert outcome.status is ResolutionStatus.AMBIGUOUS
    assert outcome.matched_id is None
    assert {c.label for c in outcome.candidates} == {
        "Q3 review meeting",
        "Q3 review planning",
    }
    assert {c.id for c in outcome.candidates} == {first.id, second.id}


def test_ambiguous_carries_candidate_discriminators_through() -> None:
    """S50: AMBIGUOUS preserves each candidate's discriminators tuple."""
    first = TargetCandidate(
        id=uuid4(),
        label="Q3 portfolio review",
        discriminators=("created 4 days ago", "0 data points"),
    )
    second = TargetCandidate(
        id=uuid4(),
        label="Q3 portfolio review",
        discriminators=("created 1 day ago", "2 data points"),
    )
    outcome = resolve_target("Q3 portfolio review", [first, second])
    assert outcome.status is ResolutionStatus.AMBIGUOUS
    assert len(outcome.candidates) == 2
    discs = {tuple(c.discriminators) for c in outcome.candidates}
    assert discs == {
        ("created 4 days ago", "0 data points"),
        ("created 1 day ago", "2 data points"),
    }


def test_target_candidate_discriminators_default_empty() -> None:
    """Existing call sites that omit discriminators get an empty tuple."""
    candidate = TargetCandidate(id=uuid4(), label="Q3 review")
    assert candidate.discriminators == ()


def test_exact_match_beats_a_token_tie() -> None:
    exact = TargetCandidate(id=uuid4(), label="Q3 review")
    longer = TargetCandidate(id=uuid4(), label="Q3 review meeting notes")
    outcome = resolve_target("Q3 review", [exact, longer])
    assert outcome.status is ResolutionStatus.MATCHED_SINGLE
    assert outcome.matched_id == exact.id


def test_zero_overlap_is_no_match() -> None:
    candidate = TargetCandidate(id=uuid4(), label="annual planning")
    outcome = resolve_target("the hiring pipeline", [candidate])
    assert outcome.status is ResolutionStatus.NO_MATCH
    assert outcome.matched_id is None


def test_empty_reference_is_no_match() -> None:
    candidate = TargetCandidate(id=uuid4(), label="Q3 review")
    assert (
        resolve_target("", [candidate]).status is ResolutionStatus.NO_MATCH
    )
    # A reference of only stopwords carries no significant tokens.
    assert (
        resolve_target("the case", [candidate]).status
        is ResolutionStatus.NO_MATCH
    )


def test_empty_candidate_set_is_no_match() -> None:
    outcome = resolve_target("Q3 review", [])
    assert outcome.status is ResolutionStatus.NO_MATCH


def test_resolution_is_case_insensitive() -> None:
    target = TargetCandidate(id=uuid4(), label="Q3 Portfolio Review")
    outcome = resolve_target("q3 portfolio review", [target])
    assert outcome.status is ResolutionStatus.MATCHED_SINGLE
    assert outcome.matched_id == target.id
