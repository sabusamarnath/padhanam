"""list_correction_origins — the D203 origins map for the receipt Undo (S103ae, D237)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from contexts.daily_driver.application.correction_receipt import (
    list_correction_origins,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


@dataclass
class _Evt:
    resource_id: str
    action_verb: str
    before_state: dict


@dataclass
class _Page:
    events: list
    next_cursor: object = None


class _FakeReader:
    """Serves pre-canned pages; records the filter it was asked for."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.filters_seen = []

    async def list_audit_events_with_filters(self, *, destination, filters, cursor, page_size, tenant_context):
        self.filters_seen.append(filters)
        # cursor=None -> first page; then follow next_cursor
        idx = 0 if cursor is None else cursor
        page = self._pages[idx]
        nxt = idx + 1 if idx + 1 < len(self._pages) else None
        return _Page(events=page, next_cursor=nxt)


def _run(reader):
    return asyncio.run(list_correction_origins(audit_reader=reader, actor=_actor()))


def test_maps_units_to_recorded_from_target() -> None:
    reader = _FakeReader([[
        _Evt("unit-1", "cdd.relink", {"element_kind": "lever", "element_id": "el-A"}),
        _Evt("unit-2", "cdd.unlink", {"element_kind": "outcome", "element_id": "el-B"}),
    ]])
    origins = _run(reader)
    assert origins["unit-1"] == {"verb": "cdd.relink", "from_kind": "lever", "from_element_id": "el-A"}
    assert origins["unit-2"] == {"verb": "cdd.unlink", "from_kind": "outcome", "from_element_id": "el-B"}
    # asked the trail for the correction verbs on the evidence resource type
    f = reader.filters_seen[0]
    assert f.resource_type == "cdd_element_evidence"
    assert set(f.action_verbs) == {"cdd.relink", "cdd.unlink"}


def test_latest_correction_per_unit_wins_timestamp_desc() -> None:
    # events sort timestamp DESC, so the FIRST seen per unit is its latest correction
    reader = _FakeReader([[
        _Evt("unit-1", "cdd.relink", {"element_kind": "outcome", "element_id": "el-NEW"}),  # latest
        _Evt("unit-1", "cdd.relink", {"element_kind": "lever", "element_id": "el-OLD"}),    # earlier
    ]])
    origins = _run(reader)
    assert origins["unit-1"]["from_element_id"] == "el-NEW"


def test_paginates_until_exhausted() -> None:
    reader = _FakeReader([
        [_Evt("unit-1", "cdd.relink", {"element_kind": "lever", "element_id": "el-A"})],
        [_Evt("unit-2", "cdd.relink", {"element_kind": "lever", "element_id": "el-B"})],
    ])
    origins = _run(reader)
    assert set(origins) == {"unit-1", "unit-2"}


def test_unwired_reader_is_empty() -> None:
    assert _run(None) == {}
