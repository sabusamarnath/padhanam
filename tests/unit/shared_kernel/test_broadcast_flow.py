"""Unit tests for BroadcastFlow Protocol + TriggerContext + BroadcastResponse (D142, S53).

The Protocol is runtime-checkable; these tests verify the structural
typing surface plus the TriggerContext value object construction plus
BroadcastResponse's structural satisfaction of CitedResponse.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from shared_kernel.broadcast_flow import (
    BroadcastFlow,
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


# --------------------------------------------------------------------------- TriggerContext


def test_trigger_context_construction_with_each_trigger_type() -> None:
    """Every BroadcastTriggerType value constructs a TriggerContext cleanly."""
    triggered_at = "2026-05-27T10:00:00+00:00"
    for trigger_type in BroadcastTriggerType:
        context = TriggerContext(
            trigger_type=trigger_type,
            trigger_id=uuid4(),
            triggered_at=triggered_at,
        )
        assert context.trigger_type is trigger_type
        assert context.triggered_at == triggered_at
        # ``metadata`` defaults to an empty dict; per-type metadata
        # shapes settle at the implementer consuming the trigger.
        assert context.metadata == {}


def test_trigger_context_carries_per_type_metadata() -> None:
    """Per-type metadata populates via the open ``metadata`` slot."""
    threshold_metadata = {
        "threshold_rule_id": str(uuid4()),
        "matched_audit_event_id": str(uuid4()),
    }
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        trigger_id=uuid4(),
        triggered_at="2026-05-27T10:00:00+00:00",
        metadata=threshold_metadata,
    )
    assert context.metadata == threshold_metadata


def test_trigger_context_is_frozen() -> None:
    """TriggerContext is a frozen dataclass — direct attribute writes fail."""
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-27T10:00:00+00:00",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        context.trigger_id = uuid4()  # type: ignore[misc]


def test_broadcast_trigger_type_values() -> None:
    """The five Phase 2-A trigger types each carry a string value."""
    assert BroadcastTriggerType.DAILY_SCHEDULED.value == "daily_scheduled"
    assert BroadcastTriggerType.THRESHOLD_CROSSED.value == "threshold_crossed"
    assert BroadcastTriggerType.CALENDAR_EVENT.value == "calendar_event"
    assert BroadcastTriggerType.EMAIL_RECEIVED.value == "email_received"
    assert BroadcastTriggerType.MANUAL.value == "manual"
    assert len(list(BroadcastTriggerType)) == 5


# --------------------------------------------------------------------------- BroadcastResponse


@dataclass(frozen=True)
class _SyntheticBroadcastResponse:
    """A minimal value object satisfying BroadcastResponse structurally."""

    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]
    # An implementer-specific extension field; the Protocol does not
    # require it and isinstance still passes.
    summary_text: str = ""


def test_broadcast_response_satisfies_protocol_structurally() -> None:
    """A value object carrying the three citation tuples satisfies the Protocol."""
    response = _SyntheticBroadcastResponse(
        cited_intake_records=(uuid4(),),
        cited_audit_events=(uuid4(),),
        cited_artefacts=(
            ArtefactCitation(artefact_id=uuid4(), artefact_type="case"),
        ),
    )
    assert isinstance(response, BroadcastResponse)


def test_broadcast_response_satisfies_cited_response_structurally() -> None:
    """BroadcastResponse and CitedResponse share the same three citation tuples;
    a value object satisfying one structurally also satisfies the other."""
    response = _SyntheticBroadcastResponse(
        cited_intake_records=(),
        cited_audit_events=(),
        cited_artefacts=(),
    )
    assert isinstance(response, BroadcastResponse)
    assert isinstance(response, CitedResponse)


def test_value_object_without_citation_fields_fails_isinstance() -> None:
    """A value object missing the citation tuples does not satisfy the Protocol."""

    @dataclass(frozen=True)
    class _MissingFields:
        text: str

    assert not isinstance(_MissingFields(text="hi"), BroadcastResponse)
    assert not isinstance(_MissingFields(text="hi"), CitedResponse)


# --------------------------------------------------------------------------- BroadcastFlow


class _SyntheticBroadcastFlow:
    """A minimal class satisfying BroadcastFlow structurally."""

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        return _SyntheticBroadcastResponse(
            cited_intake_records=(),
            cited_audit_events=(),
            cited_artefacts=(),
            summary_text=f"fired {trigger_context.trigger_type.value} for {user_id}",
        )


def test_broadcast_flow_satisfies_protocol() -> None:
    """A class with the ``fire`` method satisfies BroadcastFlow structurally."""
    implementer = _SyntheticBroadcastFlow()
    assert isinstance(implementer, BroadcastFlow)


def test_class_without_fire_method_fails_isinstance() -> None:
    """A class missing the ``fire`` method does not satisfy the Protocol."""

    class _MissingFire:
        async def turn(self, *args: object, **kwargs: object) -> None:  # noqa: ARG002
            pass

    assert not isinstance(_MissingFire(), BroadcastFlow)


def test_broadcast_flow_fire_method_runs() -> None:
    """The fire method runs to completion against a TriggerContext."""
    implementer = _SyntheticBroadcastFlow()
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-27T10:00:00+00:00",
    )
    response = asyncio.run(
        implementer.fire(
            tenant_id=uuid4(),
            user_id="operator-001",
            trigger_context=context,
        )
    )
    assert isinstance(response, BroadcastResponse)
    assert isinstance(response, _SyntheticBroadcastResponse)
    assert response.summary_text.startswith("fired daily_scheduled")
