"""Application + view tests for work-unit correlation (S66, D168, D166).

Covers correlate_units (read facets → match → replace graph), list_units (read
graph + enrich from caches → views), the authorisation boundary, and the
build_unit_views projection (ordering, candidate flag, removed-facet handling).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.daily_driver.application import correlate_units, list_units
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    WorkFacet,
)
from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)

_TENANT = "00000000-0000-4000-8000-00000000d001"
_NOW = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _actor(*, authorised: bool = True) -> ActorContext:
    roles = frozenset({ROLE_OPERATOR}) if authorised else frozenset({"viewer"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeFacetSource:
    def __init__(self, facets) -> None:
        self._facets = facets

    async def list_facets(self, *, actor):
        return tuple(self._facets)


class _FakeUnitGraph:
    def __init__(self, records=()) -> None:
        self.written = None
        self._records = records

    async def replace_units(self, *, tenant_context, units):
        self.written = list(units)

    async def list_units(self, *, tenant_context):
        return tuple(self._records)


def test_correlate_units_matches_and_replaces_the_graph() -> None:
    task_id, meeting_id = uuid4(), uuid4()
    facets = [
        WorkFacet(FacetType.TASK, task_id, "Ship Q3 report", _NOW),
        WorkFacet(FacetType.MEETING, meeting_id, "Ship Q3 Report", _NOW),
        WorkFacet(FacetType.EMAIL, uuid4(), "Unrelated note", _NOW),
    ]
    graph = _FakeUnitGraph()
    count = asyncio.run(
        correlate_units(
            facet_source=_FakeFacetSource(facets),
            unit_graph=graph,
            actor=_actor(),
        )
    )
    # Two units: the task+meeting correlation, and the lone email.
    assert count == 2
    correlated = [u for u in graph.written if len(u.links) > 1]
    assert len(correlated) == 1
    assert correlated[0].anchor.facet_id == task_id


def test_correlate_units_requires_authorisation() -> None:
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            correlate_units(
                facet_source=_FakeFacetSource([]),
                unit_graph=_FakeUnitGraph(),
                actor=_actor(authorised=False),
            )
        )


def test_list_units_enriches_graph_records_with_cache_titles() -> None:
    task_id, meeting_id, unit_id = uuid4(), uuid4(), uuid4()
    record = UnitRecord(
        unit_id=unit_id,
        facets=(
            UnitFacetRef(FacetType.TASK, task_id, 1.0, LinkStatus.CONFIRMED, "anchor"),
            UnitFacetRef(
                FacetType.MEETING, meeting_id, 0.9, LinkStatus.CONFIRMED, "title+time"
            ),
        ),
    )
    facets = [
        WorkFacet(FacetType.TASK, task_id, "Ship report", _NOW),
        WorkFacet(FacetType.MEETING, meeting_id, "Ship report", _NOW),
    ]
    views = asyncio.run(
        list_units(
            unit_graph=_FakeUnitGraph([record]),
            facet_source=_FakeFacetSource(facets),
            actor=_actor(),
        )
    )
    assert len(views) == 1
    assert views[0].is_correlated
    assert views[0].title == "Ship report"
    assert all(f.present for f in views[0].facets)


def test_list_units_requires_authorisation() -> None:
    with pytest.raises(AuthorisationDenied):
        asyncio.run(
            list_units(
                unit_graph=_FakeUnitGraph(),
                facet_source=_FakeFacetSource([]),
                actor=_actor(authorised=False),
            )
        )


def test_build_unit_views_marks_candidate_and_removed_facets() -> None:
    task_id, email_id, unit_id = uuid4(), uuid4(), uuid4()
    record = UnitRecord(
        unit_id=unit_id,
        facets=(
            UnitFacetRef(FacetType.TASK, task_id, 1.0, LinkStatus.CONFIRMED, "anchor"),
            UnitFacetRef(
                FacetType.EMAIL, email_id, 0.6, LinkStatus.CANDIDATE, "title"
            ),
        ),
    )
    # The email facet's cache row is gone (deleted since correlation).
    facets_by_key = {
        (FacetType.TASK, task_id): WorkFacet(
            FacetType.TASK, task_id, "Renew contract", _NOW
        )
    }
    views = build_unit_views((record,), facets_by_key)
    assert views[0].has_candidate
    email_view = next(f for f in views[0].facets if f.facet_type is FacetType.EMAIL)
    assert email_view.status is LinkStatus.CANDIDATE
    assert email_view.present is False
    assert email_view.title == "(removed from source)"


def test_build_unit_views_orders_correlated_units_first() -> None:
    solo_id, t_id, m_id = uuid4(), uuid4(), uuid4()
    solo = UnitRecord(
        unit_id=uuid4(),
        facets=(
            UnitFacetRef(FacetType.TASK, solo_id, 1.0, LinkStatus.CONFIRMED, "anchor"),
        ),
    )
    correlated = UnitRecord(
        unit_id=uuid4(),
        facets=(
            UnitFacetRef(FacetType.TASK, t_id, 1.0, LinkStatus.CONFIRMED, "anchor"),
            UnitFacetRef(
                FacetType.MEETING, m_id, 0.9, LinkStatus.CONFIRMED, "title+time"
            ),
        ),
    )
    facets_by_key = {
        (FacetType.TASK, solo_id): WorkFacet(FacetType.TASK, solo_id, "Zeta solo", _NOW),
        (FacetType.TASK, t_id): WorkFacet(FacetType.TASK, t_id, "Alpha unit", _NOW),
        (FacetType.MEETING, m_id): WorkFacet(FacetType.MEETING, m_id, "Alpha unit", _NOW),
    }
    views = build_unit_views((solo, correlated), facets_by_key)
    # Correlated unit leads despite the solo's title sorting first alphabetically.
    assert views[0].is_correlated
    assert not views[1].is_correlated
