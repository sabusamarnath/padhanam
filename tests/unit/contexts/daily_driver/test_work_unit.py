"""Unit tests for the work-unit correlation matcher (D168, D166)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    WorkFacet,
    correlate_facets,
    normalise_title,
)

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")
_NOW = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _facet(
    facet_type: FacetType,
    title: str,
    *,
    occurred_at: datetime | None = None,
    facet_id: UUID | None = None,
) -> WorkFacet:
    return WorkFacet(
        facet_type=facet_type,
        facet_id=facet_id or uuid4(),
        title=title,
        occurred_at=occurred_at,
    )


def _by_id(units, unit_id):
    return next(u for u in units if u.unit_id == unit_id)


def test_normalise_title_lowercases_strips_and_collapses():
    assert normalise_title("  Ship the  Q3   Report! ") == "ship the q3 report"
    assert normalise_title("Q3-Report") == "q3 report"
    assert normalise_title("!!!") == ""
    assert normalise_title("   ") == ""


def test_title_and_time_match_confirms_the_link():
    task = _facet(FacetType.TASK, "Ship Q3 report", occurred_at=_NOW)
    meeting = _facet(
        FacetType.MEETING,
        "Ship Q3 Report",
        occurred_at=_NOW + timedelta(days=2),
    )
    units = correlate_facets((task, meeting), tenant_id=_TENANT)

    assert len(units) == 1
    unit = units[0]
    # Task anchors over the meeting (anchor priority task > meeting).
    assert unit.anchor.facet_id == task.facet_id
    assert unit.is_correlated
    other = next(
        link for link in unit.links if link.facet.facet_id == meeting.facet_id
    )
    assert other.status is LinkStatus.CONFIRMED
    assert other.basis == "title+time"
    assert other.confidence >= 0.8


def test_title_match_without_time_corroboration_is_a_candidate():
    # Same title, but the times are far apart → below the floor → candidate.
    task = _facet(FacetType.TASK, "Plan offsite", occurred_at=_NOW)
    meeting = _facet(
        FacetType.MEETING,
        "Plan offsite",
        occurred_at=_NOW + timedelta(days=60),
    )
    units = correlate_facets((task, meeting), tenant_id=_TENANT)

    assert len(units) == 1
    other = next(
        link
        for link in units[0].links
        if link.facet.facet_id == meeting.facet_id
    )
    assert other.status is LinkStatus.CANDIDATE
    assert other.basis == "title"


def test_missing_time_anchor_is_a_candidate_not_a_confirmed_link():
    task = _facet(FacetType.TASK, "Renew contract", occurred_at=None)
    email = _facet(FacetType.EMAIL, "Renew contract", occurred_at=_NOW)
    units = correlate_facets((task, email), tenant_id=_TENANT)

    other = next(
        link
        for link in units[0].links
        if link.facet.facet_id == email.facet_id
    )
    assert other.status is LinkStatus.CANDIDATE


def test_anchor_link_is_always_confirmed_with_full_confidence():
    task = _facet(FacetType.TASK, "Solo task", occurred_at=_NOW)
    units = correlate_facets((task,), tenant_id=_TENANT)

    assert len(units) == 1
    unit = units[0]
    assert not unit.is_correlated
    (anchor_link,) = unit.links
    assert anchor_link.status is LinkStatus.CONFIRMED
    assert anchor_link.confidence == 1.0
    assert anchor_link.basis == "anchor"


def test_distinct_titles_form_separate_single_facet_units():
    a = _facet(FacetType.TASK, "Alpha", occurred_at=_NOW)
    b = _facet(FacetType.TASK, "Beta", occurred_at=_NOW)
    units = correlate_facets((a, b), tenant_id=_TENANT)

    assert len(units) == 2
    assert all(not u.is_correlated for u in units)


def test_blank_title_facets_never_correlate():
    a = _facet(FacetType.TASK, "   ", occurred_at=_NOW)
    b = _facet(FacetType.MEETING, "!!!", occurred_at=_NOW)
    units = correlate_facets((a, b), tenant_id=_TENANT)

    # Two separate single-facet units — nothing to match on.
    assert len(units) == 2
    assert all(not u.is_correlated for u in units)


def test_unit_id_is_deterministic_in_the_anchor_for_idempotent_recorrelation():
    task = _facet(
        FacetType.TASK,
        "Ship report",
        occurred_at=_NOW,
        facet_id=UUID("11111111-0000-4000-8000-000000000001"),
    )
    meeting = _facet(FacetType.MEETING, "Ship report", occurred_at=_NOW)

    first = correlate_facets((task, meeting), tenant_id=_TENANT)
    # Re-run with the inputs reordered: same units, same ids (idempotent).
    second = correlate_facets((meeting, task), tenant_id=_TENANT)

    assert [u.unit_id for u in first] == [u.unit_id for u in second]


def test_anchor_priority_prefers_task_then_meeting_then_email():
    meeting = _facet(FacetType.MEETING, "Quarterly review", occurred_at=_NOW)
    email = _facet(FacetType.EMAIL, "Quarterly review", occurred_at=_NOW)
    units = correlate_facets((email, meeting), tenant_id=_TENANT)

    assert len(units) == 1
    # Meeting outranks email as the anchor.
    assert units[0].anchor.facet_id == meeting.facet_id


def test_tenant_scopes_the_unit_id():
    task = _facet(
        FacetType.TASK,
        "Same task",
        occurred_at=_NOW,
        facet_id=UUID("22222222-0000-4000-8000-000000000002"),
    )
    other_tenant = UUID("00000000-0000-4000-8000-00000000d002")
    a = correlate_facets((task,), tenant_id=_TENANT)[0]
    b = correlate_facets((task,), tenant_id=other_tenant)[0]
    assert a.unit_id != b.unit_id
