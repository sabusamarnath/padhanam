"""The act-worklist domain: horizon math + per-subject dedupe (D232)."""

from __future__ import annotations

from contexts.daily_driver.domain.act_worklist import (
    HORIZON_LATER,
    HORIZON_OVERDUE,
    HORIZON_TODAY,
    HORIZON_WEEK,
    ActItem,
    build_act_worklist,
    horizon_of,
)


def _item(source, subject_id, due, *, kind="opportunity", is_opp=True, subject="X"):
    return ActItem(
        source=source, subject_kind=kind, subject_id=subject_id, subject=subject,
        action="do it", due_in_days=due, is_opportunity=is_opp,
    )


def test_horizon_boundaries_today_week_and_the_day_eight_cliff() -> None:
    assert horizon_of(-3) == HORIZON_OVERDUE
    assert horizon_of(0) == HORIZON_TODAY
    assert horizon_of(1) == HORIZON_WEEK
    assert horizon_of(7) == HORIZON_WEEK  # due within seven days
    assert horizon_of(8) == HORIZON_LATER  # a day-8 item is NOT in Week (AC4)


def test_today_filter_is_due_today_or_overdue() -> None:
    items = build_act_worklist([
        _item("pipeline", "a", -2), _item("pipeline", "b", 0),
        _item("pipeline", "c", 3), _item("pipeline", "d", 8),
    ])
    today = [i for i in items if i.due_in_days <= 0]
    week = [i for i in items if i.due_in_days <= 7]
    assert {i.subject_id for i in today} == {"a", "b"}
    assert {i.subject_id for i in week} == {"a", "b", "c"}  # d (day 8) excluded


def test_dedupe_per_subject_keeps_the_most_overdue() -> None:
    # A pipeline follow-up (silent, due -1) and a stale qualification field
    # (due -5) on ONE opportunity collapse to the more overdue (qualification).
    items = build_act_worklist([
        _item("pipeline", "opp-1", -1),
        _item("qualification", "opp-1", -5),
    ])
    assert len(items) == 1
    assert items[0].source == "qualification"
    assert items[0].due_in_days == -5


def test_distinct_kinds_do_not_collide() -> None:
    # Same id string under different subject_kinds are distinct subjects.
    items = build_act_worklist([
        _item("commitment", "x", 0, kind="commitment", is_opp=False),
        _item("case", "x", 0, kind="case", is_opp=False),
    ])
    assert len(items) == 2


def test_sorted_by_urgency_then_subject() -> None:
    items = build_act_worklist([
        _item("pipeline", "b", 2, subject="Beta"),
        _item("pipeline", "a", -4, subject="Alpha"),
        _item("pipeline", "c", -4, subject="Aardvark"),
    ])
    # most overdue first; ties broken by subject name.
    assert [i.subject_id for i in items] == ["c", "a", "b"]


def test_doing_filter_is_opportunity_items() -> None:
    items = build_act_worklist([
        _item("pipeline", "opp", -1),
        _item("commitment", "c", -1, kind="commitment", is_opp=False),
    ])
    doing = [i for i in items if i.is_opportunity]
    assert {i.subject_id for i in doing} == {"opp"}
