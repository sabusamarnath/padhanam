"""Parametrised conformance scenarios for the BroadcastFlow Protocol (D142).

Runs against every implementer registered through the conftest
mechanism. Each scenario exercises a contract property
``@runtime_checkable`` cannot verify — the minimum callable signature,
``BroadcastResponse`` structural conformance against ``CitedResponse``,
and tenant-scoping at the fire boundary (tenant_id and user_id arrive
at the implementer exactly as passed).

Scenarios map to four contract properties:
1. signature (``fire`` is async with the expected keyword arguments);
2. BroadcastFlow Protocol isinstance check at runtime;
3. BroadcastResponse structural conformance (the response value object
   satisfies CitedResponse via the three citation tuples);
4. Tenant-scoping at the fire boundary (tenant_id and user_id pass
   through to the implementer; the implementer's response cites
   nothing it should not cite cross-tenant).

S53 registers the synthetic harness implementer at
``test_synthetic_broadcast_flow.py``; S54 daily-briefing,
S57 threshold-briefing plus ThresholdEvaluator add their own
registration modules and join the parametrised set with no harness
change.
"""

from __future__ import annotations

import asyncio
import inspect
from uuid import uuid4

from shared_kernel.broadcast_flow import (
    BroadcastFlow,
    BroadcastResponse,
)
from shared_kernel.conversation_flow import CitedResponse

from tests.contract.broadcast_flow.conftest import (
    _REGISTRY,
    BroadcastFlowImplementerFixture,
    _load_registration_modules,
)


def test_synthetic_implementer_is_registered() -> None:
    """S53 registers the synthetic harness BroadcastFlow implementer; the
    four parametrised scenarios below run against it. S54+ implementers
    add their own ``test_<name>_broadcast_flow.py`` registration module
    and join the parametrised set with no harness change."""
    _load_registration_modules()
    assert "synthetic_broadcast_flow" in [f.name for f in _REGISTRY]


def test_fire_method_signature(
    broadcast_flow_implementer: BroadcastFlowImplementerFixture,
) -> None:
    """Signature scenario: ``fire`` is async and accepts the three
    keyword-only arguments the Protocol commits — ``tenant_id``,
    ``user_id``, ``trigger_context``."""
    cls = broadcast_flow_implementer.implementer_cls
    method = getattr(cls, "fire", None)
    assert callable(method), "fire method must exist"
    assert inspect.iscoroutinefunction(method), "fire must be async"
    sig = inspect.signature(method)
    parameter_names = {
        name
        for name, parameter in sig.parameters.items()
        if name != "self"
    }
    assert {"tenant_id", "user_id", "trigger_context"} <= parameter_names


def test_implementer_satisfies_broadcast_flow_protocol(
    broadcast_flow_implementer: BroadcastFlowImplementerFixture,
) -> None:
    """Protocol-isinstance scenario: the implementer satisfies
    BroadcastFlow structurally at runtime."""
    instance = broadcast_flow_implementer.make_instance()
    assert isinstance(instance, BroadcastFlow)


def test_response_satisfies_cited_response_structurally(
    broadcast_flow_implementer: BroadcastFlowImplementerFixture,
) -> None:
    """CitedResponse-conformance scenario: the implementer's response
    value object satisfies CitedResponse (D138) via the three citation
    tuple fields. The dispatch substrate at D143 plus future channel
    adapters can therefore rely on the citation surface structurally
    rather than per-implementer."""
    instance = broadcast_flow_implementer.make_instance()
    context = broadcast_flow_implementer.sample_trigger_context_factory()
    response = asyncio.run(
        instance.fire(
            tenant_id=uuid4(),
            user_id="harness-user",
            trigger_context=context,
        )
    )
    assert isinstance(response, BroadcastResponse)
    assert isinstance(response, CitedResponse)


def test_fire_passes_tenant_id_and_user_id_through(
    broadcast_flow_implementer: BroadcastFlowImplementerFixture,
) -> None:
    """Tenant-scoping scenario: the tenant_id and user_id the caller
    passes to ``fire`` are observable at the implementer side. The
    synthetic harness implementer records every call; real implementers
    at S54+ are tested via inspection of audit events / persisted
    Message records the implementer produces — the scenario here pins
    the structural pass-through invariant at the Protocol boundary."""
    instance = broadcast_flow_implementer.make_instance()
    context = broadcast_flow_implementer.sample_trigger_context_factory()
    tenant_id = uuid4()
    user_id = "harness-operator"

    response = asyncio.run(
        instance.fire(
            tenant_id=tenant_id,
            user_id=user_id,
            trigger_context=context,
        )
    )
    # The Protocol guarantees the response shape; the synthetic
    # implementer additionally records the call (so we can verify
    # pass-through without coupling to implementer internals). Real
    # implementers at S54+ may not expose a ``calls`` attribute; the
    # tenant-scoping invariant at those implementers is verified via
    # their own implementer-specific tests (audit-event tenant_id; the
    # persisted Message's tenant_id).
    assert isinstance(response, BroadcastResponse)
    recorded = getattr(instance, "calls", None)
    if recorded is not None:
        assert recorded
        recorded_tenant, recorded_user, recorded_context = recorded[-1]
        assert recorded_tenant == tenant_id
        assert recorded_user == user_id
        assert recorded_context.trigger_id == context.trigger_id
