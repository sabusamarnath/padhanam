"""Tenant isolation contract for the daily-driver substrate (D24, D157, S58).

The ``commitments``, ``commitment_completions``, and ``day_item_states``
tables are tenant-scoped per database-per-tenant (D32). Both Postgres
adapters bind their tenant at construction and reject a TenantContext
for a different tenant before any session resolution — mirroring the
portfolio, intake, and fired_triggers adapters' bound-tenant assertion.

D24 requires every adapter touching tenant-scoped data to ship with
tenant_isolation contract scenarios.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import pytest

from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
    PostgresCommitmentRepository,
)
from contexts.daily_driver.adapters.outbound.postgres.day_repository import (
    PostgresDayRepository,
)
from contexts.daily_driver.domain.commitment import Commitment
from contexts.daily_driver.domain.today_item import ItemKind
from shared_kernel import TenantContext, TenantId


def _ctx(tenant: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant
    )


async def _unreachable_resolver(_tenant_id: TenantId) -> object:  # noqa: ARG001
    raise AssertionError("resolver must not be reached on bound-tenant reject")


def test_commitment_adapter_rejects_cross_tenant() -> None:
    adapter = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    commitment = Commitment(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name="Weekly review",
        expected_interval_days=7,
        authored_by_user_id="operator",
        created_at=__import__("datetime").datetime(
            2026, 6, 1, tzinfo=__import__("datetime").timezone.utc
        ),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.add_commitment(
                tenant_context=_ctx("tenant-b"), commitment=commitment
            )
        )


def test_commitment_adapter_rejects_cross_tenant_list() -> None:
    adapter = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(adapter.list_with_activity(tenant_context=_ctx("tenant-b")))


def test_commitment_adapter_rejects_cross_tenant_checkin_response() -> None:
    # D192 (S97a): the check-in negative write is bound-tenant too.
    import datetime as _dt

    from contexts.daily_driver.domain.commitment import (
        CheckinOutcome,
        CheckinResponse,
    )

    adapter = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    response = CheckinResponse(
        id=uuid4(),
        commitment_id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        beat_date=_dt.date(2026, 6, 15),
        outcome=CheckinOutcome.REPORTED_DIDNT,
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.add_checkin_response(
                tenant_context=_ctx("tenant-b"), response=response
            )
        )


def test_commitment_adapter_rejects_cross_tenant_observed_outcome() -> None:
    # S61 (D162): the observed-outcome write is bound-tenant too.
    import datetime as _dt

    from contexts.daily_driver.domain.commitment import OutcomeStatus

    adapter = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.record_observed_outcome(
                tenant_context=_ctx("tenant-b"),
                commitment_id=uuid4(),
                observed_outcome="x",
                outcome_status=OutcomeStatus.MET,
                observed_at=_dt.datetime(
                    2026, 6, 6, tzinfo=_dt.timezone.utc
                ),
            )
        )


def test_day_adapter_rejects_cross_tenant_get() -> None:
    adapter = PostgresDayRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.get_states(
                tenant_context=_ctx("tenant-b"),
                user_id="operator",
                day_date=date(2026, 6, 4),
            )
        )


def test_day_adapter_rejects_cross_tenant_set_done() -> None:
    adapter = PostgresDayRepository(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.set_done(
                tenant_context=_ctx("tenant-b"),
                user_id="operator",
                day_date=date(2026, 6, 4),
                kind=ItemKind.COMMITMENT,
                item_id=uuid4(),
                done=True,
            )
        )
