"""Unit tests for the missing-facet suggestion engine (S68, D170, D166)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.daily_driver.domain.facet_suggestion import (
    SuggestionKind,
    suggest_missing_facets,
)
from contexts.daily_driver.domain.unit_view import UnitFacetView, UnitView
from contexts.daily_driver.domain.work_unit import FacetType, LinkStatus

_NOW = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)


def _fv(facet_type, *, occurred_at=None, present=True, title="x"):
    return UnitFacetView(
        facet_type=facet_type,
        facet_id=uuid4(),
        title=title,
        occurred_at=occurred_at,
        status=LinkStatus.CONFIRMED,
        confidence=1.0,
        basis="anchor",
        present=present,
    )


def _unit(title, facets, *, unit_id=None):
    return UnitView(unit_id=unit_id or uuid4(), title=title, facets=tuple(facets))


def test_substantial_task_with_no_time_gets_a_block_suggestion():
    u = _unit("Ship Q3 report", (_fv(FacetType.TASK, occurred_at=_NOW),))
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert len(out) == 1
    assert out[0].kind is SuggestionKind.BLOCK


def test_atomic_one_off_task_gets_no_block_suggestion():
    # No due anchor → atomic → left alone (D170 scope-guard).
    u = _unit("Reply to Sam", (_fv(FacetType.TASK, occurred_at=None),))
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert out == ()


def test_event_with_no_task_gets_satellite_work_not_an_event_mirror():
    u = _unit("Board meeting", (_fv(FacetType.MEETING, occurred_at=_NOW),))
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert len(out) == 1
    assert out[0].kind is SuggestionKind.SATELLITE_WORK
    # Satellite work, never an event mirror: the prose is prep/follow-up, not
    # "create a task called Board meeting".
    assert "prep" in out[0].suggestion or "follow-up" in out[0].suggestion


def test_email_with_no_task_becomes_a_candidate_task():
    u = _unit("Contract renewal request", (_fv(FacetType.EMAIL, occurred_at=_NOW),))
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert len(out) == 1
    assert out[0].kind is SuggestionKind.CANDIDATE_TASK


def test_orphan_unit_gets_no_suggestion_the_credulity_gate():
    # Serves no goal → not in the served set → silent (D170 credulity gate).
    u = _unit("Ship Q3 report", (_fv(FacetType.TASK, occurred_at=_NOW),))
    out = suggest_missing_facets((u,), frozenset())
    assert out == ()


def test_complete_unit_task_plus_meeting_gets_no_suggestion():
    u = _unit(
        "Ship Q3 report",
        (
            _fv(FacetType.TASK, occurred_at=_NOW),
            _fv(FacetType.MEETING, occurred_at=_NOW),
        ),
    )
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert out == ()


def test_at_most_one_suggestion_per_unit():
    # A unit with an email facet and a goal but also a task gap — only one
    # suggestion, the highest-priority applicable one.
    u = _unit(
        "Quarterly planning",
        (_fv(FacetType.MEETING, occurred_at=_NOW),),
    )
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert len(out) == 1


def test_removed_facet_does_not_count_as_present():
    # The only facet is gone from its cache → no present types → no suggestion.
    u = _unit(
        "Ship Q3 report",
        (_fv(FacetType.TASK, occurred_at=_NOW, present=False),),
    )
    out = suggest_missing_facets((u,), frozenset({u.unit_id}))
    assert out == ()


# --------------------------------------------------------------------------
# D196 (S99) — the relevance gate: a maintenance rhythm gets no planning nudge.
# A unit whose served outcomes are all homeostatic is gated at the source; a
# unit serving any progressive/sequence outcome is untouched (precision guard).
# --------------------------------------------------------------------------


def test_homeostatic_served_unit_gets_no_suggestion_the_relevance_gate():
    # A substantial task that would otherwise earn a BLOCK — but its served
    # outcome is homeostatic (a medication dose), so D196 gates it to zero.
    u = _unit("Lansoprazole", (_fv(FacetType.TASK, occurred_at=_NOW),))
    out = suggest_missing_facets(
        (u,),
        frozenset({u.unit_id}),
        frozenset({u.unit_id}),  # homeostatic-only
    )
    assert out == ()


def test_non_homeostatic_served_unit_keeps_its_suggestion():
    # Same substantial task, but serving a progressive/sequence outcome (absent
    # from the homeostatic-only set) — the nudge is untouched. The precision
    # guard against over-gating beyond homeostatic.
    u = _unit("Ship Q3 report", (_fv(FacetType.TASK, occurred_at=_NOW),))
    out = suggest_missing_facets(
        (u,),
        frozenset({u.unit_id}),
        frozenset(),  # not homeostatic-only
    )
    assert len(out) == 1
    assert out[0].kind is SuggestionKind.BLOCK
