"""Unit tests for the neutral matcher-policy seam (D186/S91b).

No content — a boolean flag only, so no PII.
"""

from __future__ import annotations

import asyncio

from contexts.matcher_policy.domain import MatcherPolicy
from shared_kernel.tenant_context import TenantContext

_TENANT = "00000000-0000-4000-8000-00000000d001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )


class _FakeStore:
    """In-memory repository + reader over one policy (the port round-trip)."""

    def __init__(self) -> None:
        self._policy: MatcherPolicy | None = None

    async def set_policy(self, *, tenant_context, policy: MatcherPolicy) -> None:
        self._policy = policy

    async def get_policy(self, *, tenant_context) -> MatcherPolicy:
        return self._policy if self._policy is not None else MatcherPolicy.inactive()


def test_inactive_is_flag_off() -> None:
    assert MatcherPolicy.inactive().suppress_single_signal is False


def test_unset_policy_reads_inactive() -> None:
    store = _FakeStore()
    policy = asyncio.run(store.get_policy(tenant_context=_ctx()))
    assert policy.suppress_single_signal is False


def test_policy_round_trips_through_the_ports() -> None:
    store = _FakeStore()
    asyncio.run(
        store.set_policy(
            tenant_context=_ctx(),
            policy=MatcherPolicy(suppress_single_signal=True),
        )
    )
    back = asyncio.run(store.get_policy(tenant_context=_ctx()))
    assert back.suppress_single_signal is True


def test_set_is_idempotent_on_repeat() -> None:
    store = _FakeStore()
    p = MatcherPolicy(suppress_single_signal=True)
    asyncio.run(store.set_policy(tenant_context=_ctx(), policy=p))
    asyncio.run(store.set_policy(tenant_context=_ctx(), policy=p))
    assert asyncio.run(store.get_policy(tenant_context=_ctx())) == p
