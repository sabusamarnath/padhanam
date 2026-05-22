"""Registers ``contexts/portfolio`` DataPoint against the Revisable contract.

DataPoint is the first Revisable implementer (S43, D125). This module
builds a fresh-DataPoint factory plus a sample AssertionChange and
registers them through the conftest mechanism, so the parametrised
scenarios in ``test_revisable_contract.py`` run against DataPoint
automatically. A future implementer adds an equivalent
``test_<implementer>_revisable.py`` and needs no harness change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.portfolio.domain.assertion import Assertion, AssertionType
from contexts.portfolio.domain.data_point import DataPoint, DataPointType
from shared_kernel import ActorReference, AssertionChange
from shared_kernel.revisable import Revisable

from tests.contract.revisable.conftest import (
    RevisableImplementerFixture,
    register_revisable_implementer,
)

_AUTHOR = ActorReference(user_id="revisable-contract-data-point-author")


def _make_data_point() -> DataPoint:
    """A fresh DataPoint carrying one INITIAL (genesis) assertion."""
    now = datetime.now(timezone.utc)
    data_point_id = uuid4()
    tenant_id = uuid4()
    jurisdiction = "EU"
    genesis = Assertion(
        id=uuid4(),
        data_point_id=data_point_id,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value={"state": "genesis"},
        authored_by=_AUTHOR,
        created_at=now,
        intake_id=None,
    )
    return DataPoint(
        id=data_point_id,
        case_id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        data_point_type=DataPointType.GOAL,
        value={"state": "genesis"},
        authored_by=_AUTHOR,
        created_at=now,
        assertions=(genesis,),
    )


register_revisable_implementer(
    RevisableImplementerFixture(
        name="portfolio.DataPoint",
        implementer_cls=DataPoint,
        make_instance=_make_data_point,
        sample_change=AssertionChange(value={"state": "revised"}),
    )
)


def test_data_point_satisfies_runtime_checkable_revisable() -> None:
    """Sanity check: a fresh DataPoint structurally satisfies the
    ``@runtime_checkable`` Revisable protocol — the isinstance surface
    ``@runtime_checkable`` provides. The parametrised scenarios in
    ``test_revisable_contract.py`` verify the rest of the contract."""
    assert isinstance(_make_data_point(), Revisable)
