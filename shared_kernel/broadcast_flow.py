"""BroadcastFlow Protocol — platform-initiated outbound contract (D142, S53).

D142 commits BroadcastFlow as the parallel abstraction to D115's
ConversationFlow Protocol. The two Protocols differ at the entry point:
ConversationFlow's ``turn`` consumes an inbound message;
BroadcastFlow's ``fire`` consumes a TriggerContext. The downstream
substrate is shared (CitedResponse Protocol from D138; D135 rendering
pattern; Message persistence; audit chain integration).

Per the S53 brief Finding 4 / pre-write reconciliation Finding 4:
BroadcastFlow lives at its own ``shared_kernel/broadcast_flow.py`` file
rather than sharing ``shared_kernel/conversation_flow.py`` because
BroadcastFlow is architecturally parallel (not an extension) to
ConversationFlow. The file imports ``CitedResponse`` and
``ArtefactCitation`` from ``shared_kernel/conversation_flow.py`` rather
than duplicating the citation shape.

TriggerContext is a frozen value object carrying a ``trigger_type``
discriminator plus per-type ``metadata`` (an open dict slot keyed by
the discriminator; per-type shapes settle at the implementer that
consumes the trigger). Phase 2-A trigger types: DAILY_SCHEDULED,
THRESHOLD_CROSSED, CALENDAR_EVENT, EMAIL_RECEIVED, MANUAL. Future
trigger types extend the enum additively without restructuring.

BroadcastResponse is a runtime-checkable Protocol that satisfies
CitedResponse Protocol structurally by carrying the three citation
tuple fields (``cited_intake_records``, ``cited_audit_events``,
``cited_artefacts``). Each BroadcastFlow implementer's response value
object satisfies the Protocol; the contract harness at
``tests/contract/broadcast_flow/`` verifies conformance.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


class BroadcastTriggerType(StrEnum):
    """The trigger type discriminator on TriggerContext (D142).

    Phase 2-A registers five values. Future trigger types extend
    additively; the BroadcastDispatch registry routes by this
    discriminator deterministically (no classifier consultation).
    """

    DAILY_SCHEDULED = "daily_scheduled"
    THRESHOLD_CROSSED = "threshold_crossed"
    CALENDAR_EVENT = "calendar_event"
    EMAIL_RECEIVED = "email_received"
    MANUAL = "manual"


@dataclass(frozen=True)
class TriggerContext:
    """The input that fires a BroadcastFlow implementer.

    ``trigger_type`` discriminates the trigger source. ``metadata`` is
    an implementer-owned open slot the trigger source populates with
    per-type metadata (e.g., the THRESHOLD_CROSSED trigger carries
    ``threshold_rule_id`` plus ``matched_audit_event_id``;
    DAILY_SCHEDULED carries no extra metadata at the Phase 2-A first
    instance). ``triggered_at`` is the ISO timestamp of trigger entry.
    ``trigger_id`` is the platform-assigned identifier for chain
    traversability — the BROADCAST_INITIATED audit event references
    this id.
    """

    trigger_type: BroadcastTriggerType
    trigger_id: UUID
    triggered_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BroadcastResponse(Protocol):
    """Platform-initiated outbound response shape (D142, S53).

    Satisfies CitedResponse Protocol from D138 structurally by carrying
    the three citation tuple fields. The ``@runtime_checkable``
    decorator allows isinstance conformance checks the contract harness
    exercises at
    ``tests/contract/broadcast_flow/test_broadcast_flow_conformance.py``.

    Per-implementer response value objects extend with implementer-
    specific fields (e.g., daily-briefing carries a summary block;
    threshold-briefing carries the matched rule plus the state delta);
    the Protocol commits the load-bearing minimum (the three citation
    tuples) and per-implementer extensions sit alongside.
    """

    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]


@runtime_checkable
class BroadcastFlow(Protocol):
    """Platform-initiated outbound contract (D142 primitive, S53 shape).

    An implementer satisfies ``BroadcastFlow`` structurally — no
    explicit inheritance is required. The ``@runtime_checkable``
    decorator additionally allows ``isinstance`` conformance checks the
    contract harness exercises.

    Per the BroadcastDispatch substrate at D143 the dispatch routes by
    ``trigger_context.trigger_type`` to the registered implementer; the
    implementer's ``fire`` runs to completion against the trigger and
    returns the BroadcastResponse. The dispatch persists the outbound
    message and emits the BROADCAST_INITIATED audit event around the
    implementer call.
    """

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        """Run the broadcast against the trigger; return the response."""
        ...


__all__ = [
    "BroadcastFlow",
    "BroadcastResponse",
    "BroadcastTriggerType",
    "TriggerContext",
]
